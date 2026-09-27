from __future__ import annotations

import hmac
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..config import settings
from ..db import get_db
from ..models import User
from ..schemas import (
    ClaimAccountRequest,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    SetChesscomUsernameRequest,
    TokenResponse,
    UpdateProfileRequest,
)
from ..services.rate_limits import rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _clean_username(value: str) -> str:
    return value.strip()


def _clean_chesscom_username(value: str) -> tuple[str, str]:
    cleaned = value.strip()
    return cleaned, cleaned.lower()


def _me(user: User) -> MeResponse:
    return MeResponse(username=user.username, chesscom_username=user.chesscom_username, timezone=user.timezone or "UTC")


def _issue(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user_id=user.id, username=user.username, token_version=user.token_version),
    )


def _require_registration_code(code: str | None) -> None:
    if settings.REGISTRATION_CODE and not hmac.compare_digest(code or "", settings.REGISTRATION_CODE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="A valid registration code is required")


@router.post("/register", response_model=TokenResponse, dependencies=[Depends(rate_limit("register", 5, 15 * 60))])
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    _require_registration_code(payload.registration_code)
    username = _clean_username(payload.username)
    existing = db.query(User.id).filter(func.lower(User.username) == username.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    user = User(username=username, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
    db.refresh(user)
    return _issue(user)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit("login", 8, 15 * 60))])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    username = _clean_username(payload.username)
    user = db.query(User).filter(func.lower(User.username) == username.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        # Intentionally identical response avoids account enumeration.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    return _issue(user)


@router.post("/claim", response_model=TokenResponse, dependencies=[Depends(rate_limit("claim", 3, 60 * 60))])
def claim_legacy_account(payload: ClaimAccountRequest, db: Session = Depends(get_db)):
    """One-time recovery path for legacy no-password quick-start accounts."""
    if not settings.ACCOUNT_CLAIM_CODE or not hmac.compare_digest(payload.claim_code, settings.ACCOUNT_CLAIM_CODE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="A valid legacy account claim code is required")
    display_name, normalized = _clean_chesscom_username(payload.chesscom_username)
    user = db.query(User).filter(User.chesscom_username_norm == normalized).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No legacy account is available to claim for this Chess.com username")
    user.password_hash = hash_password(payload.password)
    user.chesscom_username = display_name
    user.chesscom_username_norm = normalized
    user.token_version += 1
    db.commit()
    db.refresh(user)
    return _issue(user)


@router.get("/me", response_model=MeResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return _me(current_user)


@router.put("/profile", response_model=MeResponse)
def update_profile(
    payload: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.chesscom_username is not None:
        display_name, normalized = _clean_chesscom_username(payload.chesscom_username)
        other = db.query(User.id).filter(User.chesscom_username_norm == normalized, User.id != current_user.id).first()
        if other:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That Chess.com username is already linked to another account")
        current_user.chesscom_username = display_name
        current_user.chesscom_username_norm = normalized
    if payload.timezone is not None:
        try:
            ZoneInfo(payload.timezone)
        except ZoneInfoNotFoundError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Use a valid IANA timezone such as Asia/Riyadh or UTC")
        current_user.timezone = payload.timezone
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That Chess.com username is already linked to another account")
    db.refresh(current_user)
    return _me(current_user)


@router.put("/chesscom-username", response_model=MeResponse)
def set_chesscom_username(
    payload: SetChesscomUsernameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Backward-compatible endpoint; uses the same uniqueness and validation
    # rule as the complete profile update route.
    return update_profile(
        UpdateProfileRequest(chesscom_username=payload.chesscom_username), db, current_user
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Versioned JWTs make logout/revocation effective immediately without
    # storing bearer token material in the browser or database.
    current_user.token_version += 1
    db.commit()
    return None


@router.post("/quick-start", status_code=status.HTTP_410_GONE)
def quick_start_disabled():
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Quick start has been disabled. Sign in with a password-protected account instead.",
    )
