"""Message Handler: Offer Approved

Triggers: offer_approved message (manager/HR approves offer)
Purpose: Update offer status to APPROVED, queue send notification
Output: Offer marked APPROVED, candidate notification queued
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound
from app.models.offer import Offer

logger = logging.getLogger(__name__)


class OfferApprovedHandler:
    """Record offer approval."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=30)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """Process offer approval."""
        try:
            if not message.payload:
                raise ValueError(f"Message {message.id} has no payload")

            payload = message.payload
            offer_id = payload.get('offer_id')
            approver_id = payload.get('approver_id')

            # ============ PLACE 1: PRE-FLIGHT SLM ANALYSIS ============
            slm_analysis = None
            try:
                from app.services.slm_service import SLMService
                slm_analysis = SLMService.analyze_before_handler(
                    message_id=str(message.id),
                    message_type='offer_approved',
                    payload=payload,
                    context={
                        'business_goal': 'Record offer approval for candidate',
                        'risk_level': 'HIGH',
                        'offer_id': offer_id,
                        'approver_id': approver_id
                    },
                    db=db
                )
                if not slm_analysis.get('should_proceed'):
                    raise ValueError(f"SLM escalation: {slm_analysis.get('reasoning')}")
            except Exception as slm_err:
                logger.warning(f"[OfferApproved] SLM pre-flight failed (non-blocking): {slm_err}")

            if not offer_id:
                raise ValueError("Missing required field: offer_id")

            logger.info(f"[OfferApproved] Recording approval: {offer_id}")

            offer = db.query(Offer).filter(Offer.id == offer_id).first()
            if not offer:
                raise ValueError(f"Offer {offer_id} not found")

            if hasattr(offer, 'status'):
                offer.status = 'APPROVED'
                if hasattr(offer, 'approved_by'):
                    offer.approved_by = approver_id
                if hasattr(offer, 'approved_at'):
                    offer.approved_at = datetime.utcnow()

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(f"[OfferApproved] Commit failed: {commit_err}", exc_info=True)
                raise RuntimeError(f"Failed to approve offer: {str(commit_err)}") from commit_err

            # Send approval notification email to candidate
            delivery_id = None
            try:
                if hasattr(offer, 'candidate') and offer.candidate and hasattr(offer.candidate, 'email'):
                    from app.services.email_service import EmailService

                    candidate_email = offer.candidate.email
                    candidate_name = getattr(offer.candidate, 'candidateFirstName', 'Candidate')

                    approval_email_subject = "Your Job Offer Has Been Approved"
                    approval_email_body = f"""
Dear {candidate_name},

Great news! Your job offer has been approved and is ready for review.

We're excited to move forward with you. Please expect the formal offer document soon.

If you have any questions, please don't hesitate to reach out to our HR team.

Best regards,
Recruiting Team
"""

                    result = EmailService.send_email(
                        to_email=candidate_email,
                        subject=approval_email_subject,
                        body_content=approval_email_body,
                        is_html=True
                    )

                    if result.get('status') == 'skipped':
                        logger.warning(f"[OfferApproved] Email skipped to {candidate_email}: {result.get('reason')}")
                    elif result.get('status') != 'success':
                        logger.error(f"[OfferApproved] Failed to send approval email: {result}")
                        raise RuntimeError(f"Failed to send approval email: {result}")

                    delivery_id = "msgraph_" + str(hash(candidate_email))
                    logger.info(f"[OfferApproved] Approval notification sent to {candidate_email}, delivery_id={delivery_id}")
            except Exception as email_err:
                logger.error(f"[OfferApproved] Email delivery error (non-blocking): {email_err}")

            logger.info(f"[OfferApproved] ✅ Offer approved")

            # ============ PLACE 2: POST-FLIGHT OUTCOME RECORDING ============
            if slm_analysis:
                try:
                    from app.services.slm_service import SLMService
                    result = {
                        'offer_id': str(offer_id),
                        'approver_id': approver_id,
                        'status': 'approved'
                    }
                    SLMService.record_outcome(
                        slm_analysis=slm_analysis,
                        message_id=str(message.id),
                        handler_name='offer_approved_handler',
                        handler_result=result,
                        business_impact={
                            'candidate_affected': False,
                            'approver_id': approver_id,
                            'offer_id': offer_id,
                            'expected_outcome': 'approval_recorded',
                            'can_be_reversed': True,
                            'accountability_required': True,
                        },
                        db=db
                    )
                    logger.info(f"[OfferApproved] SLM outcome recorded")
                except Exception as slm_record_err:
                    logger.warning(f"[OfferApproved] SLM outcome recording failed: {slm_record_err}")

            return {
                'offer_id': str(offer_id),
                'approver_id': approver_id,
                'status': 'approved',
                'delivery_id': delivery_id
            }

        except ValueError as ve:
            logger.error(f"[OfferApproved] Validation error: {ve}")
            raise
        except OperationalError as oe:
            logger.error(f"[OfferApproved] DB error: {oe}", exc_info=True)
            raise RuntimeError(f"Database error: {str(oe)}") from oe
        except Exception as e:
            logger.error(f"[OfferApproved] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that approval was recorded."""
        from app.services.message_handlers.validate_handlers_factory import ValidateHandlersFactory
        return ValidateHandlersFactory.validate_offer_approval_recorded(result, db, "offer_approved")

    @staticmethod
    def should_retry(message: Any) -> bool:
        if message.retry_count >= OfferApprovedHandler.MAX_RETRIES:
            return False
        if hasattr(message, 'next_retry_at') and message.next_retry_at:
            if datetime.utcnow() < message.next_retry_at:
                return False
        return True

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        try:
            db.rollback()
            message.retry_count += 1
            message.error = error[:1000] if error else "Unknown error"
            message.next_retry_at = datetime.utcnow() + timedelta(
                minutes=OfferApprovedHandler.RETRY_DELAY_MINUTES
            )
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[OfferApproved] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        try:
            OfferApprovedHandler.validate(message, result, db)
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err
            logger.info(f"[OfferApproved] ✅ Message marked COMPLETED")
        except (ValueError, RuntimeError):
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"[OfferApproved] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        try:
            db.rollback()
            message.status = "FAILED"
            message.error = final_error[:1000] if final_error else "Unknown error"
            message.completed_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[OfferApproved] Failed to mark FAILED: {e}", exc_info=True)
            raise


def handle_offer_approved(message: Any, db: Session) -> Dict[str, Any]:
    """Backward compatibility wrapper."""
    return OfferApprovedHandler.process(message, db)
