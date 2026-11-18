"""Small in-memory rate limiter for login and the assistant."""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

_hits: dict[str, list[float]] = defaultdict(list)


def enforce_rate_limit(request: Request, key: str, limit: int, window_seconds: int = 60) -> None:
    if get_settings().testing:
        return
    now = time.time()
    ip = request.client.host if request.client else "unknown"
    bucket = f"{key}:{ip}"
    recent = [stamp for stamp in _hits[bucket] if now - stamp < window_seconds]
    if len(recent) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Wait a minute and try again.",
        )
    recent.append(now)
    _hits[bucket] = recent
