"""Rate limiting decorator for critical endpoints."""
import threading
import time
from collections import deque
from functools import wraps

from fastapi import HTTPException, Request

# In-memory rate limit store: {key: (count, reset_time)}
_rate_limits = {}

def rate_limit(requests_per_minute: int):
    """Decorator to rate limit endpoints by requests per minute."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            key = f"{func.__name__}"
            now = time.time()
            minute_ago = now - 60

            if key not in _rate_limits:
                _rate_limits[key] = (0, now)

            count, reset_time = _rate_limits[key]

            # Reset counter if minute has passed
            if reset_time < minute_ago:
                _rate_limits[key] = (1, now)
            elif count >= requests_per_minute:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {requests_per_minute} requests per minute"
                )
            else:
                _rate_limits[key] = (count + 1, reset_time)

            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            key = f"{func.__name__}"
            now = time.time()
            minute_ago = now - 60

            if key not in _rate_limits:
                _rate_limits[key] = (0, now)

            count, reset_time = _rate_limits[key]

            if reset_time < minute_ago:
                _rate_limits[key] = (1, now)
            elif count >= requests_per_minute:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {requests_per_minute} requests per minute"
                )
            else:
                _rate_limits[key] = (count + 1, reset_time)

            return func(*args, **kwargs)

        # Return the appropriate wrapper
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ---- per-IP limit for unauthenticated public endpoints ---------------------------------------
# Public routes (no login: client timesheet approval links, the careers chat) are limited per
# client IP and per endpoint group to settings.PUBLIC_ENDPOINT_RATE_LIMIT_PER_MINUTE requests in
# a sliding minute. In-process: each worker counts its own requests, which bounds abuse per worker.
_public_hits = {}
_public_lock = threading.Lock()
PUBLIC_WINDOW_SECONDS = 60


def public_rate_limit(bucket: str):
    """FastAPI dependency: 429 once this IP made more than the per-minute allowance on `bucket`."""

    def dependency(request: Request) -> None:
        from app.core.config import settings

        limit = settings.PUBLIC_ENDPOINT_RATE_LIMIT_PER_MINUTE
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        with _public_lock:
            hits = _public_hits.setdefault((bucket, ip), deque())
            while hits and hits[0] <= now - PUBLIC_WINDOW_SECONDS:
                hits.popleft()
            if len(hits) >= limit:
                raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute and try again.")
            hits.append(now)

    return dependency


def reset_public_rate_limits() -> None:
    with _public_lock:
        _public_hits.clear()
