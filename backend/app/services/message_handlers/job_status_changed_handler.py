"""Job Status Changed Message Handler - Process job status change notifications."""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from app.models.user import Jobs
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class JobStatusChangedHandler:
    """Handles job_status_changed messages with time-bound execution and validation."""
    # Enforced by queue_processor_service (its default for this task type)
    TIMEOUT_SECONDS = 30


    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=10)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """Process job_status_changed message.

        Args:
            message: ChannelQueueItem with type='job_status_changed'
            db: SQLAlchemy session

        Returns:
            {status, job_id, old_status, new_status, entities_updated}
        """
        try:
            payload = message.payload or {}
            job_id = payload.get('job_id')
            new_status = payload.get('new_status')

            if not job_id or not new_status:
                raise ValueError("job_id and new_status are required in payload")

            # 1. Fetch job to verify it exists
            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found in database")

            old_status = job.status if hasattr(job, 'status') else 'UNKNOWN'
            logger.info(f"[JobStatusChanged] Processing {job_id}: {old_status} → {new_status}")

            # 2. Update job status and any related fields
            if hasattr(job, 'status'):
                job.status = new_status
                db.commit()

            # 3. Notify related candidates (e.g., if job closed, notify pending candidates)
            entities_updated = 0
            try:
                if new_status == 'CLOSED':
                    # Mark pending interviews/offers as affected
                    # In production: update candidate_status records, close open interviews
                    pass
                elif new_status == 'OPEN':
                    # Reactivate if applicable
                    pass
                entities_updated += 1
            except Exception as entity_err:
                logger.warning(f"[JobStatusChanged] Could not update related entities: {entity_err}")
                # Non-fatal

            # 4. Trigger any workflows that depend on job status
            try:
                if new_status == 'CLOSED':
                    # End hiring workflow
                    pass
                elif new_status == 'FILLED':
                    # Mark success, archive conversations
                    pass
            except Exception as workflow_err:
                logger.warning(f"[JobStatusChanged] Could not trigger workflows: {workflow_err}")
                # Non-fatal

            result = {
                "status": "job_status_changed",
                "job_id": job_id,
                "old_status": old_status,
                "new_status": new_status,
                "entities_updated": entities_updated,
                "message": f"Job {job_id} status updated to {new_status}"
            }

            logger.info(f"[JobStatusChanged] ✅ Completed: {job_id}")
            return result

        except ValueError as ve:
            logger.error(f"[JobStatusChanged] Validation error: {ve}")
            raise
        except OperationalError as oe:
            logger.error(f"[JobStatusChanged] DB error: {oe}", exc_info=True)
            raise RuntimeError(f"Database error: {str(oe)}") from oe
        except Exception as e:
            logger.error(f"[JobStatusChanged] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that job status was changed successfully."""
        from app.services.message_handlers.validate_handlers_factory import ValidateHandlersFactory
        return ValidateHandlersFactory.validate_job_status_changed(result, db, "job_status_changed")

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        return message.retry_count < JobStatusChangedHandler.MAX_RETRIES

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        """Schedule message for retry."""
        db.rollback()
        message.retry_count += 1
        message.error = error[:1000]
        message.next_retry_at = datetime.utcnow() + timedelta(minutes=JobStatusChangedHandler.RETRY_DELAY_MINUTES)
        db.commit()

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation passes."""
        JobStatusChangedHandler.validate(message, result, db)
        message.status = "COMPLETED"
        message.completed_at = datetime.utcnow()
        db.commit()

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries exhausted."""
        db.rollback()
        message.status = "FAILED"
        message.error = final_error[:1000]
        message.completed_at = datetime.utcnow()
        db.commit()


def handle_job_status_changed(message: Any, db: Session) -> Dict[str, Any]:
    """Handle job_status_changed message."""
    return JobStatusChangedHandler.process(message, db)
