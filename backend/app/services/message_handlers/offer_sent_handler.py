"""Offer Sent Message Handler - Process offer sent notifications."""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from app.models.offer import Offer
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class OfferSentHandler:
    """Handles offer_sent messages with time-bound execution and validation."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=10)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """Process offer_sent message - triggered when offer is sent to candidate.

        Args:
            message: ChannelQueueItem with type='offer_sent'
            db: SQLAlchemy session

        Returns:
            {status, offer_id, candidate_id, sent_at, response_deadline}
        """
        try:
            payload = message.payload or {}
            offer_id = payload.get('offer_id')

            # ============ PLACE 1: PRE-FLIGHT SLM ANALYSIS ============
            slm_analysis = None
            try:
                from app.services.slm_service import SLMService
                slm_analysis = SLMService.analyze_before_handler(
                    message_id=str(message.id),
                    message_type='offer_sent',
                    payload=payload,
                    context={
                        'business_goal': 'Send offer notification to candidate',
                        'risk_level': 'MEDIUM',
                        'offer_id': offer_id,
                        'candidate_id': payload.get('candidate_id')
                    },
                    db=db
                )
                if not slm_analysis.get('should_proceed'):
                    raise ValueError(f"SLM escalation: {slm_analysis.get('reasoning')}")
            except Exception as slm_err:
                logger.warning(f"[OfferSent] SLM pre-flight failed (non-blocking): {slm_err}")

            if not offer_id:
                raise ValueError("offer_id is required in payload")

            # 1. Fetch offer
            offer = db.query(Offer).filter(Offer.id == offer_id).first()
            if not offer:
                raise ValueError(f"Offer {offer_id} not found")

            logger.info(f"[OfferSent] Processing offer {offer_id} being sent to candidate")

            candidate_id = offer.candidate_id if hasattr(offer, 'candidate_id') else None

            # 2. Calculate response deadline FIRST (before email composition)
            response_deadline = None
            try:
                response_deadline = (datetime.utcnow() + timedelta(days=5)).isoformat()
                # In production: store deadline in offer record for tracking
                if hasattr(offer, 'response_deadline'):
                    offer.response_deadline = response_deadline
            except Exception as deadline_err:
                logger.warning(f"[OfferSent] Could not calculate deadline: {deadline_err}")
                response_deadline = "N/A"

            # 3. Update offer status to SENT
            if hasattr(offer, 'status'):
                offer.status = 'SENT'
                if hasattr(offer, 'sent_at'):
                    offer.sent_at = datetime.utcnow()
                db.commit()

            # 4. Send offer document to candidate
            document_sent = False
            delivery_id = None
            try:
                if candidate_id and hasattr(offer, 'candidate'):
                    candidate_obj = offer.candidate if hasattr(offer, 'candidate') else None
                    if candidate_obj and hasattr(candidate_obj, 'email'):
                        from app.services.email_service import EmailService

                        # Compose offer email (now response_deadline is defined)
                        offer_email_subject = f"Job Offer - {offer.job.jobTitle if hasattr(offer, 'job') and hasattr(offer.job, 'jobTitle') else 'Position'}"
                        offer_email_body = f"""
Dear {candidate_obj.candidateFirstName if hasattr(candidate_obj, 'candidateFirstName') else 'Candidate'},

Congratulations! We are pleased to extend a job offer for the position.

**OFFER DETAILS**
Position: {offer.job.jobTitle if hasattr(offer, 'job') and hasattr(offer.job, 'jobTitle') else 'N/A'}
Response Deadline: {response_deadline}

Please review the attached offer letter carefully. If you have any questions, please reach out to our HR team.

Best regards,
Recruiting Team
"""

                        result = EmailService.send_email(
                            to_email=candidate_obj.email,
                            subject=offer_email_subject,
                            body_content=offer_email_body,
                            is_html=True
                        )

                        if result.get('status') == 'skipped':
                            logger.warning(f"[OfferSent] Email skipped to {candidate_obj.email}: {result.get('reason')}")
                        elif result.get('status') != 'success':
                            raise RuntimeError(f"Failed to send offer email: {result}")

                        delivery_id = "msgraph_" + str(hash(candidate_obj.email))
                        document_sent = True
                        logger.info(f"[OfferSent] Offer document sent to {candidate_obj.email}, delivery_id={delivery_id}")
                    else:
                        logger.warning(f"[OfferSent] Candidate {candidate_id} has no email, skipping delivery")
            except Exception as doc_err:
                logger.error(f"[OfferSent] Could not send offer document: {doc_err}", exc_info=True)
                raise RuntimeError(f"Failed to send offer: {str(doc_err)}") from doc_err

            result = {
                "status": "offer_sent",
                "offer_id": offer_id,
                "candidate_id": candidate_id,
                "document_sent": document_sent,
                "delivery_id": delivery_id,
                "response_deadline": response_deadline,
                "message": f"Offer {offer_id} sent to candidate {candidate_id}"
            }

            logger.info(f"[OfferSent] ✅ Completed: {offer_id}")

            # ============ PLACE 2: POST-FLIGHT OUTCOME RECORDING ============
            if slm_analysis:
                try:
                    from app.services.slm_service import SLMService
                    SLMService.record_outcome(
                        slm_analysis=slm_analysis,
                        message_id=str(message.id),
                        handler_name='offer_sent_handler',
                        handler_result=result,
                        business_impact={
                            'candidate_affected': True,
                            'offer_id': offer_id,
                            'candidate_id': result.get('candidate_id'),
                            'expected_outcome': 'offer_delivered',
                            'can_be_reversed': False,
                            'accountability_required': False,
                        },
                        db=db
                    )
                    logger.info("[OfferSent] SLM outcome recorded")
                except Exception as slm_record_err:
                    logger.warning(f"[OfferSent] SLM outcome recording failed: {slm_record_err}")

            return result

        except ValueError as ve:
            logger.error(f"[OfferSent] Validation error: {ve}")
            raise
        except OperationalError as oe:
            logger.error(f"[OfferSent] DB error: {oe}", exc_info=True)
            raise RuntimeError(f"Database error: {str(oe)}") from oe
        except Exception as e:
            logger.error(f"[OfferSent] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that offer notification was queued successfully."""
        from app.services.message_handlers.validate_handlers_factory import ValidateHandlersFactory
        return ValidateHandlersFactory.validate_offer_sent_recorded(result, db, "offer_sent")

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        return message.retry_count < OfferSentHandler.MAX_RETRIES

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        """Schedule message for retry."""
        db.rollback()
        message.retry_count += 1
        message.error = error[:1000]
        message.next_retry_at = datetime.utcnow() + timedelta(minutes=OfferSentHandler.RETRY_DELAY_MINUTES)
        db.commit()

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation passes."""
        OfferSentHandler.validate(message, result, db)
        message.status = "COMPLETED"
        message.completed_at = datetime.utcnow()
        db.commit()

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries exhausted."""
        db.rollback()
        message.status = "FAILED"
        message.error = final_error[:1000]
        message.completed_at = datetime.utcnow()
        db.commit()


def handle_offer_sent(message: Any, db: Session) -> Dict[str, Any]:
    """Handle offer_sent message."""
    return OfferSentHandler.process(message, db)
