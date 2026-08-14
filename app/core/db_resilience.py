"""
Database resilience utilities for handling SQLite locks.
Production: Replace with PostgreSQL connection pooling.
"""
import time
import logging
from functools import wraps
from typing import Callable, TypeVar, Any
from sqlalchemy.exc import OperationalError
from sqlalchemy import event
from sqlalchemy.pool import Pool

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_on_db_lock(max_retries: int = 5, initial_wait: float = 0.05) -> Callable:
    """
    Retry decorator for database operations that fail due to locks.
    Uses exponential backoff: 50ms, 100ms, 200ms, 400ms, 800ms
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            wait_time = initial_wait
            last_error = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    last_error = e
                    error_str = str(e).lower()

                    # Retry on database lock errors
                    if "database is locked" in error_str:
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"[DB] Database locked (attempt {attempt + 1}/{max_retries}), "
                                f"retrying in {wait_time:.2f}s..."
                            )
                            time.sleep(wait_time)
                            wait_time *= 2  # Exponential backoff
                            continue
                        else:
                            logger.error(f"[DB] Database lock persisted after {max_retries} retries")

                    # Don't retry on other errors
                    raise

            # If we get here, all retries failed
            if last_error:
                raise last_error

        return wrapper
    return decorator


def configure_sqlite_for_concurrency(engine) -> None:
    """
    Configure SQLite connection for better concurrent access.
    Note: This is a workaround. Production should use PostgreSQL.
    """
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()

        # Enable Write-Ahead Logging for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")

        # Synchronous mode: NORMAL is safer than OFF but faster than FULL
        cursor.execute("PRAGMA synchronous=NORMAL")

        # Lock timeout: 5 seconds before giving up
        cursor.execute("PRAGMA busy_timeout=5000")

        # Cache size: reduce memory usage
        cursor.execute("PRAGMA cache_size=10000")

        # Foreign keys: important for data integrity
        cursor.execute("PRAGMA foreign_keys=ON")

        cursor.close()

        logger.info("[DB] SQLite pragmas configured for concurrency")
