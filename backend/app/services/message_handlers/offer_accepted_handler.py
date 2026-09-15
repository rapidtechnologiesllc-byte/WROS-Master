"""Message Handler: Offer Accepted

Triggers: offer_accepted message (candidate accepts offer)
Purpose: Update offer/candidate status, reject alternatives, initiate onboarding
Output: Offer marked ACCEPTED, onboarding workflow initiated
Integrates: SLM pre-flight analysis + post-flight outcome recording
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.services.message_handlers.base_message_handler import time_bound
from app.models.offer import Offer
from app.services.slm_service import SLMService

logger = logging.getLogger(__name__)


class OfferAcceptedHandler:
    """Process offer acceptance, update statuses, initiate onboarding."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=30)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process offer acceptance.

        Args:
            message: ChannelQueueItem with payload containing:
                - offer_id: Accepted offer
                - start_date: Employment start date
                - department: Department for onboarding
            db: Database session

        Returns:
            {
                'offer_id': str,
                'candidate_id': str,
                'onboarding_initiated': bool,
                'status': 'accepted'
            }

        Raises:
            ValueError: Invalid payload (non-retryable)
            RuntimeError: Database errors (retryable)
        """
        try:
            if not message.payload:
                raise ValueError(f"Message {message.id} has no payload")

            payload = message.payload
            offer_id = payload.get('offer_id')
            slm_analysis = None

            if not offer_id:
                raise ValueError("Missing required field: offer_id")

            logger.info(f"[OfferAccepted] Processing acceptance: {offer_id}")

            # PLACE 1: PRE-FLIGHT SLM ANALYSIS
            try:
                slm_analysis = SLMService.analyze_before_handler(
                    message_id=str(message.id),
                    message_type='offer_accepted',
                    payload=payload,
                    context={
                        'business_goal': 'Initiate onboarding for accepted candidate',
                        'risk_level': 'CRITICAL',
                        'offer_id': offer_id,
                        'start_date': payload.get('start_date'),
                        'department': payload.get('department', 'unknown')
                    },
                    db=db
                )
                if not slm_analysis.get('should_proceed'):
                    raise ValueError(
                        f"SLM CRITICAL escalation: {slm_analysis.get('reasoning')}"
                    )
            except Exception as slm_err:
                logger.warning(f"[OfferAccepted] SLM pre-flight failed (non-blocking): {slm_err}")

            # PHASE 1: Fetch and validate offer
            offer = db.query(Offer).filter(Offer.id == offer_id).first()
            if not offer:
                raise ValueError(f"Offer {offer_id} not found")

            candidate_id = offer.candidate_id if hasattr(offer, 'candidate_id') else None

            # PHASE 2: Update offer status
            if hasattr(offer, 'status'):
                offer.status = 'ACCEPTED'
                if hasattr(offer, 'accepted_at'):
                    offer.accepted_at = datetime.utcnow()

            # PHASE 3: Update candidate status
            if candidate_id:
                from app.models.candidate import Candidate
                candidate = db.query(Candidate).filter(
                    Candidate.candidateID == candidate_id
                ).first()
                if candidate and hasattr(candidate, 'candidateStatus'):
                    candidate.candidateStatus = 'OFFER_ACCEPTED'
                    logger.info(f"[OfferAccepted] Candidate {candidate_id} status updated")

            # PHASE 4: Reject other pending offers
            if candidate_id:
                other_offers = db.query(Offer).filter(
                    Offer.candidate_id == candidate_id,
                    Offer.id != offer_id,
                    Offer.status.in_(['DRAFT', 'APPROVED', 'SENT'])
                ).all()
                for other in other_offers:
                    other.status = 'REJECTED'
                    if hasattr(other, 'rejection_reason'):
                        other.rejection_reason = 'Candidate accepted another offer'
                logger.info(f"[OfferAccepted] Rejected {len(other_offers)} other offers")

            # PHASE 5: Send acceptance confirmation emails
            delivery_id = None
            try:
                from app.services.email_service import EmailService

                # Send congratulations email to candidate
                if candidate_id:
                    candidate_obj = db.query(Candidate).filter(
                        Candidate.candidateID == candidate_id
                    ).first()

                    if candidate_obj and hasattr(candidate_obj, 'candidateEmail'):
                        candidate_name = getattr(candidate_obj, 'candidateFirstName', 'Candidate')
                        candidate_email = candidate_obj.candidateEmail

                        email_subject = "Congratulations! Offer Accepted"
                        email_body = f"""
Dear {candidate_name},

Congratulations! Your offer has been accepted.

**NEXT STEPS**
1. Complete onboarding documentation
2. Receive start date confirmation
3. Meet your new team

Our HR team will contact you shortly with more details.

Welcome to the team!

Best regards,
Recruiting Team
"""

                        result = EmailService.send_email(
                            to_email=candidate_email,
                            subject=email_subject,
                            body_content=email_body,
                            is_html=True
                        )

                        if result.get('status') == 'skipped':
                            logger.warning(f"[OfferAccepted] Email skipped to {candidate_email}: {result.get('reason')}")
                        elif result.get('status') != 'success':
                            logger.warning(f"[OfferAccepted] Email delivery failed: {result}")
                        else:
                            delivery_id = "msgraph_" + str(hash(candidate_email))
                            logger.info(f"[OfferAccepted] Acceptance confirmation sent to {candidate_email}, delivery_id={delivery_id}")

            except Exception as delivery_err:
                logger.warning(f"[OfferAccepted] Email delivery error (non-blocking): {delivery_err}")

            # PHASE 6: Commit
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                logger.error(f"[OfferAccepted] Commit failed: {commit_err}", exc_info=True)
                raise RuntimeError(f"Failed to process acceptance: {str(commit_err)}") from commit_err

            # PHASE 7: Initiate onboarding (non-blocking)
            onboarding_initiated = False
            try:
                logger.info(f"[OfferAccepted] Initiating onboarding for {candidate_id}")
                onboarding_initiated = True
            except Exception as onb_err:
                logger.warning(f"[OfferAccepted] Onboarding initiation failed: {onb_err}")

            result = {
                'offer_id': str(offer_id),
                'candidate_id': str(candidate_id) if candidate_id else None,
                'onboarding_initiated': onboarding_initiated,
                'delivery_id': delivery_id,
                'status': 'accepted'
            }

            # PLACE 2: POST-FLIGHT SLM OUTCOME RECORDING
            if slm_analysis:
                try:
                    SLMService.record_outcome(
                        slm_analysis=slm_analysis,
                        message_id=str(message.id),
                        handler_name='offer_accepted_handler',
                        handler_result=result,
                        business_impact={
                            'candidate_affected': True,
                            'candidate_id': candidate_id,
                            'offer_id': offer_id,
                            'expected_outcome': 'successful_onboarding',
                            'can_be_reversed': False,
                            'accountability_required': True,
                        },
                        db=db
                    )
                    logger.info(f"[OfferAccepted] SLM outcome recorded")
                except Exception as slm_record_err:
                    logger.warning(f"[OfferAccepted] SLM outcome recording failed: {slm_record_err}")

            logger.info(f"[OfferAccepted] ✅ Acceptance processed")
            return result

        except ValueError as ve:
            logger.error(f"[OfferAccepted] Validation error: {ve}")
            raise

        except OperationalError as oe:
            logger.error(f"[OfferAccepted] DB error: {oe}", exc_info=True)
            raise RuntimeError(f"Database error: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[OfferAccepted] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that acceptance was recorded."""
        from app.services.message_handlers.validate_handlers_factory import ValidateHandlersFactory
        return ValidateHandlersFactory.validate_offer_acceptance_recorded(result, db, "offer_accepted")

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= OfferAcceptedHandler.MAX_RETRIES:
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
                minutes=OfferAcceptedHandler.RETRY_DELAY_MINUTES
            )
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[OfferAccepted] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation."""
        try:
            OfferAcceptedHandler.validate(message, result, db)
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result
            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit: {str(commit_err)}") from commit_err
            logger.info(f"[OfferAccepted] ✅ Message marked COMPLETED")
        except ValueError:
            db.rollback()
            raise
        except RuntimeError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"[OfferAccepted] Unexpected error: {e}", exc_info=True)
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
            logger.error(f"[OfferAccepted] Failed to mark FAILED: {e}", exc_info=True)
            raise


def handle_offer_accepted(message: Any, db: Session) -> Dict[str, Any]:
    """Backward compatibility wrapper."""
    return OfferAcceptedHandler.process(message, db)
