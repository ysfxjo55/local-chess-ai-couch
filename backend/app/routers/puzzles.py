from __future__ import annotations

import io
from datetime import datetime

import chess
import chess.engine
import chess.pgn
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..db import get_db
from ..models import Game, MoveRecord, PuzzleReviewState, User
from ..schemas import (
    PuzzleAttemptRequest,
    PuzzleAttemptResponse,
    PuzzleExplanationResponse,
    PuzzleGameListResponse,
    PuzzleGameOption,
    PuzzleGuessRequest,
    PuzzleGuessResponse,
    PuzzleOut,
    PuzzleStatsResponse,
)
from ..services.coach_llm import generate_move_explanation
from ..services.skill_model import record_puzzle_evidence
from ..services.spaced_repetition import ensure_review_states_for_user, record_review
from ..services.stockfish_analysis import classify_cp_loss, cp_loss_for_player, format_game_context, white_cp

router = APIRouter(prefix="/api/puzzles", tags=["puzzles"])

FLAGGED = ("Blunder", "Mistake")
TIME_CLASS_PRIORITY = {"rapid": 0, "daily": 0, "blitz": 1, "bullet": 1, None: 1}


def _queue(db: Session, user_id: int, game_id: int | None = None):
    ensure_review_states_for_user(db, user_id)
    now = datetime.now().astimezone()
    query = (
        db.query(MoveRecord, Game, PuzzleReviewState)
        .join(Game, Game.id == MoveRecord.game_id)
        .join(
            PuzzleReviewState,
            and_(PuzzleReviewState.move_id == MoveRecord.id, PuzzleReviewState.user_id == user_id),
        )
        .filter(
            Game.user_id == user_id,
            MoveRecord.is_player_move.is_(True),
            MoveRecord.classification.in_(FLAGGED),
            or_(PuzzleReviewState.last_attempt_at.is_(None), PuzzleReviewState.due_at <= now),
        )
    )
    if game_id is not None:
        query = query.filter(Game.id == game_id)
    return query


def _find_move(db: Session, user_id: int, game_id: int, ply: int) -> tuple[MoveRecord, Game] | None:
    row = (
        db.query(MoveRecord, Game)
        .join(Game, Game.id == MoveRecord.game_id)
        .filter(
            Game.user_id == user_id,
            MoveRecord.game_id == game_id,
            MoveRecord.ply == ply,
            MoveRecord.is_player_move.is_(True),
            MoveRecord.classification.in_(FLAGGED),
        )
        .first()
    )
    return row


@router.get("/games", response_model=PuzzleGameListResponse)
def puzzle_games(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = (
        _queue(db, current_user.id)
        .with_entities(Game.id, Game.opponent, Game.time_class, Game.played_at, func.count(MoveRecord.id).label("count"))
        .group_by(Game.id, Game.opponent, Game.time_class, Game.played_at)
        .order_by(Game.played_at.desc())
        .all()
    )
    return PuzzleGameListResponse(
        games=[
            PuzzleGameOption(
                game_id=row.id,
                opponent=row.opponent,
                count=row.count,
                time_class=row.time_class,
                played_at=row.played_at,
            )
            for row in rows
        ]
    )


@router.get("/next", response_model=PuzzleOut | None)
def next_puzzle(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    game_id: int | None = Query(default=None, ge=1),
):
    rows = _queue(db, current_user.id, game_id=game_id).all()
    if not rows:
        db.commit()  # persist any freshly created review states
        return None

    if game_id is not None:
        rows.sort(key=lambda pair: pair[0].ply)
    else:
        rows.sort(
            key=lambda pair: (
                0 if pair[2].last_attempt_at is not None else 1,  # due reviews before unseen material
                pair[2].due_at,
                TIME_CLASS_PRIORITY.get(pair[1].time_class, 1),
                0 if pair[0].classification == "Blunder" else 1,
                -(pair[0].cp_loss or 0),
            )
        )
        last_state = (
            db.query(PuzzleReviewState)
            .filter(PuzzleReviewState.user_id == current_user.id, PuzzleReviewState.last_attempt_at.isnot(None))
            .order_by(PuzzleReviewState.last_attempt_at.desc())
            .first()
        )
        if last_state:
            last_game_id = (
                db.query(MoveRecord.game_id).filter(MoveRecord.id == last_state.move_id).scalar()
            )
            if rows[0][1].id == last_game_id:
                alternative = next((row for row in rows if row[1].id != last_game_id), None)
                if alternative:
                    rows.remove(alternative)
                    rows.insert(0, alternative)

    move, game, state = rows[0]
    db.commit()
    return PuzzleOut(
        game_id=game.id,
        ply=move.ply,
        label=move.label,
        classification=move.classification or "Mistake",
        cp_loss=move.cp_loss,
        opponent=game.opponent,
        player_color=game.player_color,
        time_class=game.time_class,
        remaining=len(rows),
        total=len(rows),
        due_at=state.due_at,
        interval_days=state.interval_days,
    )


@router.post("/attempt", response_model=PuzzleAttemptResponse)
def attempt_puzzle(
    payload: PuzzleAttemptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    found = _find_move(db, current_user.id, payload.game_id, payload.ply)
    if found is None:
        raise HTTPException(status_code=404, detail="Puzzle not found")
    move, game = found
    state, attempt, created = record_review(
        db,
        user_id=current_user.id,
        move=move,
        outcome=payload.outcome,
        attempts_before_result=payload.attempts_before_result,
        response_seconds=payload.response_seconds,
        idempotency_key=payload.idempotency_key,
    )
    if created:
        record_puzzle_evidence(
            db,
            user_id=current_user.id,
            game=game,
            move=move,
            attempt_id=attempt.id,
            outcome=payload.outcome,
            occurred_at=attempt.created_at,
        )
    db.commit()
    return PuzzleAttemptResponse(
        recorded=True,
        remaining=_queue(db, current_user.id).count(),
        due_at=state.due_at,
        interval_days=state.interval_days,
    )


@router.post("/{game_id}/{ply}/guess", response_model=PuzzleGuessResponse)
def guess_puzzle(
    game_id: int,
    ply: int,
    payload: PuzzleGuessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    found = _find_move(db, current_user.id, game_id, ply)
    if found is None:
        raise HTTPException(status_code=404, detail="Puzzle not found")
    move, game = found
    if not game.pgn:
        raise HTTPException(status_code=422, detail="Could not replay this game's PGN")

    parsed = chess.pgn.read_game(io.StringIO(game.pgn))
    if parsed is None:
        raise HTTPException(status_code=422, detail="Could not replay this game's PGN")
    board = parsed.board()
    for index, game_move in enumerate(parsed.mainline_moves()):
        if index >= ply:
            break
        board.push(game_move)
    try:
        guess = chess.Move.from_uci(payload.from_square + payload.to_square + (payload.promotion or ""))
    except ValueError:
        raise HTTPException(status_code=422, detail="Malformed move")
    if guess not in board.legal_moves:
        raise HTTPException(status_code=422, detail="Illegal move")

    san = board.san(guess)
    board.push(guess)
    if not settings.STOCKFISH_PATH:
        raise HTTPException(status_code=503, detail="Puzzle engine is not configured")
    try:
        with chess.engine.SimpleEngine.popen_uci(settings.STOCKFISH_PATH) as engine:
            evaluation = white_cp(engine.analyse(board, chess.engine.Limit(time=settings.PUZZLE_ENGINE_SECONDS))["score"])
    except (FileNotFoundError, chess.engine.EngineError):
        raise HTTPException(status_code=503, detail="Puzzle engine is unavailable")

    cp_loss = cp_loss_for_player(move.eval_before or 0, evaluation, game.player_color or "")
    classification = classify_cp_loss(cp_loss)
    solved = classification in ("Excellent", "Good")
    if not solved:
        return PuzzleGuessResponse(san=san, classification=classification, cp_loss=cp_loss, is_best=cp_loss <= 15, solved=False)

    state, attempt, created = record_review(
        db,
        user_id=current_user.id,
        move=move,
        outcome="solved",
        attempts_before_result=payload.attempts_before_result,
        response_seconds=payload.response_seconds,
        idempotency_key=payload.idempotency_key,
    )
    if created:
        record_puzzle_evidence(
            db,
            user_id=current_user.id,
            game=game,
            move=move,
            attempt_id=attempt.id,
            outcome="solved",
            occurred_at=attempt.created_at,
        )
    db.commit()
    return PuzzleGuessResponse(
        san=san,
        classification=classification,
        cp_loss=cp_loss,
        is_best=cp_loss <= 15,
        solved=True,
        recorded=True,
        remaining=_queue(db, current_user.id).count(),
        due_at=state.due_at,
    )


@router.get("/{game_id}/{ply}/explain", response_model=PuzzleExplanationResponse)
def explain_puzzle(
    game_id: int,
    ply: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    found = _find_move(db, current_user.id, game_id, ply)
    if found is None:
        raise HTTPException(status_code=404, detail="Puzzle not found")
    move, game = found
    if move.explanation:
        return PuzzleExplanationResponse(explanation=move.explanation)
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
    explanation = generate_move_explanation(
        format_game_context(ctx), move.label, move.san, move.best_move, move.classification, move.cp_loss
    )
    move.explanation = explanation
    db.commit()
    return PuzzleExplanationResponse(explanation=explanation)


@router.get("/stats", response_model=PuzzleStatsResponse)
def puzzle_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_review_states_for_user(db, current_user.id)
    total = (
        db.query(MoveRecord)
        .join(Game, Game.id == MoveRecord.game_id)
        .filter(Game.user_id == current_user.id, MoveRecord.is_player_move.is_(True), MoveRecord.classification.in_(FLAGGED))
        .count()
    )
    states = db.query(PuzzleReviewState).filter(PuzzleReviewState.user_id == current_user.id)
    solved = states.filter(PuzzleReviewState.last_attempt_at.isnot(None)).count()
    correct = states.filter(PuzzleReviewState.last_result == "solved").count()
    due = _queue(db, current_user.id).count()
    db.commit()
    return PuzzleStatsResponse(total=total, due=due, solved=solved, correct=correct)
