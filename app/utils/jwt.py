import uuid
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError

from app.config import get_settings

settings = get_settings()


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload["jti"] = uuid.uuid4().hex  # unique ID used for blocklist on logout
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except InvalidTokenError:
        return None


async def add_to_blocklist(jti: str, exp: int) -> None:
    """Add a JWT jti to Redis blocklist with TTL equal to remaining token lifetime."""
    from app.utils.redis_client import get_redis

    r = await get_redis()
    remaining = int(exp - datetime.now(timezone.utc).timestamp())
    if remaining > 0:
        await r.setex(f"blocklist:{jti}", remaining, "1")


async def is_blocklisted(jti: str) -> bool:
    from app.utils.redis_client import get_redis

    r = await get_redis()
    return await r.exists(f"blocklist:{jti}") == 1
