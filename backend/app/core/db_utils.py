"""Database utilities: transaction management, retry logic, and error handling.

Provides:
- Retry decorator with exponential backoff
- Transaction isolation configuration
- Connection pool management
"""

import time
import logging
from functools import wraps
from sqlalchemy.exc import OperationalError, IntegrityError

logger = logging.getLogger(__name__)


def retry_on_db_lock(max_retries=3, initial_wait=0.1):
    """Retry decorator for operations that might hit database locks.

    Uses exponential backoff: 0.1s, 0.2s, 0.4s

    Args:
        max_retries: Maximum number of retry attempts (default 3)
        initial_wait: Starting wait time in seconds (default 0.1)

    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            wait = initial_wait
            last_error = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    last_error = e
                    error_msg = str(e).lower()

                    if "database is locked" in error_msg or "deadlock" in error_msg:
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"Database lock in {func.__name__}, "
                                f"retry {attempt + 1}/{max_retries} after {wait}s"
                            )
                            time.sleep(wait)
                            wait *= 2
                            continue

                    raise
                except IntegrityError as e:
                    logger.error(f"Integrity error in {func.__name__}: {e}")
                    raise

            if last_error:
                raise last_error

        return wrapper
    return decorator


def retry_on_connection_error(max_retries=3, initial_wait=0.5):
    """Retry decorator for connection-related errors.

    Uses exponential backoff for transient connection failures.

    Args:
        max_retries: Maximum number of retry attempts
        initial_wait: Starting wait time in seconds

    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            wait = initial_wait
            last_error = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, ConnectionError) as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Connection error in {func.__name__}, "
                            f"retry {attempt + 1}/{max_retries} after {wait}s: {e}"
                        )
                        time.sleep(wait)
                        wait *= 2
                        continue
                    raise

            if last_error:
                raise last_error

        return wrapper
    return decorator
