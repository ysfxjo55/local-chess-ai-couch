from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import Game, MoveRecord, SkillEvidence, SkillState, utcnow


def phase_for_ply(ply: int) -> str:
    if ply <= 20:
        return "opening"
    if ply <= 60:
        return "middlegame"
    return "endgame"


def _opening_key(opening: str | None) -> str:
    normalized = " ".join((opening or "unknown opening").lower().split())
    return f"opening:{normalized[:72]}"


def skill_keys(game: Game, move: MoveRecord) -> list[str]:
    return [f"phase:{phase_for_ply(move.ply)}", _opening_key(game.opening)]


def _engine_weight(classification: str | None) -> float:
    return {
        "Excellent": 1.0,
        "Good": 0.4,
        "Inaccuracy": -0.4,
        "Mistake": -0.8,
        "Blunder": -1.2,
    }.get(classification or "", 0.0)


def _upsert_state(db: Session, user_id: int, key: str, weight: float, occurred_at: datetime) -> None:
    state = db.query(SkillState).filter_by(user_id=user_id, skill_key=key).first()
    if state is None:
        state = SkillState(user_id=user_id, skill_key=key, mastery=0.5, confidence=0.0, evidence_count=0)
        db.add(state)
    old_score = (state.mastery - 0.5) * 2 * state.evidence_count
    state.evidence_count += 1
    # Dampens noisy individual moves; a new event can never swing a mature
    # profile as much as an early sparse profile.
    normalized_score = max(-1.0, min(1.0, (old_score + weight) / max(1, state.evidence_count)))
    state.mastery = round(0.5 + normalized_score / 2, 4)
    state.confidence = round(min(0.95, state.evidence_count / 12), 4)
    state.priority = round((1 - state.mastery) * state.confidence, 4)
    state.last_evidence_at = occurred_at
    # autoflush is off (see db.py); without this, two moves in the same game
    # hitting the same skill_key would both try to INSERT a new row, since
    # the second lookup can't see the first one's still-pending insert.
    db.flush()


def record_engine_evidence(db: Session, user_id: int, game: Game, moves: list[MoveRecord]) -> int:
    """Add organic game evidence only once per move/skill key."""
    created = 0
    for move in moves:
        if not move.is_player_move or move.classification is None:
            continue
        for key in skill_keys(game, move):
            exists = (
                db.query(SkillEvidence.id)
                .filter_by(user_id=user_id, source_type="move", source_id=str(move.id), skill_key=key)
                .first()
            )
            if exists:
                continue
            weight = _engine_weight(move.classification)
            evidence = SkillEvidence(
                user_id=user_id,
                source_type="move",
                source_id=str(move.id),
                skill_key=key,
                context="organic",
                outcome=move.classification.lower(),
                weight=weight,
                occurred_at=game.played_at or utcnow(),
                metadata_json=json.dumps({"game_id": game.id, "ply": move.ply, "classification": move.classification}),
            )
            db.add(evidence)
            _upsert_state(db, user_id, key, weight, evidence.occurred_at)
            created += 1
    return created


def record_puzzle_evidence(
    db: Session,
    *,
    user_id: int,
    game: Game,
    move: MoveRecord,
    attempt_id: int,
    outcome: str,
    occurred_at: datetime | None = None,
) -> int:
    """Practice evidence is tracked independently from organic play evidence."""
    at = occurred_at or utcnow()
    created = 0
    weight = 0.8 if outcome == "solved" else -0.7
    for key in skill_keys(game, move):
        exists = (
            db.query(SkillEvidence.id)
            .filter_by(user_id=user_id, source_type="puzzle_attempt", source_id=str(attempt_id), skill_key=key)
            .first()
        )
        if exists:
            continue
        evidence = SkillEvidence(
            user_id=user_id,
            source_type="puzzle_attempt",
            source_id=str(attempt_id),
            skill_key=key,
            context="practice",
            outcome=outcome,
            weight=weight,
            occurred_at=at,
            metadata_json=json.dumps({"game_id": game.id, "ply": move.ply}),
        )
        db.add(evidence)
        _upsert_state(db, user_id, key, weight, at)
        created += 1
    return created
