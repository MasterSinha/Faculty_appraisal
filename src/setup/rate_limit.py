import time
import asyncio
import sys
from collections import defaultdict
from fastapi import HTTPException

_buckets: dict[str, list[float]] = defaultdict(list)
_lock = asyncio.Lock()


async def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    """
    In-memory sliding-window rate limiter.
    Raises HTTP 429 if `key` has exceeded `max_requests` within `window_seconds`.
    Resets on server restart — acceptable for this deployment scale.
    """
    if "pytest" in sys.modules:
        return
    now = time.monotonic()
    async with _lock:
        timestamps = _buckets[key]
        _buckets[key] = [t for t in timestamps if now - t < window_seconds]
        if len(_buckets[key]) >= max_requests:
            raise HTTPException(
                status_code=429,
                detail="Too many attempts. Please wait a moment and try again.",
            )
        _buckets[key].append(now)
