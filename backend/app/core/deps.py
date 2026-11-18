"""Shared FastAPI dependencies."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import read_token, token_from_request
from app.models import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = token_from_request(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
    user_id = read_token(token)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
    return user
