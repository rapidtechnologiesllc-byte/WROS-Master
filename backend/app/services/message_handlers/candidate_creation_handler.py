"""Message Handler: Candidate Creation with Retry Logic

Implements idempotent candidate creation through message queue.
- 5 retry attempts with 30-minute intervals
- Waits for candidate_id confirmation from database
- Marks success only when candidate exists in database
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.message_queue import MessageQueue
from app.models.candidate import Candidate
from app.services.candidate_service import (
    create_candidate_safe,
    DuplicateCandidateError,
)
from app.utils.uniq_id_generator import generate_password as generate_temp_password

logger = logging.getLogger(__name__)


class CandidateCreationHandler:
    """Handles candidate creation messages from queue with retry logic."""

    MAX_RETRIES = 5
    RETRY_DELAY_MINUTES = 30

    @staticmethod
    def process(
        message: MessageQueue,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Process candidate creation message.

        Implements FAIL FAST: Raises exceptions on any error.

        Args:
            message: MessageQueue record with payload containing candidate data
            db: Database session

        Returns:
            {'status': 'success', 'candidate_id': str, 'is_new': bool}

        Raises:
            ValueError: If payload invalid
            DuplicateCandidateError: If candidate already exists (retryable)
            RuntimeError: If database commit fails (retryable)
            Exception: Any unhandled error (retryable, will mark FAILED after 5 attempts)
        """
        if not message.payload:
            raise ValueError(f"Message {message.id} has no payload")

        payload = message.payload
        logger.info(f"[CandidateCreationHandler] Processing candidate creation: {payload.get('candidate_email')}")

        try:
            # Extract candidate data from payload
            candidate_email = payload.get("candidate_email")
            candidate_mobile = payload.get("candidate_mobile")
            candidate_password = payload.get("candidate_password")
            tenant_id = payload.get("tenant_id")
            candidate_role = payload.get("candidate_role", "Candidate")
            candidate_employee_type = payload.get("candidate_employee_type")
            candidate_job_title = payload.get("candidate_job_title")
            candidate_first_name = payload.get("candidate_first_name")
            candidate_last_name = payload.get("candidate_last_name")
            candidate_gender = payload.get("candidate_gender")
            candidate_date_of_birth = payload.get("candidate_date_of_birth")
            candidate_current_location = payload.get("candidate_current_location")

            # Validate mandatory fields
            if not candidate_email:
                raise ValueError("candidate_email is required")
            if not candidate_current_location:
                raise ValueError("candidate_current_location is required")
            if not tenant_id:
                raise ValueError("tenant_id is required")

            # Create candidate using sanctioned R-07 path
            candidate, is_new = create_candidate_safe(
                db,
                email=candidate_email,
                mobile=candidate_mobile,
                plain_password=candidate_password,
                tenant_id=tenant_id,
                candidateRole=candidate_role,
                candidateEmployeeType=candidate_employee_type,
                candidateJobTitle=candidate_job_title,
                candidateFirstName=candidate_first_name,
                candidateLastName=candidate_last_name,
                candidateGender=candidate_gender,
                candidateDateOfBirth=candidate_date_of_birth,
                candidateCurrentLocation=candidate_current_location,
                candidateCreatedAt=datetime.now(),
            )

            # Attempt to commit to database
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(
                    f"[CandidateCreationHandler] Commit failed for {candidate_email}: {commit_err}",
                    exc_info=True,
                )
                raise RuntimeError(f"Database commit failed: {str(commit_err)}") from commit_err

            # Verify candidate was created and has ID
            candidate_id = candidate.candidateID
            if not candidate_id:
                db.rollback()
                raise ValueError(f"Candidate created but has no candidateID")

            # Final verification: Query database to confirm candidate exists
            try:
                db.refresh(candidate)
                verified_candidate = db.query(Candidate).filter(
                    Candidate.candidateID == candidate_id
                ).first()

                if not verified_candidate:
                    raise ValueError(
                        f"Candidate {candidate_id} created but not found in verification query"
                    )

            except Exception as verify_err:
                logger.error(
                    f"[CandidateCreationHandler] Verification failed for {candidate_id}: {verify_err}",
                    exc_info=True,
                )
                raise RuntimeError(f"Candidate verification failed: {str(verify_err)}") from verify_err

            logger.info(
                f"[CandidateCreationHandler] ✅ Candidate created successfully: "
                f"id={candidate_id}, email={candidate_email}, is_new={is_new}"
            )

            return {
                "status": "success",
                "candidate_id": candidate_id,
                "is_new": is_new,
                "candidate_email": candidate_email,
            }

        except DuplicateCandidateError as e:
            # Duplicate candidates are retryable in case it was a transient issue
            logger.warning(
                f"[CandidateCreationHandler] Duplicate candidate detected: {payload.get('candidate_email')}",
                exc_info=True,
            )
            raise RuntimeError(f"Duplicate candidate (retryable): {str(e)}") from e

        except ValueError as e:
            # Validation errors are retryable (might be transient state)
            logger.warning(
                f"[CandidateCreationHandler] Validation error for {payload.get('candidate_email')}: {e}",
                exc_info=True,
            )
            raise RuntimeError(f"Validation error (retryable): {str(e)}") from e

        except Exception as e:
            logger.error(
                f"[CandidateCreationHandler] Unexpected error for {payload.get('candidate_email')}: {e}",
                exc_info=True,
            )
            raise

    @staticmethod
    def should_retry(message: MessageQueue) -> bool:
        """
        Determine if message should be retried.

        Retries up to MAX_RETRIES times with RETRY_DELAY_MINUTES between attempts.

        Args:
            message: MessageQueue record with retry_count and next_retry_at

        Returns:
            True if should retry, False if max retries exceeded
        """
        if message.retry_count >= CandidateCreationHandler.MAX_RETRIES:
            logger.error(
                f"[CandidateCreationHandler] Max retries exceeded for message {message.id} "
                f"(attempted {message.retry_count} times)"
            )
            return False

        # Check if enough time has passed since last retry
        if message.next_retry_at is None:
            return True

        if datetime.utcnow() < message.next_retry_at:
            logger.debug(
                f"[CandidateCreationHandler] Message {message.id} not ready for retry yet "
                f"(next_retry_at={message.next_retry_at})"
            )
            return False

        logger.info(
            f"[CandidateCreationHandler] Message {message.id} ready for retry "
            f"(attempt {message.retry_count + 1}/{CandidateCreationHandler.MAX_RETRIES})"
        )
        return True

    @staticmethod
    def on_retry(message: MessageQueue, error: str, db: Session) -> None:
        """
        Handle retry logic after failed attempt.

        Increments retry_count and schedules next retry attempt.

        Args:
            message: MessageQueue record to update
            error: Error message from the failed attempt
            db: Database session
        """
        message.retry_count += 1
        message.error = error
        message.next_retry_at = datetime.utcnow() + timedelta(
            minutes=CandidateCreationHandler.RETRY_DELAY_MINUTES
        )

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(
                f"[CandidateCreationHandler] Failed to update retry schedule for message {message.id}: {e}",
                exc_info=True,
            )
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

        logger.info(
            f"[CandidateCreationHandler] Scheduled retry for message {message.id}: "
            f"next_retry_at={message.next_retry_at}, retry_count={message.retry_count}/{CandidateCreationHandler.MAX_RETRIES}"
        )

    @staticmethod
    def on_success(message: MessageQueue, result: Dict[str, Any], db: Session) -> None:
        """
        Handle successful message processing.

        Updates message status to COMPLETED and stores result in metadata.

        Args:
            message: MessageQueue record to mark as completed
            result: Result dict from process() method
            db: Database session
        """
        message.status = "COMPLETED"
        message.completed_at = datetime.utcnow()
        message.result = result

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(
                f"[CandidateCreationHandler] Failed to mark message {message.id} as completed: {e}",
                exc_info=True,
            )
            raise RuntimeError(f"Failed to mark success: {str(e)}") from e

        logger.info(
            f"[CandidateCreationHandler] ✅ Message {message.id} completed successfully "
            f"(candidate_id={result.get('candidate_id')})"
        )

    @staticmethod
    def on_failed(message: MessageQueue, final_error: str, db: Session) -> None:
        """
        Handle final failure after all retries exhausted.

        Updates message status to FAILED and logs for investigation.

        Args:
            message: MessageQueue record that failed
            final_error: Final error message
            db: Database session
        """
        message.status = "FAILED"
        message.error = final_error
        message.completed_at = datetime.utcnow()

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(
                f"[CandidateCreationHandler] Failed to mark message {message.id} as failed: {e}",
                exc_info=True,
            )
            raise

        logger.error(
            f"[CandidateCreationHandler] ❌ Message {message.id} FAILED after "
            f"{message.retry_count} retries: {final_error}"
        )
