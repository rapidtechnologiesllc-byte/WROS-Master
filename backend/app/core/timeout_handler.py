"""Handler timeout enforcement with threading wrapper.

Prevents queue handlers from hanging indefinitely on slow database operations.
Raises RuntimeError if handler exceeds timeout threshold.
"""

import functools
import threading
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Handler exceeded timeout threshold."""
    pass


def timeout_handler(seconds: int = 30):
    """
    Decorator that enforces timeout on queue handler functions.

    Args:
        seconds: Timeout in seconds (default 30)

    Raises:
        RuntimeError: If handler exceeds timeout

    Usage:
        @timeout_handler(30)
        def handle_candidate_creation(message):
            # This will timeout after 30 seconds
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            result = [None]
            exception = [None]

            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e

            # Start handler in thread with timeout
            thread = threading.Thread(target=target, daemon=False)
            thread.start()
            thread.join(timeout=seconds)

            # Check if thread is still alive (timeout occurred)
            if thread.is_alive():
                logger.error(
                    f"[TIMEOUT] Handler {func.__name__} exceeded {seconds}s timeout. "
                    f"Thread still running, marking as failed."
                )
                raise RuntimeError(
                    f"Handler {func.__name__} exceeded {seconds}s timeout"
                )

            # If exception occurred in thread, re-raise it
            if exception[0]:
                raise exception[0]

            return result[0]

        return wrapper
    return decorator
