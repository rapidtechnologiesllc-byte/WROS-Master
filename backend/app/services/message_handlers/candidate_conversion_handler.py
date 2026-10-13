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

from app.models.channel_queue import ChannelQueueItem
from app.models.candidate import Candidate, CandidateStatus
from app.models.employee import Employee
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class CandidateConversionHandler:
    """Handles candidate-to-employee conversion messages from queue with retry logic."""

    HANDLER_NAME = "candidate_conversion"
    TIMEOUT_SECONDS = 40
    MAX_RETRIES = 5
    RETRY_DELAY_MINUTES = 30

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(
        message: ChannelQueueItem,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Process candidate-to-employee conversion message.

        Implements FAIL FAST: Raises exceptions on any error.

        Args:
            message: ChannelQueueItem record with payload containing conversion data
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
    def should_retry(message: ChannelQueueItem) -> bool:
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
    def validate(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
        """Validate that candidate conversion actually completed successfully."""
        from app.models.employee import Employee

        if not result or "employee_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        candidate_id = result.get("candidate_id")
        employee_id = result.get("employee_id")

        try:
            # Verify candidate still exists
            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found after conversion")

            # Verify employee was created
            employee = db.query(Employee).filter(Employee.id == employee_id).first()
            if not employee:
                raise ValueError(f"Employee {employee_id} not found after conversion")

            # Verify status updated to EMPLOYEE (NEW)
            status = db.query(CandidateStatus).filter(
                CandidateStatus.candidateID == candidate_id
            ).first()
            if not status or status.piplineStatus != "EMPLOYEE":
                raise ValueError(
                    f"Candidate {candidate_id} status not EMPLOYEE: "
                    f"found '{status.piplineStatus if status else 'NONE'}'"
                )

            # Verify email matches (data integrity) (NEW)
            if employee.email != candidate.candidateEmail:
                raise ValueError(
                    f"Email mismatch after conversion: employee={employee.email}, "
                    f"candidate={candidate.candidateEmail}"
                )

            logger.info(f"✅ Candidate conversion validated: {candidate_id} -> {employee_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[CandidateConversionHandler] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def on_retry(message: ChannelQueueItem, error: str, db: Session) -> None:
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
    def on_success(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
        """Handle successful message processing with validation before marking COMPLETED."""
        try:
            # ===== VALIDATION STEP 1: Check result structure =====
            if not isinstance(result, dict):
                raise ValueError(f"Handler returned invalid type: {type(result)}")

            required_fields = ['candidate_id', 'employee_id', 'status']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Handler result missing required field: {field}")
                if not result[field]:
                    raise ValueError(f"Handler result has empty field: {field}")

            candidate_id = result['candidate_id']
            employee_id = result['employee_id']
            logger.info(f"[Handler] ✅ Step 1: Result structure valid (candidate_id={candidate_id}, employee_id={employee_id})")

            # ===== VALIDATION STEP 2: Database verification - candidate exists =====
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                raise RuntimeError(
                    f"Record {candidate_id} not found in database after handler completed. "
                    f"Handler returned ID but record was not persisted."
                )

            logger.info("[Handler] ✅ Step 2a: Database verification passed, candidate exists")

            # ===== VALIDATION STEP 2b: Database verification - employee exists =====
            employee = db.query(Employee).filter(Employee.id == employee_id).first()

            if not employee:
                raise RuntimeError(
                    f"Employee {employee_id} not found in database after conversion. "
                    f"Handler returned ID but employee record was not created."
                )

            logger.info("[Handler] ✅ Step 2b: Database verification passed, employee exists")

            # ===== VALIDATION STEP 3: Related records consistency =====
            # Verify candidate status was updated to EMPLOYEE
            status = db.query(CandidateStatus).filter(
                CandidateStatus.candidateID == candidate_id
            ).first()

            if not status:
                raise RuntimeError(
                    f"Required status record missing for {candidate_id}. "
                    f"Candidate exists but status was not created."
                )

            if status.piplineStatus != "EMPLOYEE":
                raise RuntimeError(
                    f"Candidate {candidate_id} status is '{status.piplineStatus}', "
                    f"expected 'EMPLOYEE'. Conversion not properly recorded."
                )

            logger.info("[Handler] ✅ Step 3: Related records valid, status updated to EMPLOYEE")

            # ===== VALIDATION STEP 4: Data integrity =====
            # Verify employee details match candidate
            if employee.email != candidate.candidateEmail:
                raise RuntimeError(
                    f"Email mismatch: employee has '{employee.email}' "
                    f"but candidate has '{candidate.candidateEmail}'. "
                    f"Data corruption detected."
                )

            logger.info("[Handler] ✅ Step 4: Data integrity verified, email matches")

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
            # Non-retryable error (handler code bug)
            db.rollback()
            logger.error(f"[Handler] ❌ NON-RETRYABLE validation failure: {e}")
            raise  # Will be caught by processor

        except RuntimeError as e:
            # Retryable error (temporary DB issue)
            db.rollback()
            logger.error(f"[Handler] ❌ RETRYABLE validation failure: {e}")
            raise  # Will be caught by processor

        except Exception as e:
            # Unexpected error
            db.rollback()
            logger.error(f"[Handler] ❌ Unexpected validation error: {e}", exc_info=True)
            raise RuntimeError(f"Validation error: {str(e)}") from e

    @staticmethod
    def on_failed(message: ChannelQueueItem, final_error: str, db: Session) -> None:
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
