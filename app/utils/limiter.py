"""Global slowapi rate-limiter instance shared across all routers."""
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.config import get_settings

settings = get_settings()


def _real_client_ip(request: Request) -> str:
    """Resolve the true client IP for rate-limit keying.

    Behind the nginx reverse proxy every request's socket address is
    127.0.0.1, which would lump all clients into one bucket. nginx sets
    X-Real-IP to $remote_addr (the real TCP peer) and OVERWRITES any
    client-supplied value, so it can't be spoofed — prefer it. Fall back to
    the last X-Forwarded-For hop (also appended by nginx) and finally the
    socket address for direct, non-proxied hits.
    """
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Last entry is the hop nginx appended (the real peer); leading
        # entries are client-controllable and must not be trusted.
        return forwarded.split(",")[-1].strip()
    return get_remote_address(request)


# Redis-backed storage so limit counters are shared across workers and survive
# process restarts (the same Redis already used for OTP/JWT-blocklist).
# default_limits applies a generous global per-IP cap to every route, including
# public reads (property listing/search, cities) that carry no explicit
# decorator — protection against scraping / abuse.
limiter = Limiter(
    key_func=_real_client_ip,
    storage_uri=settings.REDIS_URL,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
)
