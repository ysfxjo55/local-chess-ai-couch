from __future__ import annotations

import io
import json
import threading
import uuid
from datetime import datetime

import chess.engine
import chess.pgn
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..db import SessionLocal, get_db
from ..models import AnalysisRun, Game, InsightsRule, MoveRecord, SyncJob, User, utcnow
from ..schemas import (
    AnalysisResponse,
    ChatMessageOut,
    GameDetail,
    GameListItem,
    GameSyncItem,
    MoveOut,
    PaginatedGamesResponse,
    SyncBlunderHighlight,
    SyncStatusResponse,
)
from ..services.coach_llm import SYSTEM_PROMPT, generate_analysis, generate_key_takeaway
from ..services.fetch_chess_com import ChessComUnavailable, fetch_recent_games
from ..services.rate_limits import rate_limit
from ..services.skill_model import record_engine_evidence
from ..services.stockfish_analysis import (
    analyze_game_enriched,
    build_analysis_summary,
    build_game_context,
    format_game_context,
    parse_played_at,
)

router = APIRouter(prefix="/api/games", tags=["games"])
_sync_create_lock = threading.Lock()


def _json_default(value):  # noqa: ANN001
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Unsupported type: {type(value)!r}")


def _job_summary(job: SyncJob) -> dict:
    try:
        summary = json.loads(job.summary_json or "{}")
        return summary if isinstance(summary, dict) else {}
    except json.JSONDecodeError:
        return {}


def _status(job: SyncJob) -> SyncStatusResponse:
    summary = _job_summary(job)
    games = []
    for item in summary.get("games", []):
        try:
            games.append(GameSyncItem(**item))
        except Exception:
            continue
    worst = None
    if isinstance(summary.get("worst_blunder"), dict):
        try:
            worst = SyncBlunderHighlight(**summary["worst_blunder"])
        except Exception:
            pass
    return SyncStatusResponse(
        job_id=job.id,
        status=job.status,
        processed=job.processed,
        total=job.total,
        new_games=job.new_games,
        games=games,
        error=job.error,
        blunders_found=int(summary.get("blunders_found", 0)),
        worst_blunder=worst,
    )


def _update_job(db: Session, job: SyncJob, **values) -> None:
    for key, value in values.items():
        setattr(job, key, value)
    job.heartbeat_at = utcnow()
    db.commit()


def recover_interrupted_sync_jobs() -> None:
    """Mark process-local runner work as interrupted after a restart."""
    db = SessionLocal()
    try:
        jobs = db.query(SyncJob).filter(SyncJob.status.in_(("queued", "running"))).all()
        for job in jobs:
            job.status = "error"
            job.error = "Sync was interrupted by a server restart. Start a new sync to continue safely."
            job.finished_at = utcnow()
        if jobs:
            db.commit()
    finally:
        db.close()


@router.post("/sync", response_model=SyncStatusResponse, dependencies=[Depends(rate_limit("sync", 4, 60 * 60))])
def sync_games(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.chesscom_username:
        raise HTTPException(status_code=400, detail="no_chesscom_username")
    if not settings.STOCKFISH_PATH:
        raise HTTPException(status_code=503, detail="Stockfish is not configured")

    with _sync_create_lock:
        running = (
            db.query(SyncJob)
            .filter(SyncJob.user_id == current_user.id, SyncJob.status.in_(("queued", "running")))
            .order_by(SyncJob.created_at.desc())
            .first()
        )
        if running:
            return _status(running)
        job = SyncJob(id=str(uuid.uuid4()), user_id=current_user.id, status="queued")
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
        chesscom_username = current_user.chesscom_username

    threading.Thread(target=_run_sync_job, args=(job_id, current_user.id, chesscom_username), daemon=True).start()
    return _status(job)


@router.get("/sync/status", response_model=SyncStatusResponse)
def sync_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = (
        db.query(SyncJob)
        .filter(SyncJob.user_id == current_user.id)
        .order_by(SyncJob.created_at.desc())
        .first()
    )
    return _status(job) if job else SyncStatusResponse(status="idle")


def _run_sync_job(job_id: str, user_id: int, chesscom_username: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(SyncJob, job_id)
        if not job:
            return
        job.status = "running"
        job.started_at = utcnow()
        _update_job(db, job)
        _do_sync(db, job, user_id, chesscom_username)
    except Exception:
        db.rollback()
        job = db.get(SyncJob, job_id)
        if job:
            job.status = "error"
            job.error = "Sync could not be completed. No partially imported game was discarded; try again later."
            job.finished_at = utcnow()
            db.commit()
    finally:
        db.close()


def _do_sync(db: Session, job: SyncJob, user_id: int, chesscom_username: str) -> None:
    first_sync = db.query(Game.id).filter(Game.user_id == user_id).first() is None
    try:
        fetched_games = fetch_recent_games(chesscom_username, months_back=None if first_sync else 1)
    except ChessComUnavailable as exc:
        job.status = "error"
        job.error = str(exc)
        job.finished_at = utcnow()
        db.commit()
        return

    job.total = len(fetched_games)
    db.commit()
    created_games: list[dict] = []
    blunders_found = 0
    worst_blunder: dict | None = None
    try:
        engine_context = chess.engine.SimpleEngine.popen_uci(settings.STOCKFISH_PATH)
    except (FileNotFoundError, chess.engine.EngineError):
        job.status = "error"
        job.error = "Stockfish is unavailable; verify STOCKFISH_PATH before retrying."
        job.finished_at = utcnow()
        db.commit()
        return

    try:
        with engine_context as engine:
            for index, fetched in enumerate(fetched_games, start=1):
                parsed = chess.pgn.read_game(io.StringIO(fetched["pgn"]))
                if parsed is None:
                    _update_job(db, job, processed=index)
                    continue
                chess_com_url = parsed.headers.get("Link")
                if not chess_com_url:
                    _update_job(db, job, processed=index)
                    continue
                existing = db.query(Game).filter(Game.user_id == user_id, Game.chess_com_url == chess_com_url).first()
                if existing:
                    if existing.time_class is None and fetched.get("time_class"):
                        existing.time_class = fetched["time_class"]
                    _update_job(db, job, processed=index)
                    continue

                context = build_game_context(parsed, chesscom_username)
                if context["player_color"] == "Unknown":
                    _update_job(db, job, processed=index)
                    continue
                move_records, _ = analyze_game_enriched(parsed, engine, context["player_color"])
                game = Game(
                    user_id=user_id,
                    chess_com_url=chess_com_url,
                    pgn=fetched["pgn"],
                    event=context["event"],
                    date=context["date"],
                    white=context["white"],
                    black=context["black"],
                    result=context["result"],
                    player_color=context["player_color"],
                    opponent=context["opponent"],
                    player_outcome=context["player_outcome"],
                    opening=context["opening"],
                    time_class=fetched.get("time_class"),
                    source="chesscom",
                    played_at=parse_played_at(parsed.headers),
                )
                db.add(game)
                try:
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    job = db.get(SyncJob, job.id)
                    _update_job(db, job, processed=index)
                    continue

                analysis_run = AnalysisRun(
                    game_id=game.id,
                    profile_version="stockfish-cpl-v1",
                    engine_name="Stockfish",
                    engine_options=json.dumps({"path": settings.STOCKFISH_PATH}),
                    analysis_seconds=settings.ENGINE_ANALYSIS_SECONDS,
                )
                db.add(analysis_run)
                db.flush()
                game.analysis_version = analysis_run.profile_version
                records: list[MoveRecord] = []
                for ply, record in enumerate(move_records):
                    model = MoveRecord(game_id=game.id, ply=ply, analysis_run_id=analysis_run.id, **record)
                    db.add(model)
                    records.append(model)
                db.flush()
                record_engine_evidence(db, user_id, game, records)
                game_blunders = [record for record in move_records if record["is_player_move"] and record["classification"] == "Blunder"]
                blunders_found += len(game_blunders)
                if game_blunders:
                    worst = max(game_blunders, key=lambda record: record["cp_loss"] or 0)
                    candidate = {"game_id": game.id, "opponent": game.opponent or "Unknown", "label": worst["label"], "san": worst["san"], "cp_loss": worst["cp_loss"] or 0}
                    if worst_blunder is None or candidate["cp_loss"] > worst_blunder["cp_loss"]:
                        worst_blunder = candidate
                created_games.append(
                    {"id": game.id, "opponent": game.opponent, "result": game.result, "player_color": game.player_color, "played_at": game.played_at, "time_class": game.time_class}
                )
                summary = {"games": created_games[-20:], "blunders_found": blunders_found, "worst_blunder": worst_blunder}
                _update_job(
                    db,
                    job,
                    processed=index,
                    new_games=len(created_games),
                    summary_json=json.dumps(summary, default=_json_default),
                )
    finally:
        pass

    job.status = "done"
    job.finished_at = utcnow()
    job.summary_json = json.dumps({"games": created_games[-20:], "blunders_found": blunders_found, "worst_blunder": worst_blunder}, default=_json_default)
    db.commit()


@router.get("/{game_id}", response_model=GameDetail)
def get_game(game_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    game = db.query(Game).filter(Game.id == game_id, Game.user_id == current_user.id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    moves = db.query(MoveRecord).filter(MoveRecord.game_id == game_id).order_by(MoveRecord.ply).all()
    from ..models import ChatMessage
    chat_history = (
        db.query(ChatMessage)
        .filter(ChatMessage.game_id == game_id, ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at)
        .limit(settings.COACH_HISTORY_LIMIT)
        .all()
    )
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
        opening=game.opening,
        time_class=game.time_class,
        moves=[MoveOut.model_validate(move) for move in moves],
        coach_analysis=game.coach_analysis,
        chat_history=[ChatMessageOut.model_validate(message) for message in chat_history],
    )


@router.get("", response_model=PaginatedGamesResponse)
def list_games(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
):
    total = db.query(func.count(Game.id)).filter(Game.user_id == current_user.id).scalar() or 0
    counts = (
        db.query(
            MoveRecord.game_id.label("game_id"),
            func.sum(case((MoveRecord.classification == "Blunder", 1), else_=0)).label("blunders"),
            func.sum(case((MoveRecord.classification == "Mistake", 1), else_=0)).label("mistakes"),
            func.sum(case((MoveRecord.classification == "Inaccuracy", 1), else_=0)).label("inaccuracies"),
        )
        .filter(MoveRecord.is_player_move.is_(True))
        .group_by(MoveRecord.game_id)
        .subquery()
    )
    records = (
        db.query(Game, counts.c.blunders, counts.c.mistakes, counts.c.inaccuracies)
        .outerjoin(counts, counts.c.game_id == Game.id)
        .filter(Game.user_id == current_user.id)
        .order_by(Game.played_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return PaginatedGamesResponse(
        total=total,
        games=[
            GameListItem(
                id=game.id,
                opponent=game.opponent,
                result=game.result,
                player_color=game.player_color,
                played_at=game.played_at,
                time_class=game.time_class,
                player_outcome=game.player_outcome,
                opening=game.opening,
                blunders=int(blunders or 0),
                mistakes=int(mistakes or 0),
                inaccuracies=int(inaccuracies or 0),
            )
            for game, blunders, mistakes, inaccuracies in records
        ],
    )


@router.post("/{id}/analysis", response_model=AnalysisResponse, dependencies=[Depends(rate_limit("analysis", 6, 60 * 60))])
def analyze_game(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    game = db.query(Game).filter(Game.id == id, Game.user_id == current_user.id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    moves = db.query(MoveRecord).filter(MoveRecord.game_id == id).order_by(MoveRecord.ply).all()
    context = {
        "event": game.event, "date": game.date, "white": game.white, "black": game.black,
        "result": game.result, "player": current_user.username, "player_color": game.player_color,
        "opponent": game.opponent, "player_outcome": game.player_outcome,
    }
    move_dicts = [MoveOut.model_validate(move).model_dump() for move in moves]
    game_format = format_game_context(context)
    summary = build_analysis_summary(context, move_dicts)
    content = generate_analysis([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"### Game Details\n{game_format}\n\n### Engine Evidence\n{summary}"},
    ])
    game.coach_analysis = content
    if game.player_outcome == "Loss" and not db.query(InsightsRule.id).filter(InsightsRule.game_id == id).first():
        db.add(InsightsRule(user_id=current_user.id, game_id=id, content=generate_key_takeaway(game_format, summary)))
    db.commit()
    return AnalysisResponse(coach_analysis=content)
