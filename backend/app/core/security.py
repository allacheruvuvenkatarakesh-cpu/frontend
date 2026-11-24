"""Password hashing and JWT helpers."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.exceptions import AuthError


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _encode(payload: dict, minutes: int) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {**payload, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)


def create_access_token(user_id: str) -> str:
    return _encode({"sub": user_id, "typ": "access"}, get_settings().JWT_EXPIRE_MINUTES)


def create_media_token(user_id: str, video_id: str) -> str:
    """Short-lived token scoped to one video, usable in <video src="...?token=">
    (browsers cannot attach Authorization headers to media elements)."""
    return _encode({"sub": user_id, "vid": video_id, "typ": "media"}, get_settings().MEDIA_TOKEN_EXPIRE_MINUTES)


def decode_token(token: str, expected_type: str) -> dict:
    s = get_settings()
    try:
        data = jwt.decode(token, s.JWT_SECRET, algorithms=[s.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise AuthError("Token expired") from e
    except jwt.PyJWTError as e:
        raise AuthError("Invalid token") from e
    if data.get("typ") != expected_type:
        raise AuthError("Wrong token type")
    return data
