"""Job Delete Flash Handler - Queue-driven job deletion with cascade cleanup."""
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError
from app.models.user import Jobs
from datetime import datetime, timedelta
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class JobDeleteFlashHandler:
    """Handles job_deleted_flash queue messages with cascade cleanup."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=15)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process: Delete job and cascade cleanup from queue message

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

            # PHASE 2: QUERY (Verify job exists)
            try:
                job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
                if not job:
                    raise ValueError(f"Job not found: {job_id}")

            except ValueError:
                raise  # Re-raise ValueError as-is (not retryable)
            except Exception as e:
                raise RuntimeError(f"Failed to query job {job_id}: {str(e)}") from e

            # PHASE 3: CASCADE CLEANUP (Count and delete rows in FK order)
            cascade_summary = []

            try:
                # Cleanup 1: CandidateJobApplication
                from app.models.user import CandidateJobApplication
                cja_count = db.query(CandidateJobApplication).filter(
                    CandidateJobApplication.job_id == job_id
                ).count()
                if cja_count > 0:
                    db.query(CandidateJobApplication).filter(
                        CandidateJobApplication.job_id == job_id
                    ).delete()
                    cascade_summary.append(f"CandidateJobApplication: {cja_count} rows")
                    logger.info(f"[JobDeleteFlash] Cleaned {cja_count} CandidateJobApplication rows for {job_id}")

                # Cleanup 2: Interview
                from app.models.user import Interview
                interview_count = db.query(Interview).filter(
                    Interview.job_id == job_id
                ).count()
                if interview_count > 0:
                    db.query(Interview).filter(
                        Interview.job_id == job_id
                    ).delete()
                    cascade_summary.append(f"Interview: {interview_count} rows")
                    logger.info(f"[JobDeleteFlash] Cleaned {interview_count} Interview rows for {job_id}")

                # Cleanup 3: InterviewPanel (if table exists)
                try:
                    from app.models.user import InterviewPanel
                    panel_count = db.query(InterviewPanel).filter(
                        InterviewPanel.job_id == job_id
                    ).count()
                    if panel_count > 0:
                        db.query(InterviewPanel).filter(
                            InterviewPanel.job_id == job_id
                        ).delete()
                        cascade_summary.append(f"InterviewPanel: {panel_count} rows")
                        logger.info(f"[JobDeleteFlash] Cleaned {panel_count} InterviewPanel rows for {job_id}")
                except Exception as e:
                    logger.warning(f"[JobDeleteFlash] Could not cleanup InterviewPanel (may not exist): {e}")

                # Cleanup 4: CandidateAssignment (if job_id column exists)
                try:
                    from app.models.user import CandidateAssignment
                    assign_count = db.query(CandidateAssignment).filter(
                        CandidateAssignment.job_id == job_id
                    ).count()
                    if assign_count > 0:
                        db.query(CandidateAssignment).filter(
                            CandidateAssignment.job_id == job_id
                        ).delete()
                        cascade_summary.append(f"CandidateAssignment: {assign_count} rows")
                        logger.info(f"[JobDeleteFlash] Cleaned {assign_count} CandidateAssignment rows for {job_id}")
                except Exception as e:
                    logger.warning(f"[JobDeleteFlash] Could not cleanup CandidateAssignment (may not exist): {e}")

            except IntegrityError as e:
                db.rollback()
                logger.error(f"[JobDeleteFlash] FK constraint during cascade cleanup for {job_id}: {e}", exc_info=True)
                raise RuntimeError(f"Cascade cleanup FK constraint: {str(e)}") from e

            # PHASE 4: DELETE JOB RECORD
            try:
                db.delete(job)
                db.flush()

                # PHASE 5: NEIGHBOR MONITORING (Verify deletion persisted)
                persisted_job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
                if persisted_job:
                    raise RuntimeError(f"Write validation failed: job still exists after delete")

                db.commit()
                logger.info(f"[JobDeleteFlash] ✅ Deleted job {job_id}, cascade cleanup: {cascade_summary}")

                return {
                    'status': 'success',
                    'job_id': job_id,
                    'deleted_at': datetime.utcnow().isoformat(),
                    'cascade_tables_cleaned': cascade_summary
                }

            except IntegrityError as e:
                db.rollback()
                logger.error(f"[JobDeleteFlash] FK constraint deleting job {job_id}: {e}", exc_info=True)
                raise RuntimeError(f"Cannot delete job (FK constraint): {str(e)}") from e

            except OperationalError as e:
                db.rollback()
                logger.error(f"[JobDeleteFlash] DB operational error for {job_id}: {e}", exc_info=True)
                raise RuntimeError(f"DB unavailable: {str(e)}") from e

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

            logger.info(f"[Handler] ✅ Step 2: Database verification passed, job properly deleted")

            # ===== FINAL: Mark COMPLETED after all validations pass =====
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit success status: {str(commit_err)}") from commit_err

            logger.info(f"[Handler] ✅✅✅ ALL VALIDATIONS PASSED - Message marked COMPLETED")

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
