"""Message Handler: HM Validation Response Recording

Triggers: hm_validation_response_submitted message (from portal webhook)
Purpose: Record HM's validation decision, queue next action
Output: Validation record updated with response, appropriate next message queued
State machine: PENDING → (APPROVED | REJECTED | ESCALATED)
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class HMValidationResponseHandler:
    """Record HM validation response and determine next action."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=30)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Record HM validation response and queue next action.

        State machine:
        - APPROVED (Q4='yes') → Queue interview_scheduling_approved
        - REJECTED (Q4='no')  → Queue candidate_rejected
        - ESCALATED (Q4='maybe') → Queue hm_validation_escalation

        Args:
            message: ChannelQueueItem with payload containing:
                - validation_id: HM validation record
                - responses: Dict of answers {q1, q2, q3, q4}
                - decision_score: Numeric confidence 0-100
            db: Database session

        Returns:
            {
                'validation_id': str,
                'status': str (APPROVED | REJECTED | ESCALATED),
                'response_time_hours': float,
                'next_action': str
            }

        Raises:
            ValueError: Invalid payload (non-retryable)
            RuntimeError: Database errors (retryable)
        """
        try:
            if not message.payload:
                raise ValueError(f"Message {message.id} has no payload")

            payload = message.payload
            validation_id = payload.get('validation_id')
            responses = payload.get('responses', {})

            if not validation_id:
                raise ValueError("Missing required field: validation_id")

            logger.info(
                f"[HMValidationResponse] Processing response: validation={validation_id}"
            )

            # PHASE 1: Verify validation exists and is PENDING
            from app.models.hiring import HiringManagerValidation

            validation = db.query(HiringManagerValidation).filter(
                HiringManagerValidation.id == validation_id
            ).first()

            if not validation:
                raise ValueError(f"HM validation {validation_id} not found")

            if validation.status != 'PENDING':
                raise ValueError(
                    f"Cannot record response for validation {validation_id} "
                    f"with status {validation.status}"
                )

            logger.info(f"[HMValidationResponse] Validation found: {validation_id}")

            # PHASE 2: Extract decision from Q4 response
            q4_response = responses.get('q4', '').lower()

            if q4_response == 'yes':
                next_status = 'APPROVED'
                next_action = 'interview_scheduling_approved'
            elif q4_response == 'no':
                next_status = 'REJECTED'
                next_action = 'candidate_rejected'
            elif q4_response == 'maybe':
                next_status = 'ESCALATED'
                next_action = 'hm_validation_escalated'
            else:
                raise ValueError(f"Invalid Q4 response: {q4_response}")

            logger.info(
                f"[HMValidationResponse] Decision: {next_status}, "
                f"next action: {next_action}"
            )

            # PHASE 3: Calculate response time
            response_time_minutes = (
                datetime.utcnow() - validation.created_at
            ).total_seconds() / 60
            response_time_hours = response_time_minutes / 60

            logger.info(
                f"[HMValidationResponse] Response time: {response_time_hours:.1f} hours"
            )

            # PHASE 4: Update validation record
            validation.status = next_status
            validation.responses = responses
            validation.responded_at = datetime.utcnow()
            validation.response_time_hours = response_time_hours

            # PHASE 5: Queue next action message
            try:
                from app.services.message_queue_service import MessageQueueService

                MessageQueueService.enqueue(
                    task_name=next_action,
                    task_id=f"{next_action}_{validation_id}",
                    data={
                        'validation_id': str(validation_id),
                        'candidate_id': str(validation.candidate_id),
                        'job_id': str(validation.job_id),
                        'hiring_manager_id': str(validation.hiring_manager_id),
                        'decision': next_status,
                        'responses': responses
                    }
                )
                logger.info(f"[HMValidationResponse] Queued {next_action} message")

            except Exception as queue_err:
                logger.warning(
                    f"[HMValidationResponse] Failed to queue next message "
                    f"(non-blocking): {queue_err}"
                )

            # PHASE 6: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(
                    f"[HMValidationResponse] Commit failed: {commit_err}",
                    exc_info=True
                )
                raise RuntimeError(
                    f"Failed to record response: {str(commit_err)}"
                ) from commit_err

            logger.info(f"[HMValidationResponse] ✅ Response recorded successfully")

            return {
                'validation_id': str(validation_id),
                'status': next_status,
                'response_time_hours': response_time_hours,
                'next_action': next_action
            }

        except ValueError as ve:
            logger.error(f"[HMValidationResponse] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(
                f"[HMValidationResponse] DB operational error: {oe}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[HMValidationResponse] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that response was recorded successfully."""
        from app.models.hiring import HiringManagerValidation

        if not result or "validation_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        validation_id = result.get('validation_id')
        expected_status = result.get('status')

        try:
            validation = db.query(HiringManagerValidation).filter(
                HiringManagerValidation.id == validation_id
            ).first()

            if not validation:
                raise ValueError(f"Validation {validation_id} not found")

            if validation.status != expected_status:
                raise ValueError(
                    f"Validation {validation_id} status is {validation.status}, "
                    f"expected {expected_status}"
                )

            if not validation.responded_at:
                raise ValueError(f"Validation {validation_id} responded_at not set")

            if not validation.responses:
                raise ValueError(f"Validation {validation_id} responses not stored")

            logger.info(f"✅ HM response validation passed: {validation_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(
                f"[HMValidationResponse] RETRYABLE validation error: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= HMValidationResponseHandler.MAX_RETRIES:
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
                minutes=HMValidationResponseHandler.RETRY_DELAY_MINUTES
            )
            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(
                f"[HMValidationResponse] Failed to schedule retry: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            HMValidationResponseHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err

            logger.info(f"[HMValidationResponse] ✅ Message marked COMPLETED")

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"[HMValidationResponse] Unexpected error: {e}", exc_info=True)
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
                f"[HMValidationResponse] Failed to mark as FAILED: {e}",
                exc_info=True
            )
            raise
