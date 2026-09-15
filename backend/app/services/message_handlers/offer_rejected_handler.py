"""Message Handler: Offer Rejected

Triggers: offer_rejected message (candidate rejects offer)
Purpose: Update offer status, mark candidate available, check if job needs reopening
Output: Offer marked REJECTED, candidate status reverted
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound
from app.models.offer import Offer

logger = logging.getLogger(__name__)


class OfferRejectedHandler:
    """Record offer rejection."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=30)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """Process offer rejection."""
        try:
            if not message.payload:
                raise ValueError(f"Message {message.id} has no payload")

            payload = message.payload
            offer_id = payload.get('offer_id')
            reason = payload.get('rejection_reason', 'Candidate declined')

            # ============ PLACE 1: PRE-FLIGHT SLM ANALYSIS ============
            slm_analysis = None
            try:
                from app.services.slm_service import SLMService
                slm_analysis = SLMService.analyze_before_handler(
                    message_id=str(message.id),
                    message_type='offer_rejected',
                    payload=payload,
                    context={
                        'business_goal': 'Record offer rejection',
                        'risk_level': 'MEDIUM',
                        'offer_id': offer_id,
                        'rejection_reason': reason
                    },
                    db=db
                )
                if not slm_analysis.get('should_proceed'):
                    raise ValueError(f"SLM escalation: {slm_analysis.get('reasoning')}")
            except Exception as slm_err:
                logger.warning(f"[OfferRejected] SLM pre-flight failed (non-blocking): {slm_err}")

            if not offer_id:
                raise ValueError("Missing required field: offer_id")

            logger.info(f"[OfferRejected] Recording rejection: {offer_id}")

            offer = db.query(Offer).filter(Offer.id == offer_id).first()
            if not offer:
                raise ValueError(f"Offer {offer_id} not found")

            offer.status = 'REJECTED' if hasattr(offer, 'status') else None
            if hasattr(offer, 'rejection_reason'):
                offer.rejection_reason = reason
            if hasattr(offer, 'rejected_at'):
                offer.rejected_at = datetime.utcnow()

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(f"[OfferRejected] Commit failed: {commit_err}", exc_info=True)
                raise RuntimeError(f"Failed to reject offer: {str(commit_err)}") from commit_err

            # Send rejection notification email to hiring team
            delivery_id = None
            try:
                if hasattr(offer, 'job') and offer.job and hasattr(offer.job, 'created_by'):
                    from app.services.email_service import EmailService
                    from app.models.user import User

                    # Get hiring manager email
                    hiring_manager = db.query(User).filter(User.id == offer.job.created_by).first()
                    if hiring_manager and hasattr(hiring_manager, 'email'):
                        hm_email = hiring_manager.email
                        hm_name = getattr(hiring_manager, 'firstName', 'Hiring Manager')

                        rejection_email_subject = f"Candidate Rejection Notification - Offer {offer_id}"
                        rejection_email_body = f"""
Dear {hm_name},

The candidate has rejected the offer for the position.

**REJECTION DETAILS**
Reason: {reason}
Offer ID: {offer_id}

Please review your candidate pipeline and adjust accordingly.

Best regards,
Recruiting System
"""

                        result = EmailService.send_email(
                            to_email=hm_email,
                            subject=rejection_email_subject,
                            body_content=rejection_email_body,
                            is_html=True
                        )

                        if result.get('status') == 'skipped':
                            logger.warning(f"[OfferRejected] Email skipped to {hm_email}: {result.get('reason')}")
                        elif result.get('status') != 'success':
                            logger.warning(f"[OfferRejected] Failed to send rejection notification: {result}")
                        else:
                            delivery_id = "msgraph_" + str(hash(hm_email))
                            logger.info(f"[OfferRejected] Rejection notification sent to {hm_email}, delivery_id={delivery_id}")
            except Exception as email_err:
                logger.warning(f"[OfferRejected] Email delivery error (non-blocking): {email_err}")

            logger.info(f"[OfferRejected] ✅ Offer rejected")

            # ============ PLACE 2: POST-FLIGHT OUTCOME RECORDING ============
            if slm_analysis:
                try:
                    from app.services.slm_service import SLMService
                    result = {
                        'offer_id': str(offer_id),
                        'rejection_reason': reason,
                        'status': 'rejected'
                    }
                    SLMService.record_outcome(
                        slm_analysis=slm_analysis,
                        message_id=str(message.id),
                        handler_name='offer_rejected_handler',
                        handler_result=result,
                        business_impact={
                            'candidate_affected': True,
                            'offer_id': offer_id,
                            'rejection_reason': reason,
                            'expected_outcome': 'rejection_recorded',
                            'can_be_reversed': False,
                            'accountability_required': True,
                        },
                        db=db
                    )
                    logger.info(f"[OfferRejected] SLM outcome recorded")
                except Exception as slm_record_err:
                    logger.warning(f"[OfferRejected] SLM outcome recording failed: {slm_record_err}")

            return {
                'offer_id': str(offer_id),
                'rejection_reason': reason,
                'status': 'rejected',
                'delivery_id': delivery_id
            }

        except ValueError as ve:
            logger.error(f"[OfferRejected] Validation error: {ve}")
            raise
        except OperationalError as oe:
            logger.error(f"[OfferRejected] DB error: {oe}", exc_info=True)
            raise RuntimeError(f"Database error: {str(oe)}") from oe
        except Exception as e:
            logger.error(f"[OfferRejected] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that rejection was recorded."""
        from app.services.message_handlers.validate_handlers_factory import ValidateHandlersFactory
        return ValidateHandlersFactory.validate_offer_rejection_recorded(result, db, "offer_rejected")

    @staticmethod
    def should_retry(message: Any) -> bool:
        return message.retry_count < OfferRejectedHandler.MAX_RETRIES

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        db.rollback()
        message.retry_count += 1
        message.error = error[:1000]
        message.next_retry_at = datetime.utcnow() + timedelta(minutes=15)
        db.commit()

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        OfferRejectedHandler.validate(message, result, db)
        message.status = "COMPLETED"
        message.completed_at = datetime.utcnow()
        db.commit()

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        db.rollback()
        message.status = "FAILED"
        message.error = final_error[:1000]
        message.completed_at = datetime.utcnow()
        db.commit()


def handle_offer_rejected(message: Any, db: Session) -> Dict[str, Any]:
    """Backward compatibility wrapper."""
    return OfferRejectedHandler.process(message, db)
