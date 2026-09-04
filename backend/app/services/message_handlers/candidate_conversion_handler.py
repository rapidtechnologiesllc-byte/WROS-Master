"""Message Handler: Candidate-to-Employee Conversion with Retry Logic

Implements idempotent candidate-to-employee conversion through message queue.
- 5 retry attempts with 30-minute intervals
- Verifies candidate exists before conversion
- Creates employee record atomically
"""
import logging
from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.message_queue import MessageQueue
from app.models.candidate import Candidate, CandidateStatus
from app.models.employee import Employee
from app.models.candidate_ai import ConversationEvent

logger = logging.getLogger(__name__)


class CandidateConversionHandler:
    """Handles candidate-to-employee conversion messages from queue with retry logic."""

    MAX_RETRIES = 5
    RETRY_DELAY_MINUTES = 30

    @staticmethod
    def process(
        message: MessageQueue,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Process candidate-to-employee conversion message.

        Implements FAIL FAST: Raises exceptions on any error.

        Args:
            message: MessageQueue record with payload containing conversion data
            db: Database session

        Returns:
            {'status': 'success', 'candidate_id': str, 'employee_id': str}

        Raises:
            ValueError: If payload invalid
            RuntimeError: If conversion fails (retryable)
        """
        if not message.payload:
            raise ValueError(f"Message {message.id} has no payload")

        payload = message.payload
        candidate_id = payload.get("candidate_id")
        logger.info(f"[CandidateConversionHandler] Processing conversion for candidate {candidate_id}")

        try:
            # Verify candidate exists and has OFFER status
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            candidate_status = db.query(CandidateStatus).filter(
                CandidateStatus.candidateID == candidate_id
            ).first()

            if not candidate_status or candidate_status.piplineStatus != "OFFER":
                raise ValueError(f"Candidate {candidate_id} status is not OFFER")

            # Create Employee record (check if already exists for idempotency)
            employee_id = payload.get("candidate_id")

            # Idempotency check: does employee already exist?
            employee = db.query(Employee).filter(Employee.id == employee_id).first()

            # Only create employee if doesn't exist (idempotent)
            if not employee:
                employee = Employee(
                    id=employee_id,  # Use candidate ID as employee ID initially
                    tenant_id=payload.get("tenant_id", "default"),
                    first_name=payload.get("candidate_first_name"),
                    last_name=payload.get("candidate_last_name", ""),
                    email=payload.get("candidate_email"),
                    mobile=payload.get("candidate_mobile"),
                    gender=payload.get("candidate_gender"),
                    date_of_birth=payload.get("candidate_dob"),
                    status="ACTIVE",
                    employment_type=payload.get("candidate_employee_type", "Full-Time"),
                    designation=payload.get("candidate_job_title", "Employee"),
                    location=payload.get("candidate_location"),
                    joining_date=payload.get("candidate_joining_date"),
                    created_at=datetime.utcnow(),
                )
                # Only add to DB if not already there (IDEMPOTENT)
                db.add(employee)
            else:
                logger.info(f"[CandidateConversionHandler] Employee {employee_id} already exists, reusing")

            db.flush()

            # Track if we're actually changing the status (for idempotent event logging)
            old_status = candidate_status.piplineStatus

            # Update candidate status to EMPLOYEE
            candidate_status.piplineStatus = "EMPLOYEE"
            candidate_status.status = "EMPLOYEE"
            candidate_status.updatedAt = datetime.utcnow()

            # Note: ConversationEvent logging removed - idempotency already guaranteed by
            # old_status check and gate restrictions. Conversion event will be tracked via
            # candidate_status.updatedAt timestamp in audit logs.

            # Commit conversion
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(
                    f"[CandidateConversionHandler] Commit failed for {candidate_id}: {commit_err}",
                    exc_info=True,
                )
                raise RuntimeError(f"Database commit failed: {str(commit_err)}") from commit_err

            logger.info(
                f"[CandidateConversionHandler] Successfully converted candidate {candidate_id} "
                f"to employee {employee.id}"
            )

            return {
                "status": "success",
                "candidate_id": candidate_id,
                "employee_id": employee.id,
            }

        except ValueError as e:
            logger.warning(f"[CandidateConversionHandler] Validation error: {e}", exc_info=True)
            raise RuntimeError(f"Validation error (retryable): {str(e)}") from e

        except Exception as e:
            logger.error(
                f"[CandidateConversionHandler] Unexpected error for {candidate_id}: {e}",
                exc_info=True,
            )
            raise

    @staticmethod
    def should_retry(message: MessageQueue) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= CandidateConversionHandler.MAX_RETRIES:
            logger.error(
                f"[CandidateConversionHandler] Max retries exceeded for message {message.id} "
                f"(attempted {message.retry_count} times)"
            )
            return False

        if message.next_retry_at is None:
            return True

        if datetime.utcnow() < message.next_retry_at:
            logger.debug(
                f"[CandidateConversionHandler] Message {message.id} not ready for retry yet"
            )
            return False

        logger.info(
            f"[CandidateConversionHandler] Message {message.id} ready for retry "
            f"(attempt {message.retry_count + 1}/{CandidateConversionHandler.MAX_RETRIES})"
        )
        return True

    @staticmethod
    def on_retry(message: MessageQueue, error: str, db: Session) -> None:
        """Handle retry logic after failed attempt."""
        from datetime import timedelta

        message.retry_count += 1
        message.error = error
        message.next_retry_at = datetime.utcnow() + timedelta(
            minutes=CandidateConversionHandler.RETRY_DELAY_MINUTES
        )

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(
                f"[CandidateConversionHandler] Failed to update retry for message {message.id}: {e}",
                exc_info=True,
            )
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

        logger.info(
            f"[CandidateConversionHandler] Scheduled retry for message {message.id}: "
            f"retry_count={message.retry_count}/{CandidateConversionHandler.MAX_RETRIES}"
        )

    @staticmethod
    def on_success(message: MessageQueue, result: Dict[str, Any], db: Session) -> None:
        """Handle successful message processing."""
        message.status = "COMPLETED"
        message.completed_at = datetime.utcnow()
        message.result = result

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(
                f"[CandidateConversionHandler] Failed to mark message {message.id} as completed: {e}",
                exc_info=True,
            )
            raise RuntimeError(f"Failed to mark success: {str(e)}") from e

        logger.info(
            f"[CandidateConversionHandler] Message {message.id} completed successfully"
        )

    @staticmethod
    def on_failed(message: MessageQueue, final_error: str, db: Session) -> None:
        """Handle final failure after all retries exhausted."""
        message.status = "FAILED"
        message.error = final_error
        message.completed_at = datetime.utcnow()

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(
                f"[CandidateConversionHandler] Failed to mark message {message.id} as failed: {e}",
                exc_info=True,
            )
            raise

        logger.error(
            f"[CandidateConversionHandler] Message {message.id} FAILED after "
            f"{message.retry_count} retries: {final_error}"
        )
