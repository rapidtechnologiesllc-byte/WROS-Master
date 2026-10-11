"""Job Delete Flash Handler: confirms a job deletion for Flash. Nothing is cascaded -- a job
with history cannot be deleted at all (app.services.job_lifecycle_service)."""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.user import Jobs
from datetime import datetime, timedelta
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class JobDeleteFlashHandler:
    """Confirms job_deleted_flash events (the endpoint already deleted the job)."""

    TIMEOUT_SECONDS = 45
    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=15)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process: confirm the job is gone

        Args:
            message: ChannelQueueItem with type='job_deleted_flash'
            db: SQLAlchemy session

        Returns:
            {
                'status': 'success',
                'job_id': str,
                'deleted_at': ISO timestamp,
                'cascade_tables_cleaned': [
                    'CandidateJobApplication: 5 rows',
                    'Interview: 2 rows',
                    ...
                ]
            }

        Raises:
            ValueError: Job not found (400, NOT retryable)
            RuntimeError: FK constraint violations or commit failure (500, retryable)

        Payload Schema:
        {
            'job_id': str (required, must exist)
        }

        Cascade Cleanup Order (FK safety):
        1. CandidateJobApplication (job_id FK)
        2. Interview (job_id FK)
        3. InterviewPanel (job_id FK, if present)
        4. CandidateAssignment (job_id FK, if present)
        5. Jobs record (primary)
        """
        try:
            payload = message.payload or {}

            # PHASE 1: VALIDATION
            job_id = payload.get('job_id')
            if not job_id:
                raise ValueError("Missing required field: job_id")

            # The endpoint deleted the job (only possible when nothing refers to it --
            # job_lifecycle_service.assert_deletable); this event only confirms it for Flash.
            if db.query(Jobs).filter(Jobs.jobID == job_id).first() is not None:
                raise ValueError(f"Job {job_id} still exists: a delete event for a job that was not deleted")
            logger.info(f"[JobDeleteFlash] Job {job_id} deletion confirmed")
            return {'status': 'success', 'job_id': job_id, 'confirmed_at': datetime.utcnow().isoformat()}

        except ValueError as ve:
            logger.error(f"[JobDeleteFlash] Validation error: {ve}")
            raise  # NOT RETRYABLE

        except RuntimeError as re:
            logger.error(f"[JobDeleteFlash] Runtime error (retryable): {re}")
            raise  # RETRYABLE

        except Exception as e:
            db.rollback()
            logger.error(f"[JobDeleteFlash] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= JobDeleteFlashHandler.MAX_RETRIES:
            logger.error(f"[JobDeleteFlash] Max retries exceeded for {message.id}")
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
                minutes=JobDeleteFlashHandler.RETRY_DELAY_MINUTES
            )

            db.commit()
            logger.info(
                f"[JobDeleteFlash] Scheduled retry for {message.id}: "
                f"retry_count={message.retry_count}/{JobDeleteFlashHandler.MAX_RETRIES}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[JobDeleteFlash] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that job deletion actually completed successfully."""
        if not result or "job_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        job_id = result.get("job_id")

        try:
            # For delete operations, validation is inverse: job should NOT exist
            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            if job:
                raise ValueError(f"Job {job_id} still exists after delete (deletion failed)")

            logger.info(f"✅ Job deletion validated: {job_id} successfully deleted")

        except ValueError as e:
            logger.error(f"[JobDeleteFlash] NON-RETRYABLE validation error: {e}")
            raise

        except Exception as e:
            logger.error(f"[JobDeleteFlash] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database validation error: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Handle successful message processing with validation before marking COMPLETED."""
        try:
            # ===== VALIDATION STEP 1: Check result structure =====
            if not isinstance(result, dict):
                raise ValueError(f"Handler returned invalid type: {type(result)}")

            required_fields = ['job_id', 'status', 'deleted_at']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Handler result missing required field: {field}")
                if not result[field]:
                    raise ValueError(f"Handler result has empty field: {field}")

            job_id = result['job_id']
            logger.info(f"[Handler] ✅ Step 1: Result structure valid (job_id={job_id})")

            # ===== VALIDATION STEP 2: Database verification - job should NOT exist =====
            # This is a deletion handler, so job should be deleted
            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()

            if job:
                raise RuntimeError(
                    f"Record {job_id} still exists in database after deletion. "
                    f"Handler claimed to delete but record persists."
                )

            logger.info("[Handler] ✅ Step 2: Database verification passed, job properly deleted")

            # ===== FINAL: Mark COMPLETED after all validations pass =====
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit success status: {str(commit_err)}") from commit_err

            logger.info("[Handler] ✅✅✅ ALL VALIDATIONS PASSED - Message marked COMPLETED")

        except ValueError as e:
            # Non-retryable error
            db.rollback()
            logger.error(f"[Handler] ❌ NON-RETRYABLE validation failure: {e}")
            raise

        except RuntimeError as e:
            # Retryable error
            db.rollback()
            logger.error(f"[Handler] ❌ RETRYABLE validation failure: {e}")
            raise

        except Exception as e:
            # Unexpected error
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
                f"[JobDeleteFlash] Message {message.id} FAILED after "
                f"{message.retry_count} retries: {final_error}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[JobDeleteFlash] Failed to mark as FAILED: {e}", exc_info=True)
            raise
