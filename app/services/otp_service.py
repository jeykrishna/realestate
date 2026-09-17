"""OTP storage and verification backed by Redis.

Keys:
    otp:{email}          -> hashed 6-digit OTP (TTL = OTP_TTL_SECONDS)
    otp_attempts:{email} -> send counter     (TTL = 900 s / 15 min window)
    otp_fails:{email}    -> verify-fail counter (TTL = 900 s)
"""
import hashlib
from fastapi import HTTPException, status
from app.config import get_settings
from app.utils.redis_client import get_redis

settings = get_settings()

_MAX_VERIFY_FAILS = 5


def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()


async def store_otp(email: str, otp: str) -> None:
    r = await get_redis()

    # Rate limit: max 3 OTP requests per 15-minute window
    attempts_key = f"otp_attempts:{email}"
    attempts = await r.get(attempts_key)
    if attempts and int(attempts) >= 3:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Please wait 15 minutes before trying again.",
        )

    hashed = _hash_otp(otp)
    otp_key = f"otp:{email}"
    await r.setex(otp_key, settings.OTP_TTL_SECONDS, hashed)

    pipe = r.pipeline()
    await pipe.incr(attempts_key)
    await pipe.expire(attempts_key, 900)
    await pipe.execute()


async def verify_otp_code(email: str, otp: str) -> bool:
    r = await get_redis()
    fail_key = f"otp_fails:{email}"

    # Block after too many failed attempts
    fails = await r.get(fail_key)
    if fails and int(fails) >= _MAX_VERIFY_FAILS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Please request a new OTP.",
        )

    otp_key = f"otp:{email}"
    stored_hash = await r.get(otp_key)

    if not stored_hash:
        return False

    if _hash_otp(otp) != stored_hash:
        # Increment fail counter
        pipe = r.pipeline()
        await pipe.incr(fail_key)
        await pipe.expire(fail_key, 900)
        await pipe.execute()
        return False

    # Single-use: delete OTP and clear counters on success
    await r.delete(otp_key, f"otp_attempts:{email}", fail_key)
    return True
