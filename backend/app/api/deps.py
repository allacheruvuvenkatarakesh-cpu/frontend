"""Shared FastAPI dependencies."""
import time
from collections import defaultdict, deque

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AppError, AuthError
from app.core.security import decode_token
from app.db import mongo

bearer = HTTPBearer(auto_error=False)


async def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not creds:
        raise AuthError("Not authenticated")
    data = decode_token(creds.credentials, "access")
    user = await mongo.get_db()[mongo.USERS].find_one({"_id": data["sub"]})
    if not user:
        raise AuthError("User no longer exists")
    return user


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"


class RateLimiter:
    """Simple in-memory sliding window per key. Use Redis for multi-instance deployments."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit, self.window = limit, window_seconds
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            raise RateLimitError(f"Too many requests. Try again in {int(self.window - (now - q[0])) + 1}s")
        q.append(now)


analysis_limiter = RateLimiter(limit=10, window_seconds=3600)
login_limiter = RateLimiter(limit=10, window_seconds=300)
