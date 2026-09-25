from datetime import datetime, timedelta, timezone
import bcrypt
from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.db import get_db
from backend.app.models import User


def hash_password(password: str) -> str:
    pw_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    try:
        pw_bytes = password.encode("utf-8")
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode = {"sub": username, "uid": user_id, "exp": expire}
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")


def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = parts[1]

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        username: str = payload.get("sub")
        user_id: int = payload.get("uid")
        if username is None or user_id is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
    except JWTError:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.id == user_id, User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user
