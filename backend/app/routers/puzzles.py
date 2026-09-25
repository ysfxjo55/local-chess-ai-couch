import io
from datetime import datetime
import chess
import chess.engine
import chess.pgn
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..db import get_db
from ..auth import get_current_user
from ..config import settings
from ..models import Game, MoveRecord, User
from ..schemas import (
    PuzzleOut,
    PuzzleAttemptRequest,
    PuzzleAttemptResponse,
    PuzzleStatsResponse,
    PuzzleExplanationResponse,
    PuzzleGuessRequest,
    PuzzleGuessResponse,
    PuzzleGameOption,
    PuzzleGameListResponse,
)
from ..services.stockfish_analysis import (
    format_game_context,
    white_cp,
    cp_loss_for_player,
    classify_cp_loss,
)
from ..services.coach_llm import generate_move_explanation

router = APIRouter(prefix="/api/puzzles", tags=["puzzles"])

FLAGGED = ("Blunder", "Mistake")
# Bullet/blitz blunders are disproportionately clock-pressure scrambles, not
# real understanding gaps — rapid/daily games are queued first so review
# time goes toward mistakes actually worth fixing. Bullet/blitz still show
# up once those run out, just last.
TIME_CLASS_PRIORITY = {"rapid": 0, "daily": 0, "blitz": 1, "bullet": 1, None: 1}


def _queue(db: Session, user_id: int, game_id: int | None = None):
    q = (
        db.query(MoveRecord, Game)
        .join(Game, Game.id == MoveRecord.game_id)
        .filter(
            Game.user_id == user_id,
            MoveRecord.is_player_move == True,  # noqa: E712
            MoveRecord.classification.in_(FLAGGED),
            MoveRecord.puzzle_reviewed_at.is_(None),
        )
    )
    if game_id is not None:
        q = q.filter(Game.id == game_id)
    return q


@router.get("/games", response_model=PuzzleGameListResponse)
def puzzle_games(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Games with at least one unreviewed flagged move — powers a "review
    this specific game's mistakes in order" picker, the Lichess-style game
    analysis view, as an alternative to the shuffled cross-game queue."""
    rows = (
        db.query(
            Game.id,
            Game.opponent,
            Game.time_class,
            Game.played_at,
            func.count(MoveRecord.id).label("count"),
        )
        .join(MoveRecord, MoveRecord.game_id == Game.id)
        .filter(
            Game.user_id == current_user.id,
            MoveRecord.is_player_move == True,  # noqa: E712
            MoveRecord.classification.in_(FLAGGED),
            MoveRecord.puzzle_reviewed_at.is_(None),
        )
        .group_by(Game.id, Game.opponent, Game.time_class, Game.played_at)
        # Most recent first — "review the game I just played" is the
        # natural use, not "the game with the most mistakes ever".
        .order_by(Game.played_at.desc())
        .all()
    )
    return PuzzleGameListResponse(
        games=[
            PuzzleGameOption(
                game_id=r.id, opponent=r.opponent, count=r.count,
                time_class=r.time_class, played_at=r.played_at,
            )
            for r in rows
        ]
    )


@router.get("/next", response_model=PuzzleOut | None)
def next_puzzle(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    game_id: int | None = Query(default=None),
):
    rows = _queue(db, current_user.id, game_id=game_id).all()
    if not rows:
        return None

    if game_id is not None:
        # Scoped to one game: "fix them in order" means chronological, not
        # re-sorted by severity/time-class — you're working through this
        # specific game's mistakes the way they actually happened.
        rows.sort(key=lambda pair: pair[0].ply)
    else:
        rows.sort(
            key=lambda pair: (
                TIME_CLASS_PRIORITY.get(pair[1].time_class, 1),
                0 if pair[0].classification == "Blunder" else 1,
            )
        )

        # Game diversity: don't serve the next puzzle from the exact same
        # game you just reviewed when another game has one available —
        # several in a row from one match both reads as repetitive and,
        # since the positions are inherently more similar within one game,
        # makes it harder to visually tell "did this advance" from "stuck".
        last_reviewed = (
            db.query(MoveRecord, Game)
            .join(Game, Game.id == MoveRecord.game_id)
            .filter(Game.user_id == current_user.id, MoveRecord.puzzle_reviewed_at.isnot(None))
            .order_by(MoveRecord.puzzle_reviewed_at.desc())
            .first()
        )
        if last_reviewed and rows[0][1].id == last_reviewed[1].id:
            alternative = next((pair for pair in rows if pair[1].id != last_reviewed[1].id), None)
            if alternative:
                rows.remove(alternative)
                rows.insert(0, alternative)

    move, game = rows[0]

    return PuzzleOut(
        game_id=game.id,
        ply=move.ply,
        label=move.label,
        classification=move.classification,
        cp_loss=move.cp_loss,
        opponent=game.opponent,
        player_color=game.player_color,
        time_class=game.time_class,
        remaining=len(rows),
        total=len(rows),
    )


@router.post("/attempt", response_model=PuzzleAttemptResponse)
def attempt_puzzle(
    payload: PuzzleAttemptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    move = (
        db.query(MoveRecord)
        .join(Game, Game.id == MoveRecord.game_id)
        .filter(
            Game.user_id == current_user.id,
            MoveRecord.game_id == payload.game_id,
            MoveRecord.ply == payload.ply,
        )
        .first()
    )
    if move is None:
        raise HTTPException(status_code=404, detail="Puzzle not found")

    move.puzzle_reviewed_at = datetime.now()
    move.puzzle_correct = payload.correct
    db.commit()

    remaining = _queue(db, current_user.id).count()
    return PuzzleAttemptResponse(recorded=True, remaining=remaining)


@router.post("/{game_id}/{ply}/guess", response_model=PuzzleGuessResponse)
def guess_puzzle(
    game_id: int,
    ply: int,
    payload: PuzzleGuessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lichess-style: rates the player's own attempted move live via
    Stockfish (reusing the exact same cp-loss classification as everywhere
    else in the app) instead of just comparing squares against the single
    stored best_move — a different, also-strong move should count as
    solved too, and a wrong guess gets a rating, not the answer, so the
    player can keep trying. Doesn't touch puzzle_reviewed_at/puzzle_correct
    — that only happens once via /attempt, when the puzzle is actually
    resolved (solved or given up on), not on every failed try."""
    move = (
        db.query(MoveRecord)
        .join(Game, Game.id == MoveRecord.game_id)
        .filter(Game.user_id == current_user.id, MoveRecord.game_id == game_id, MoveRecord.ply == ply)
        .first()
    )
    game = db.query(Game).filter(Game.id == game_id, Game.user_id == current_user.id).first()
    if move is None or game is None or not game.pgn:
        raise HTTPException(status_code=404, detail="Puzzle not found")

    parsed = chess.pgn.read_game(io.StringIO(game.pgn))
    if parsed is None:
        raise HTTPException(status_code=422, detail="Could not replay this game's PGN")

    board = chess.Board()
    for i, mv in enumerate(parsed.mainline_moves()):
        if i >= ply:
            break
        board.push(mv)

    try:
        guess = chess.Move.from_uci(payload.from_square + payload.to_square + (payload.promotion or ""))
    except ValueError:
        raise HTTPException(status_code=422, detail="Malformed move")
    if guess not in board.legal_moves:
        raise HTTPException(status_code=422, detail="Illegal move")

    guess_san = board.san(guess)
    board.push(guess)

    with chess.engine.SimpleEngine.popen_uci(settings.STOCKFISH_PATH) as engine:
        eval_after = white_cp(engine.analyse(board, chess.engine.Limit(time=0.15))["score"])

    cp_loss = cp_loss_for_player(move.eval_before, eval_after, game.player_color)
    classification = classify_cp_loss(cp_loss)

    # A short time-limited search isn't perfectly reproducible run-to-run —
    # re-evaluating the *actual* stored best_move here can itself come back
    # a few cp off "Excellent" purely from search noise between two
    # separate short searches, not a real difference in move quality. A
    # small tolerance (well under "Inaccuracy" at 30cp) absorbs that noise
    # without accepting genuinely inferior moves as solved.
    is_best = cp_loss <= 15

    return PuzzleGuessResponse(
        san=guess_san,
        classification=classification,
        cp_loss=cp_loss,
        is_best=is_best,
        # Passing bar is "not a mistake at all": Good/Excellent pass, while
        # Inaccuracy/Mistake/Blunder mean try again. A good-but-not-best
        # move still passes; the UI then shows what the best move was.
        solved=classification in ("Excellent", "Good"),
    )


@router.get("/{game_id}/{ply}/explain", response_model=PuzzleExplanationResponse)
def explain_puzzle(
    game_id: int,
    ply: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    move = (
        db.query(MoveRecord)
        .join(Game, Game.id == MoveRecord.game_id)
        .filter(
            Game.user_id == current_user.id,
            MoveRecord.game_id == game_id,
            MoveRecord.ply == ply,
        )
        .first()
    )
    if move is None:
        raise HTTPException(status_code=404, detail="Puzzle not found")

    if move.explanation:
        return PuzzleExplanationResponse(explanation=move.explanation)

    game = db.query(Game).filter(Game.id == game_id).first()
    ctx = {
        "event": game.event, "date": game.date, "white": game.white, "black": game.black,
        "result": game.result, "player": current_user.username, "player_color": game.player_color,
        "opponent": game.opponent, "player_outcome": game.player_outcome,
    }
    explanation = generate_move_explanation(
        format_game_context(ctx), move.label, move.san, move.best_move,
        move.classification, move.cp_loss,
    )
    move.explanation = explanation
    db.commit()
    return PuzzleExplanationResponse(explanation=explanation)


@router.get("/stats", response_model=PuzzleStatsResponse)
def puzzle_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    base = (
        db.query(MoveRecord)
        .join(Game, Game.id == MoveRecord.game_id)
        .filter(
            Game.user_id == current_user.id,
            MoveRecord.is_player_move == True,  # noqa: E712
            MoveRecord.classification.in_(FLAGGED),
        )
    )
    total = base.count()
    solved = base.filter(MoveRecord.puzzle_reviewed_at.isnot(None)).count()
    correct = base.filter(MoveRecord.puzzle_correct == True).count()  # noqa: E712
    return PuzzleStatsResponse(total=total, solved=solved, correct=correct)
