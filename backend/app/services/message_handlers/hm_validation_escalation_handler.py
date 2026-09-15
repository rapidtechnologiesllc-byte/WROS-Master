"""Message Handler: HM Validation Escalation

Triggers: hm_validation_escalated message (from response or timeout)
Purpose: Escalate MAYBE/TIMEOUT responses to HM's manager for review
Output: Escalation recorded, manager notified
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class HMValidationEscalationHandler:
    """Escalate HM validation to manager for final decision."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=35)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Escalate HM validation to manager.

        Escalation reasons:
        - hm_response_maybe: HM uncertain (Q4='maybe')
        - hm_response_timeout: HM didn't respond within 24h
        - hm_manual_escalation: HM clicked escalate button

        Args:
            message: ChannelQueueItem with payload containing:
                - validation_id: HM validation record
                - escalation_reason: Why escalating
            db: Database session

        Returns:
            {
                'validation_id': str,
                'escalated_to_user_id': str,
                'escalation_reason': str,
                'email_sent': bool
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
            escalation_reason = payload.get('escalation_reason', 'hm_response_maybe')

            if not validation_id:
                raise ValueError("Missing required field: validation_id")

            logger.info(
                f"[HMValidationEscalation] Escalating: validation={validation_id}, "
                f"reason={escalation_reason}"
            )

            # PHASE 1: Verify validation exists
            from app.models.hiring import HiringManagerValidation

            validation = db.query(HiringManagerValidation).filter(
                HiringManagerValidation.id == validation_id
            ).first()

            if not validation:
                raise ValueError(f"HM validation {validation_id} not found")

            logger.info(f"[HMValidationEscalation] Validation found: {validation_id}")

            # PHASE 2: Find HM's manager via org structure
            from app.models.user import User

            hm = db.query(User).filter(User.id == validation.hiring_manager_id).first()

            if not hm:
                raise ValueError(f"Hiring manager not found")

            # Get manager from org_structure (or skip-level)
            manager_id = getattr(hm, 'manager_id', None) or getattr(hm, 'skip_level_manager_id', None)

            if not manager_id:
                raise ValueError(f"HM has no manager assigned for escalation")

            manager = db.query(User).filter(User.id == manager_id).first()

            if not manager:
                raise ValueError(f"Manager {manager_id} not found")

            logger.info(f"[HMValidationEscalation] Manager: {manager.email}")

            # PHASE 3: Update validation to mark escalated
            validation.status = 'ESCALATED'
            validation.escalated_to_user_id = manager_id
            validation.escalated_at = datetime.utcnow()
            validation.escalation_reason = escalation_reason

            # PHASE 4: Send email to manager via Microsoft Graph
            email_sent = False
            delivery_id = None
            try:
                from app.services.email_service import EmailService

                email_subject = f"Escalation: HM Decision Required on Candidate Validation"
                email_body = f"""
Hi {manager.firstName or 'Manager'},

{hm.firstName} is uncertain about a candidate match. Please review and make a final decision.

Escalation Reason: {escalation_reason}
Due: {validation.due_at.strftime('%Y-%m-%d %H:%M UTC') if hasattr(validation, 'due_at') else 'ASAP'}

[Review & decide: /hr/hm-validations/{validation_id}/escalated]

Thank you,
AI Recruiting
                """

                delivery_result = EmailService.send_email(
                    to_email=manager.email,
                    subject=email_subject,
                    body_content=email_body,
                    is_html=True
                )

                if delivery_result and delivery_result.get('status') == 'success':
                    email_sent = True
                    delivery_id = "msgraph_" + str(hash(manager.email))
                    logger.info(f"[HMValidationEscalation] Escalation email sent: {delivery_id}")
                elif delivery_result and delivery_result.get('status') == 'skipped':
                    logger.warning(f"[HMValidationEscalation] Email skipped: {delivery_result.get('reason')}")
                else:
                    logger.warning(f"[HMValidationEscalation] Email delivery failed: {delivery_result}")

            except Exception as email_err:
                logger.warning(
                    f"[HMValidationEscalation] Failed to send escalation email "
                    f"(non-blocking): {email_err}"
                )

            # PHASE 5: Commit transaction
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(
                    f"[HMValidationEscalation] Commit failed: {commit_err}",
                    exc_info=True
                )
                raise RuntimeError(f"Failed to escalate: {str(commit_err)}") from commit_err

            logger.info(f"[HMValidationEscalation] ✅ Escalation processed")

            return {
                'validation_id': str(validation_id),
                'escalated_to_user_id': str(manager_id),
                'escalation_reason': escalation_reason,
                'email_sent': email_sent,
                'delivery_id': delivery_id
            }

        except ValueError as ve:
            logger.error(f"[HMValidationEscalation] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(
                f"[HMValidationEscalation] DB operational error: {oe}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[HMValidationEscalation] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that escalation was processed successfully."""
        from app.models.hiring import HiringManagerValidation

        if not result or "validation_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        validation_id = result.get('validation_id')

        try:
            validation = db.query(HiringManagerValidation).filter(
                HiringManagerValidation.id == validation_id
            ).first()

            if not validation:
                raise ValueError(f"Validation {validation_id} not found")

            if validation.status != 'ESCALATED':
                raise ValueError(
                    f"Validation {validation_id} status is {validation.status}, "
                    f"expected ESCALATED"
                )

            if not validation.escalated_to_user_id:
                raise ValueError(f"Escalation target not set")

            logger.info(f"✅ Escalation validation passed: {validation_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(
                f"[HMValidationEscalation] RETRYABLE validation error: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= HMValidationEscalationHandler.MAX_RETRIES:
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
                minutes=HMValidationEscalationHandler.RETRY_DELAY_MINUTES
            )
            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"[HMValidationEscalation] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            HMValidationEscalationHandler.validate(message, result, db)

            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err

            logger.info(f"[HMValidationEscalation] ✅ Message marked COMPLETED")

        except ValueError:
            db.rollback()
            raise

        except RuntimeError:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"[HMValidationEscalation] Unexpected error: {e}", exc_info=True)
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
            logger.error(f"[HMValidationEscalation] Failed to mark as FAILED: {e}", exc_info=True)
            raise
