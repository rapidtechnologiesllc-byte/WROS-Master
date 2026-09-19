"""Rate limiting decorator for critical endpoints."""
import time
from functools import wraps
from fastapi import HTTPException

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
