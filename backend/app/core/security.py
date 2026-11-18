"""Password hashing and JWT session cookies."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, Request, status

from app.core.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    # bcrypt only uses the first 72 bytes.
    raw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(raw, password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def read_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc


def token_from_request(request: Request) -> str | None:
    cookie = request.cookies.get(settings.cookie_name)
    if cookie:
        return cookie
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return None
