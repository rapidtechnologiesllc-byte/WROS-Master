"""Job Delete Flash Handler - Queue-driven job deletion with cascade cleanup."""
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError
from app.models.user import Jobs
from datetime import datetime

logger = logging.getLogger(__name__)


class JobDeleteFlashHandler:
    """Handles job_deleted_flash queue messages with cascade cleanup."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
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
