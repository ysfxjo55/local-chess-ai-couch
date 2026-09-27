from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import Game, SkillState, User
from ..schemas import CompletePlanItemResponse, DailyPlanItemOut, DailyPlanResponse, PlayerProfileResponse, SkillStateOut
from ..services.daily_plan import complete_plan_item, generate_daily_plan

router = APIRouter(prefix="/api/learning", tags=["learning"])


def _state_out(state: SkillState) -> SkillStateOut:
    return SkillStateOut(
        skill_key=state.skill_key,
        mastery=state.mastery,
        confidence=state.confidence,
        evidence_count=state.evidence_count,
        priority=state.priority,
        last_evidence_at=state.last_evidence_at,
    )


def _plan_out(plan) -> DailyPlanResponse:  # noqa: ANN001
    items = sorted(plan.items, key=lambda item: item.ordinal)
    return DailyPlanResponse(
        id=plan.id,
        plan_date=plan.plan_date,
        timezone=plan.timezone,
        generated_at=plan.generated_at,
        items=[
            DailyPlanItemOut(
                id=item.id,
                ordinal=item.ordinal,
                kind=item.kind,
                reference_id=item.reference_id,
                title=item.title,
                rationale=item.rationale,
                target_minutes=item.target_minutes,
                completed_at=item.completed_at,
            )
            for item in items
        ],
    )


@router.get("/profile", response_model=PlayerProfileResponse)
def player_profile(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    states = db.query(SkillState).filter(SkillState.user_id == current_user.id).all()
    strengths = sorted(states, key=lambda state: (-state.mastery, -state.confidence))[:3]
    focus = sorted(states, key=lambda state: (-state.priority, -state.confidence))[:3]
    games_analyzed = db.query(Game.id).filter(Game.user_id == current_user.id).count()
    return PlayerProfileResponse(
        generated_at=datetime.now(timezone.utc),
        games_analyzed=games_analyzed,
        strengths=[_state_out(state) for state in strengths],
        focus_areas=[_state_out(state) for state in focus],
        methodology="Evidence is calculated from your engine-analyzed games and server-scored practice reviews. Practice and real-game evidence are stored separately; the coach should cite the underlying games rather than infer a pattern from chat alone.",
    )


@router.get("/daily-plan", response_model=DailyPlanResponse)
def daily_plan(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    plan = generate_daily_plan(db, current_user)
    db.commit()
    db.refresh(plan)
    return _plan_out(plan)


@router.post("/daily-plan/items/{item_id}/complete", response_model=CompletePlanItemResponse)
def complete_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = complete_plan_item(db, current_user.id, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Plan item not found")
    return CompletePlanItemResponse(completed=True, completed_at=item.completed_at)
