"""Lightweight in-memory sliding-window rate limiter.

No Redis or external dependency. Suitable for single-process deployments
(Uvicorn with --workers 1, which is the current AHONIX setup).

Usage as a FastAPI dependency:
    from rate_limit import make_rate_limiter
    login_limiter = make_rate_limiter(max_calls=10, window_seconds=60, scope="login")

    @router.post("/login")
    async def login(request: Request, _rl=Depends(login_limiter)):
        ...
"""

import time
import threading
from collections import defaultdict
from fastapi import Request, HTTPException

_lock = threading.Lock()
_buckets: dict[str, list[float]] = defaultdict(list)

# Periodic cleanup counter — avoids scanning on every request.
_call_count = 0
_CLEANUP_EVERY = 200


def _cleanup(window: int):
    """Remove timestamps older than the largest reasonable window."""
    cutoff = time.monotonic() - window - 60
    keys_to_delete = []
    for key, timestamps in _buckets.items():
        _buckets[key] = [t for t in timestamps if t > cutoff]
        if not _buckets[key]:
            keys_to_delete.append(key)
    for key in keys_to_delete:
        del _buckets[key]


def _get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For behind a proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(key: str, max_calls: int, window_seconds: int) -> None:
    """Check and record an access.  Raises HTTPException(429) if limit exceeded."""
    global _call_count
    now = time.monotonic()
    cutoff = now - window_seconds

    with _lock:
        _call_count += 1
        if _call_count % _CLEANUP_EVERY == 0:
            _cleanup(window_seconds)

        timestamps = _buckets[key]
        # Prune expired entries for this key.
        _buckets[key] = [t for t in timestamps if t > cutoff]
        timestamps = _buckets[key]

        if len(timestamps) >= max_calls:
            retry_after = int(timestamps[0] - cutoff) + 1
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please slow down.",
                headers={"Retry-After": str(max(retry_after, 1))},
            )
        timestamps.append(now)


def make_rate_limiter(max_calls: int, window_seconds: int, scope: str):
    """Return a FastAPI dependency that enforces per-IP rate limiting.

    Args:
        max_calls: Maximum allowed requests within the window.
        window_seconds: Sliding window size in seconds.
        scope: A label that namespaces the bucket (e.g. "login", "ask").
    """

    async def _limiter(request: Request):
        ip = _get_client_ip(request)
        key = f"{scope}:{ip}"
        check_rate_limit(key, max_calls, window_seconds)

    return _limiter
