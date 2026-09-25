import io
import threading
import chess.pgn
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..db import get_db, SessionLocal
from ..auth import get_current_user
from ..config import settings
from ..models import Game, MoveRecord, ChatMessage, InsightsRule, User
from ..schemas import GameDetail, MoveOut, ChatMessageOut, SyncStatusResponse, SyncBlunderHighlight, GameSyncItem, PaginatedGamesResponse, GameListItem, AnalysisResponse
from ..services.fetch_chess_com import fetch_recent_games, ChessComUnavailable
import chess.engine
from ..services.stockfish_analysis import build_game_context, analyze_game_enriched, parse_played_at, build_analysis_summary, format_game_context
from sqlalchemy import func
from ..services.coach_llm import SYSTEM_PROMPT, generate_analysis, generate_key_takeaway

router = APIRouter(prefix="/api/games", tags=["games"])

# Sync (especially a brand-new account's first sync, which pulls its whole
# Chess.com history) can take many minutes — Stockfish analyzes every move
# of every new game. That's far longer than Cloudflare's tunnel/edge will
# hold a single HTTP request open for, so sync runs in a background thread:
# POST /sync starts it and returns immediately, GET /sync/status is polled
# for progress. `_syncing_user_ids` prevents a double-tap (or a client
# retrying after it gave up waiting) from starting a second overlapping job
# for the same account, which used to be able to throw "database is locked".
_syncing_user_ids: set[int] = set()
_syncing_lock = threading.Lock()
_sync_jobs: dict[int, dict] = {}
_sync_jobs_lock = threading.Lock()


def _default_job() -> dict:
    return {
        "status": "running", "processed": 0, "total": 0, "new_games": 0, "games": [], "error": None,
        "blunders_found": 0, "worst_blunder": None,
    }


def _set_job(user_id: int, **fields) -> None:
    with _sync_jobs_lock:
        job = _sync_jobs.setdefault(user_id, _default_job())
        job.update(fields)


@router.post("/sync", response_model=SyncStatusResponse)
def sync_games(current_user: User = Depends(get_current_user)):
    if not current_user.chesscom_username:
        raise HTTPException(status_code=400, detail="no_chesscom_username")

    with _syncing_lock:
        if current_user.id in _syncing_user_ids:
            return SyncStatusResponse(**_sync_jobs.get(current_user.id, {"status": "running"}))
        _syncing_user_ids.add(current_user.id)

    _sync_jobs[current_user.id] = _default_job()
    threading.Thread(
        target=_run_sync_job,
        args=(current_user.id, current_user.chesscom_username),
        daemon=True,
    ).start()
    return SyncStatusResponse(**_sync_jobs[current_user.id])


@router.get("/sync/status", response_model=SyncStatusResponse)
def sync_status(current_user: User = Depends(get_current_user)):
    job = _sync_jobs.get(current_user.id)
    if job is None:
        return SyncStatusResponse(status="idle")
    return SyncStatusResponse(**job)


def _run_sync_job(user_id: int, chesscom_username: str) -> None:
    """Runs on a background thread — needs its own DB session, since the
    request-scoped one from `get_db` closes as soon as the endpoint above
    returns (which happens immediately, before this function starts)."""
    db = SessionLocal()
    try:
        _do_sync(db, user_id, chesscom_username)
    except Exception as e:
        _set_job(user_id, status="error", error=str(e))
    finally:
        db.close()
        with _syncing_lock:
            _syncing_user_ids.discard(user_id)


def _do_sync(db: Session, user_id: int, chesscom_username: str) -> None:
    # First sync ever for this account: pull the player's entire Chess.com
    # history, not just the current month — otherwise a brand-new account
    # only ever sees whatever was played so far this calendar month.
    is_first_sync = db.query(Game.id).filter(Game.user_id == user_id).first() is None
    months_back = None if is_first_sync else 1

    try:
        fetched_games = fetch_recent_games(chesscom_username, months_back=months_back)
    except ChessComUnavailable as e:
        _set_job(user_id, status="error", error=str(e))
        return

    _set_job(user_id, total=len(fetched_games))

    new_games_out: list[dict] = []
    blunders_found = 0
    worst_blunder: SyncBlunderHighlight | None = None

    with chess.engine.SimpleEngine.popen_uci(settings.STOCKFISH_PATH) as engine:
        for i, fetched in enumerate(fetched_games):
            pgn_text = fetched["pgn"]
            time_class = fetched["time_class"]
            parsed = chess.pgn.read_game(io.StringIO(pgn_text))
            if parsed is not None:
                chess_com_url = parsed.headers.get("Link")
                # Scoped per-user: two different app accounts can each hold
                # their own copy of the same Chess.com game (see models.py).
                existing = (
                    db.query(Game)
                    .filter(Game.chess_com_url == chess_com_url, Game.user_id == user_id)
                    .first()
                    if chess_com_url
                    else None
                )
                if existing is not None:
                    # Self-heals rows synced before time_class existed —
                    # only the current month ever passes through here on a
                    # normal incremental sync, so older rows still need the
                    # one-off backfill script for months outside that window.
                    if existing.time_class is None and time_class is not None:
                        existing.time_class = time_class
                        db.commit()
                elif chess_com_url:
                    ctx = build_game_context(parsed, chesscom_username)
                    played_at = parse_played_at(parsed.headers)
                    move_records, _ = analyze_game_enriched(parsed, engine, ctx["player_color"])

                    game = Game(
                        user_id=user_id,
                        chess_com_url=chess_com_url,
                        pgn=pgn_text,
                        event=ctx["event"],
                        date=ctx["date"],
                        white=ctx["white"],
                        black=ctx["black"],
                        result=ctx["result"],
                        player_color=ctx["player_color"],
                        opponent=ctx["opponent"],
                        player_outcome=ctx["player_outcome"],
                        opening=ctx["opening"],
                        time_class=time_class,
                        played_at=played_at,
                    )
                    db.add(game)
                    db.flush()  # assigns game.id before we attach MoveRecords

                    game_blunders = [
                        r for r in move_records
                        if r["is_player_move"] and r["classification"] == "Blunder"
                    ]
                    if game_blunders:
                        blunders_found += len(game_blunders)
                        worst_in_game = max(game_blunders, key=lambda r: r["cp_loss"])
                        if worst_blunder is None or worst_in_game["cp_loss"] > worst_blunder.cp_loss:
                            worst_blunder = SyncBlunderHighlight(
                                game_id=game.id,
                                opponent=ctx["opponent"],
                                label=worst_in_game["label"],
                                san=worst_in_game["san"],
                                cp_loss=worst_in_game["cp_loss"],
                            )

                    for ply, record in enumerate(move_records):
                        db.add(MoveRecord(game_id=game.id, ply=ply, **record))

                    # Commit per-game rather than once at the end: each
                    # transaction stays short (no more multi-minute lock
                    # window), and a crash/restart partway through a huge
                    # first sync doesn't throw away everything already done.
                    db.commit()

                    # Losses only, and best-effort: a lost game's "what went
                    # wrong" writeup and takeaway rule are worth having
                    # ready the moment you open the game, not gated behind a
                    # manual click — but an LLM hiccup here must never take
                    # the sync job down with it (a win/draw just doesn't get
                    # this at all; those aren't cost-effective to
                    # auto-generate for every synced game).
                    if ctx["player_outcome"] == "Loss":
                        try:
                            game_format = format_game_context(ctx)
                            analysis_summary = build_analysis_summary(ctx, move_records)
                            messages = [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {
                                    "role": "user",
                                    "content": f"### Game Details\n{game_format}\n\n### Move Analysis Summary\n{analysis_summary}",
                                },
                            ]
                            game.coach_analysis = generate_analysis(messages)
                            db.add(
                                InsightsRule(
                                    user_id=user_id,
                                    game_id=game.id,
                                    content=generate_key_takeaway(game_format, analysis_summary),
                                )
                            )
                            db.commit()
                        except Exception:
                            db.rollback()

                    new_games_out.append(
                        {
                            "id": game.id,
                            "opponent": game.opponent,
                            "result": game.result,
                            "player_color": game.player_color,
                            "played_at": game.played_at,
                            "time_class": game.time_class,
                        }
                    )

            _set_job(
                user_id,
                processed=i + 1,
                new_games=len(new_games_out),
                games=list(new_games_out),
                blunders_found=blunders_found,
                worst_blunder=worst_blunder,
            )

    _set_job(user_id, status="done")


@router.get("/{game_id}", response_model=GameDetail)
def get_game(game_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    game = db.query(Game).filter(Game.id == game_id, Game.user_id == current_user.id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    moves = db.query(MoveRecord).filter(MoveRecord.game_id == game_id).order_by(MoveRecord.ply).all()
    chat_history = db.query(ChatMessage).filter(ChatMessage.game_id == game_id, ChatMessage.user_id == current_user.id).order_by(ChatMessage.created_at).all()

    return GameDetail(
        id=game.id,
        event=game.event,
        date=game.date,
        white=game.white,
        black=game.black,
        result=game.result,
        player=current_user.username,
        player_color=game.player_color,
        opponent=game.opponent,
        player_outcome=game.player_outcome,
        time_class=game.time_class,
        moves=[MoveOut.model_validate(m) for m in moves],
        coach_analysis=game.coach_analysis,
        chat_history=[ChatMessageOut.model_validate(c) for c in chat_history],
    )

@router.get("", response_model=PaginatedGamesResponse)
def list_games(db: Session = Depends(get_db), current_user: User = Depends(get_current_user), offset: int = Query(default=0, ge=0), limit: int = Query(default=10, ge=1, le=100)):
    total_count = db.query(func.count(Game.id)).filter(Game.user_id == current_user.id).scalar()

    games_records = (
        db.query(Game)
        .filter(Game.user_id == current_user.id)
        .order_by(Game.played_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    game_list = []
    for g in games_records:
        blunders = db.query(MoveRecord).filter(MoveRecord.game_id == g.id, MoveRecord.is_player_move == True, MoveRecord.classification == "Blunder").count()
        mistakes = db.query(MoveRecord).filter(MoveRecord.game_id == g.id, MoveRecord.is_player_move == True, MoveRecord.classification == "Mistake").count()
        inaccuracies = db.query(MoveRecord).filter(MoveRecord.game_id == g.id, MoveRecord.is_player_move == True, MoveRecord.classification == "Inaccuracy").count()

        item = GameListItem(
            id=g.id,
            opponent=g.opponent,
            result=g.result,
            player_color=g.player_color,
            played_at=g.played_at,
            time_class=g.time_class,
            player_outcome=g.player_outcome,
            blunders=blunders,
            mistakes=mistakes,
            inaccuracies=inaccuracies,
        )
        game_list.append(item)
    return PaginatedGamesResponse(
        total=total_count,
        games=game_list,
    )

@router.post("/{id}/analysis", response_model=AnalysisResponse)
def analyze_game(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    game = db.query(Game).filter(Game.id == id, Game.user_id == current_user.id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    ctx = {
        "event": game.event,
        "date": game.date,
        "white": game.white,
        "black": game.black,
        "result": game.result,
        "player": current_user.username,
        "player_color": game.player_color,
        "opponent": game.opponent,
        "player_outcome": game.player_outcome,
    }
    moves = db.query(MoveRecord).filter(MoveRecord.game_id == id).order_by(MoveRecord.ply).all()
    move_dicts = [MoveOut.model_validate(m).model_dump() for m in moves]
    game_format = format_game_context(ctx)
    analysis_summary = build_analysis_summary(ctx, move_dicts)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",
            "content": f"### Game Details\n{game_format}\n\n### Move Analysis Summary\n{analysis_summary}"
        }
    ]
    content = generate_analysis(messages)
    game.coach_analysis = content
    db.commit()

    # One takeaway per lost game, generated once — an existing rule for
    # this game means a previous request already covered it (this endpoint
    # can be hit again, e.g. a page revisit before coach_analysis was
    # cached client-side).
    if game.player_outcome == "Loss":
        existing_rule = db.query(InsightsRule.id).filter(InsightsRule.game_id == id).first()
        if existing_rule is None:
            takeaway = generate_key_takeaway(game_format, analysis_summary)
            db.add(InsightsRule(user_id=current_user.id, game_id=id, content=takeaway))
            db.commit()

    return AnalysisResponse(coach_analysis=content)
