from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ..models import DailyPlan, DailyPlanItem, Game, MoveRecord, PuzzleReviewState, SkillState, User, utcnow
from .spaced_repetition import ensure_review_states_for_user


def _day_for_user(user: User) -> tuple[str, str]:
    try:
        zone = ZoneInfo(user.timezone or "UTC")
    except Exception:
        zone = ZoneInfo("UTC")
    return datetime.now(zone).date().isoformat(), zone.key


def generate_daily_plan(db: Session, user: User) -> DailyPlan:
    plan_date, timezone_name = _day_for_user(user)
    existing = db.query(DailyPlan).filter_by(user_id=user.id, plan_date=plan_date).first()
    if existing:
        return existing

    ensure_review_states_for_user(db, user.id)
    now = utcnow()
    plan = DailyPlan(user_id=user.id, plan_date=plan_date, timezone=timezone_name)
    db.add(plan)
    db.flush()

    due = (
        db.query(PuzzleReviewState, MoveRecord, Game)
        .join(MoveRecord, MoveRecord.id == PuzzleReviewState.move_id)
        .join(Game, Game.id == MoveRecord.game_id)
        .filter(PuzzleReviewState.user_id == user.id, PuzzleReviewState.due_at <= now)
        .order_by(PuzzleReviewState.due_at.asc(), MoveRecord.cp_loss.desc())
        .limit(4)
        .all()
    )
    selected_move_ids = {state.move_id for state, _, _ in due}
    new_items = (
        db.query(PuzzleReviewState, MoveRecord, Game)
        .join(MoveRecord, MoveRecord.id == PuzzleReviewState.move_id)
        .join(Game, Game.id == MoveRecord.game_id)
        .filter(PuzzleReviewState.user_id == user.id, PuzzleReviewState.last_attempt_at.is_(None), PuzzleReviewState.move_id.notin_(selected_move_ids) if selected_move_ids else True)
        .order_by(MoveRecord.cp_loss.desc(), Game.played_at.desc())
        .limit(2)
        .all()
    )

    ordinal = 1
    snapshot_items: list[dict] = []
    for state, move, game in due:
        title = f"Review {move.label} vs {game.opponent or 'opponent'}"
        rationale = f"Due review: last result was {state.last_result or 'unseen'}; repeat it before adding new material."
        item = DailyPlanItem(plan_id=plan.id, ordinal=ordinal, kind="review", reference_id=f"{game.id}:{move.ply}", title=title, rationale=rationale, target_minutes=8)
        db.add(item)
        snapshot_items.append({"kind": "review", "move_id": move.id, "due_at": state.due_at.isoformat()})
        ordinal += 1
    for _, move, game in new_items:
        title = f"Learn {move.label} vs {game.opponent or 'opponent'}"
        rationale = f"New high-impact {move.classification.lower()} from your own game ({move.cp_loss or 0} cp loss)."
        item = DailyPlanItem(plan_id=plan.id, ordinal=ordinal, kind="new_puzzle", reference_id=f"{game.id}:{move.ply}", title=title, rationale=rationale, target_minutes=10)
        db.add(item)
        snapshot_items.append({"kind": "new_puzzle", "move_id": move.id})
        ordinal += 1

    focus = (
        db.query(SkillState)
        .filter(SkillState.user_id == user.id, SkillState.confidence >= 0.25)
        .order_by(SkillState.priority.desc())
        .first()
    )
    if focus:
        title = f"Focus block: {focus.skill_key.replace(':', ' — ').title()}"
        rationale = (
            f"This is a repeated pattern across {focus.evidence_count} evidence points; "
            f"current mastery estimate is {round(focus.mastery * 100)}%."
        )
        db.add(DailyPlanItem(plan_id=plan.id, ordinal=ordinal, kind="focus", reference_id=focus.skill_key, title=title, rationale=rationale, target_minutes=12))
        snapshot_items.append({"kind": "focus", "skill": focus.skill_key, "priority": focus.priority})

    plan.snapshot_json = json.dumps({"generated_at": now.isoformat(), "items": snapshot_items})
    db.flush()
    return plan


def complete_plan_item(db: Session, user_id: int, item_id: int) -> DailyPlanItem | None:
    item = (
        db.query(DailyPlanItem)
        .join(DailyPlan, DailyPlan.id == DailyPlanItem.plan_id)
        .filter(DailyPlanItem.id == item_id, DailyPlan.user_id == user_id)
        .first()
    )
    if item is None:
        return None
    if item.completed_at is None:
        item.completed_at = utcnow()
        db.commit()
        db.refresh(item)
    return item
