from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from ..models import Game, MoveRecord, PuzzleAttempt, PuzzleReviewState, utcnow

FLAGGED = ("Blunder", "Mistake")


def ensure_review_state(db: Session, user_id: int, move: MoveRecord) -> PuzzleReviewState:
    state = db.query(PuzzleReviewState).filter_by(user_id=user_id, move_id=move.id).first()
    if state is None:
        state = PuzzleReviewState(user_id=user_id, move_id=move.id, due_at=utcnow())
        db.add(state)
        db.flush()
    return state


def ensure_review_states_for_user(db: Session, user_id: int) -> int:
    """Create missing review state only for engine-flagged personal mistakes."""
    moves = (
        db.query(MoveRecord)
        .join(Game, Game.id == MoveRecord.game_id)
        .outerjoin(PuzzleReviewState, (PuzzleReviewState.move_id == MoveRecord.id) & (PuzzleReviewState.user_id == user_id))
        .filter(
            Game.user_id == user_id,
            MoveRecord.is_player_move.is_(True),
            MoveRecord.classification.in_(FLAGGED),
            PuzzleReviewState.id.is_(None),
        )
        .all()
    )
    for move in moves:
        db.add(PuzzleReviewState(user_id=user_id, move_id=move.id, due_at=utcnow()))
    if moves:
        db.flush()
    return len(moves)


def apply_review(state: PuzzleReviewState, *, outcome: str, attempts_before_result: int) -> None:
    """Apply a conservative SM-2-derived interval update.

    The algorithm is deterministic, stored per position, and treats a solve
    after several tries as less durable than a first-try solve. It never lets
    an LLM decide a learning schedule.
    """
    now = utcnow()
    solved = outcome == "solved"
    if solved:
        quality_penalty = 0.15 if attempts_before_result else 0.0
        state.ease_factor = min(2.7, max(1.3, state.ease_factor + 0.1 - quality_penalty))
        state.repetitions += 1
        if state.repetitions == 1:
            state.interval_days = 1
        elif state.repetitions == 2:
            state.interval_days = 3
        else:
            state.interval_days = max(4, round(max(1, state.interval_days) * state.ease_factor))
    else:
        state.lapses += 1
        state.repetitions = 0
        state.interval_days = 1
        state.ease_factor = max(1.3, state.ease_factor - 0.2)
    state.last_attempt_at = now
    state.last_result = outcome
    state.due_at = now + timedelta(days=state.interval_days)


def record_review(
    db: Session,
    *,
    user_id: int,
    move: MoveRecord,
    outcome: str,
    attempts_before_result: int,
    response_seconds: int | None,
    idempotency_key: str,
) -> tuple[PuzzleReviewState, PuzzleAttempt, bool]:
    """Persist a server-scored review exactly once and return `(state, attempt, created)`."""
    state = ensure_review_state(db, user_id, move)
    existing = (
        db.query(PuzzleAttempt)
        .filter(PuzzleAttempt.review_state_id == state.id, PuzzleAttempt.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        return state, existing, False

    attempt = PuzzleAttempt(
        review_state_id=state.id,
        result=outcome,
        attempts_before_result=attempts_before_result,
        response_seconds=response_seconds,
        idempotency_key=idempotency_key,
    )
    db.add(attempt)
    apply_review(state, outcome=outcome, attempts_before_result=attempts_before_result)
    # Compatibility fields power legacy game-review UI while the real schedule
    # lives in PuzzleReviewState/PuzzleAttempt.
    move.puzzle_reviewed_at = state.last_attempt_at
    move.puzzle_correct = outcome == "solved"
    db.flush()
    return state, attempt, True
