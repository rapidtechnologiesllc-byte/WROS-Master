"""Message Handler: HM Validation Record Creation

Triggers: candidate_matched_to_job message
Purpose: Create HiringManagerValidation record for candidate-to-job match
Output: Validation record with state=PENDING, ready for HM notification
Validation: Ensures validation record created, due date set correctly
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class HMValidationCreatedHandler:
    """Create HM validation record for candidate-to-job match."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=30)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Create HiringManagerValidation record.

        State: PENDING (awaiting HM response)
        Due date: 24 hours from creation
        Next message: queued with 15-minute delay for notification

        Args:
            message: ChannelQueueItem with payload containing:
                - candidate_id: Candidate being matched
                - job_id: Job matched to
                - hiring_manager_id: HM who needs to validate
            db: Database session

        Returns:
            {
                'validation_id': str,
                'hiring_manager_id': str,
                'candidate_id': str,
                'job_id': str,
                'due_at': ISO8601 timestamp,
                'status': 'PENDING'
            }

        Raises:
            ValueError: Invalid payload (non-retryable)
            RuntimeError: Database errors (retryable)
        """
        try:
            if not message.payload:
                raise ValueError(f"Message {message.id} has no payload")

            payload = message.payload
            candidate_id = payload.get('candidate_id')
            job_id = payload.get('job_id')
            hiring_manager_id = payload.get('hiring_manager_id')

            if not all([candidate_id, job_id, hiring_manager_id]):
                raise ValueError(
                    "Missing required fields: candidate_id, job_id, hiring_manager_id"
                )

            logger.info(
                f"[HMValidationCreated] Creating validation: "
                f"candidate={candidate_id}, job={job_id}, hm={hiring_manager_id}"
            )

            # PHASE 1: Verify candidate exists
            from app.models.candidate import Candidate

            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            logger.info(f"[HMValidationCreated] Candidate found: {candidate.candidateEmail}")

            # PHASE 2: Verify job exists
            from app.models.user import Jobs

            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()

            if not job:
                raise ValueError(f"Job {job_id} not found")

            logger.info(f"[HMValidationCreated] Job found: {job.jobTitle}")

            # PHASE 3: Verify hiring manager exists
            from app.models.user import User

            hm = db.query(User).filter(User.id == hiring_manager_id).first()

            if not hm:
                raise ValueError(f"Hiring manager {hiring_manager_id} not found")

            logger.info(f"[HMValidationCreated] HM found: {hm.email}")

            # PHASE 4: Create HiringManagerValidation record
            from app.models.hiring import HiringManagerValidation

            now = datetime.utcnow()
            due_at = now + timedelta(hours=24)  # 24-hour window for HM response

            validation = HiringManagerValidation(
                candidate_id=candidate_id,
                job_id=job_id,
                hiring_manager_id=hiring_manager_id,
                status='PENDING',
                created_at=now,
                due_at=due_at,
                tenant_id=candidate.tenantID if hasattr(candidate, 'tenantID') else None
            )

            db.add(validation)
            db.flush()
            validation_id = validation.id

            logger.info(
                f"[HMValidationCreated] HM validation record created: {validation_id}"
            )

            # PHASE 5: Queue notification message (with 15-minute delay)
            try:
                from app.services.message_queue_service import MessageQueueService

                MessageQueueService.enqueue(
                    task_name='hm_validation_notify',
                    task_id=f"hm_notify_{validation_id}",
                    data={
                        'validation_id': str(validation_id),
                        'candidate_id': str(candidate_id),
                        'job_id': str(job_id),
                        'hiring_manager_id': str(hiring_manager_id)
                    },
                    delay_seconds=900  # 15-minute delay
                )
                logger.info(f"[HMValidationCreated] Queued notification message")

            except Exception as queue_err:
                logger.warning(
                    f"[HMValidationCreated] Failed to queue notification "
                    f"(non-blocking): {queue_err}"
                )

            # PHASE 6: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(
                    f"[HMValidationCreated] Commit failed: {commit_err}",
                    exc_info=True
                )
                raise RuntimeError(
                    f"Failed to create HM validation: {str(commit_err)}"
                ) from commit_err

            logger.info(
                f"[HMValidationCreated] ✅ HM validation created successfully"
            )

            return {
                'validation_id': str(validation_id),
                'hiring_manager_id': str(hiring_manager_id),
                'candidate_id': str(candidate_id),
                'job_id': str(job_id),
                'due_at': due_at.isoformat(),
                'status': 'PENDING'
            }

        except ValueError as ve:
            logger.error(f"[HMValidationCreated] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(
                f"[HMValidationCreated] DB operational error: {oe}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[HMValidationCreated] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that HM validation creation completed successfully."""
        from app.models.hiring import HiringManagerValidation

        if not result or "validation_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        validation_id = result.get("validation_id")

        try:
            validation = db.query(HiringManagerValidation).filter(
                HiringManagerValidation.id == validation_id
            ).first()

            if not validation:
                raise ValueError(f"HM validation {validation_id} not found")

            if validation.status != 'PENDING':
                raise ValueError(
                    f"HM validation {validation_id} status is {validation.status}, "
                    f"expected PENDING"
                )

            if not validation.due_at:
                raise ValueError(f"HM validation {validation_id} due_at not set")

            # Verify due_at is in future
            if validation.due_at <= datetime.utcnow():
                raise ValueError(
                    f"HM validation {validation_id} due_at is in past"
                )

            logger.info(f"✅ HM validation creation validated: {validation_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(
                f"[HMValidationCreated] RETRYABLE validation error: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= HMValidationCreatedHandler.MAX_RETRIES:
            return False
        if hasattr(message, 'next_retry_at') and message.next_retry_at:
            if datetime.utcnow() < message.next_retry_at:
                return False
        return True

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        """Schedule message for retry."""
        try:
            db.rollback()
            message.retry_count += 1
            message.error = error[:1000] if error else "Unknown error"
            message.next_retry_at = datetime.utcnow() + timedelta(
                minutes=HMValidationCreatedHandler.RETRY_DELAY_MINUTES
            )
            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(
                f"[HMValidationCreated] Failed to schedule retry: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            HMValidationCreatedHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err

            logger.info(f"[HMValidationCreated] ✅ Message marked COMPLETED")

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(
                f"[HMValidationCreated] Unexpected error: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries."""
        try:
            db.rollback()
            message.status = "FAILED"
            message.error = final_error[:1000] if final_error else "Unknown error"
            message.completed_at = datetime.utcnow()
            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(
                f"[HMValidationCreated] Failed to mark as FAILED: {e}",
                exc_info=True
            )
            raise
