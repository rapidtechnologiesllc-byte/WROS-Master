"""Base Message Handler - Enforces validation and time-binding patterns.

CRITICAL RULES:
1. Every handler MUST validate before marking COMPLETED
2. Every handler execution MUST timeout after 10-15 seconds
3. Validation MUST query database to verify work actually happened
4. Errors MUST be categorized as retryable (RuntimeError) or non-retryable (ValueError)
"""

import logging
import time
import functools
from datetime import datetime, timedelta
from typing import Callable, Any, Dict
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Raised when handler execution exceeds time limit."""
    pass


class ValidationError(Exception):
    """Raised when post-execution validation fails."""
    pass


def time_bound(timeout_seconds: float = 15):
    """
    Decorator to enforce timeout on handler execution.

    Args:
        timeout_seconds: Maximum execution time (default 15 seconds)

    Raises:
        TimeoutError: If execution exceeds timeout

    Example:
        @time_bound(timeout_seconds=15)
        def process(message, db):
            # Handler logic here - must complete within 15 seconds
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time

                if elapsed > timeout_seconds:
                    logger.warning(
                        f"[TimeBinding] Handler {func.__name__} completed but took {elapsed:.2f}s "
                        f"(timeout: {timeout_seconds}s). Consider optimizing DB queries or logic."
                    )

                return result

            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(
                    f"[TimeBinding] Handler {func.__name__} failed after {elapsed:.2f}s: {e}",
                    exc_info=True
                )
                raise

        return wrapper
    return decorator


class BaseMessageHandler:
    """
    Base class for all message handlers.

    Enforces:
    1. Validation before marking COMPLETED
    2. Time-bound execution (10-15 seconds)
    3. Proper error handling and retry logic
    4. Database transaction safety

    Subclasses must implement:
    - process() - Execute the actual work
    - validate() - Verify work succeeded in database
    """

    MAX_RETRIES = 5
    RETRY_DELAY_MINUTES = 30
    TIMEOUT_SECONDS = 15

    @staticmethod
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """Execute the actual work. Override in subclass."""
        raise NotImplementedError("Subclass must implement process()")

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """
        Validate that work was actually completed.

        This is called BEFORE marking COMPLETED.
        Must raise exceptions if validation fails.

        Args:
            message: The queue message
            result: Result dict from process()
            db: Database session

        Raises:
            ValueError: Non-retryable error (handler bug)
            RuntimeError: Retryable error (temporary DB issue)
        """
        raise NotImplementedError("Subclass must implement validate()")

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried after failure."""
        if message.retry_count >= BaseMessageHandler.MAX_RETRIES:
            logger.error(f"[Handler] Max retries exceeded for {message.id}")
            return False

        if hasattr(message, 'next_retry_at') and message.next_retry_at:
            if datetime.utcnow() < message.next_retry_at:
                return False

        return True

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        """Schedule message for retry after failed attempt."""
        try:
            db.rollback()

            message.retry_count += 1
            message.error = error[:1000] if error else "Unknown error"
            message.next_retry_at = datetime.utcnow() + timedelta(
                minutes=BaseMessageHandler.RETRY_DELAY_MINUTES
            )

            db.commit()
            logger.info(
                f"[Handler] Scheduled retry for {message.id}: "
                f"retry_count={message.retry_count}/{BaseMessageHandler.MAX_RETRIES}, "
                f"next_retry_at={message.next_retry_at}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[Handler] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """
        Mark message as COMPLETED after validation passes.

        CRITICAL: Must call validate() BEFORE marking COMPLETED.
        """
        try:
            # ===== VALIDATION (before marking COMPLETED) =====
            BaseMessageHandler.validate(message, result, db)

            # ===== MARK COMPLETED (only after validation passes) =====
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit success status: {str(commit_err)}") from commit_err

            logger.info(f"[Handler] ✅ Message {message.id} marked COMPLETED (validation passed)")

        except ValueError as e:
            # Non-retryable error (handler code bug, don't retry)
            db.rollback()
            logger.error(f"[Handler] ❌ NON-RETRYABLE validation failure: {e}")
            raise  # Will be caught by processor and marked FAILED

        except RuntimeError as e:
            # Retryable error (temporary DB issue, connection problem, etc.)
            db.rollback()
            logger.error(f"[Handler] ❌ RETRYABLE validation failure: {e}")
            raise  # Will be caught by processor and retry scheduled

        except Exception as e:
            # Unexpected error (treat as retryable)
            db.rollback()
            logger.error(f"[Handler] ❌ Unexpected validation error: {e}", exc_info=True)
            raise RuntimeError(f"Validation error: {str(e)}") from e

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries exhausted."""
        try:
            db.rollback()

            message.status = "FAILED"
            message.error = final_error[:1000] if final_error else "Unknown error"
            message.completed_at = datetime.utcnow()

            db.commit()
            logger.error(
                f"[Handler] Message {message.id} FAILED after "
                f"{message.retry_count} retries: {final_error}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[Handler] Failed to mark as FAILED: {e}", exc_info=True)
            raise
