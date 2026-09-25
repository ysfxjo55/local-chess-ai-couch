from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..db import get_db
from ..auth import create_access_token, hash_password, verify_password, get_current_user
from ..models import User
from ..schemas import LoginRequest, RegisterRequest, MeResponse, TokenResponse, SetChesscomUsernameRequest, QuickStartRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if len(payload.username) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username must be at least 3 characters",
        )
    if len(payload.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 6 characters",
        )

    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id, username=user.username)
    return TokenResponse(access_token=token, token_type="bearer")


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_access_token(user_id=user.id, username=user.username)
    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/me", response_model=MeResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return MeResponse(
        username=current_user.username,
        chesscom_username=current_user.chesscom_username,
    )


@router.put("/chesscom-username", response_model=MeResponse)
def set_chesscom_username(
    payload: SetChesscomUsernameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    name = payload.chesscom_username.strip()
    if len(name) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Chess.com username must be at least 3 characters",
        )
    current_user.chesscom_username = name
    db.commit()
    db.refresh(current_user)
    return MeResponse(
        username=current_user.username,
        chesscom_username=current_user.chesscom_username,
    )


@router.post("/quick-start", response_model=TokenResponse)
def quick_start(payload: QuickStartRequest, db: Session = Depends(get_db)):
    """Single-field sign-in: enter a Chess.com username, get logged into
    that account if it already exists, or get one auto-created and logged
    in immediately if it doesn't. No password, no separate sign-up step —
    this is a single-user local app, not a public multi-tenant one, so
    Chess.com-username-as-identity is an accepted tradeoff here.
    """
    name = payload.chesscom_username.strip()
    if len(name) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Chess.com username must be at least 3 characters",
        )

    existing = db.query(User).filter(User.chesscom_username == name).first()
    if existing:
        token = create_access_token(user_id=existing.id, username=existing.username)
        return TokenResponse(access_token=token, token_type="bearer")

    # Auto-create a new account: username = the Chess.com name, random password
    import secrets
    auto_password = secrets.token_urlsafe(16)
    auto_username = name  # use Chess.com username as the app username

    # Handle collision (unlikely but safe)
    if db.query(User).filter(User.username == auto_username).first():
        auto_username = f"{name}_{secrets.token_hex(3)}"

    user = User(
        username=auto_username,
        password_hash=hash_password(auto_password),
        chesscom_username=name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id, username=user.username)
    return TokenResponse(access_token=token, token_type="bearer")
