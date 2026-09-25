from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..auth import get_current_user
from ..models import User
from ..schemas import (
    SparringLevelsResponse,
    SparringTargetPreview,
    SparringStartRequest,
    SparringStartResponse,
    SparringMoveRequest,
    SparringMoveResponse,
    SparringWarning,
    SparringTakebackResponse,
)
from ..services import sparring

router = APIRouter(prefix="/api/sparring", tags=["sparring"])


@router.get("/levels", response_model=SparringLevelsResponse)
def levels():
    return SparringLevelsResponse(levels=sparring.available_levels())


@router.get("/target-preview", response_model=SparringTargetPreview | None)
def target_preview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    target = sparring.find_weak_opening_target(db, current_user.id)
    if not target:
        return None
    return SparringTargetPreview(
        opening=target["opening"],
        player_color=target["player_color"],
        win_rate=target["win_rate"],
        games=target["games"],
        seed_moves=target["seed_moves"],
    )


@router.post("/start", response_model=SparringStartResponse)
def start(
    payload: SparringStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.maia_level not in sparring.available_levels():
        raise HTTPException(status_code=422, detail="Unavailable Maia level")
    try:
        session = sparring.start_session(
            db, current_user.id, payload.maia_level, payload.target_weak_opening
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    target = (
        SparringTargetPreview(
            opening=session.target["opening"],
            player_color=session.target["player_color"],
            win_rate=session.target["win_rate"],
            games=session.target["games"],
            seed_moves=session.target["seed_moves"],
        )
        if session.target
        else None
    )
    return SparringStartResponse(
        session_id=session.id,
        fen=session.board.fen(),
        player_color=session.player_color,
        maia_level=session.maia_level,
        target=target,
        seed_moves=session.seed_moves,
        moves=session.sans,
        done=session.done,
    )


@router.post("/{session_id}/move", response_model=SparringMoveResponse)
def move(
    session_id: str,
    payload: SparringMoveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = sparring.get_session(session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sparring session not found")

    with session.lock:
        try:
            result = sparring.submit_move(
                db, session, payload.from_square, payload.to_square, payload.promotion
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    warning = SparringWarning(**result["warning"]) if result["warning"] else None
    return SparringMoveResponse(
        session_id=session_id,
        fen=result["fen"],
        player_san=result["player_san"],
        maia_san=result["maia_san"],
        warning=warning,
        done=result["done"],
        result=result["result"],
        game_id=result["game_id"],
    )


@router.post("/{session_id}/takeback", response_model=SparringTakebackResponse)
def take_back(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    session = sparring.get_session(session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sparring session not found")

    with session.lock:
        try:
            result = sparring.takeback(session)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    return SparringTakebackResponse(session_id=session_id, fen=result["fen"], moves=result["moves"])


@router.delete("/{session_id}")
def abandon(session_id: str, current_user: User = Depends(get_current_user)):
    ok = sparring.abandon_session(session_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Sparring session not found")
    return {"abandoned": True}
