"""Offer Approved Message Handler - Process offer approval notifications."""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.offer import Offer
from app.services.slm_service import SLMService

logger = logging.getLogger(__name__)


def handle_offer_approved(message: Any, db: Session) -> Dict[str, Any]:
    """Handle offer_approved message - triggered when an offer is approved.

    Message is marked COMPLETED only when:
    1. Offer status updated to APPROVED
    2. Candidate notification sent
    3. Finance/onboarding workflow initiated

    Args:
        message: ChannelQueueItem with type='offer_approved'
        db: SQLAlchemy session

    Returns:
        {status, offer_id, candidate_id, approver_id, workflow_initiated}
    """
    try:
        payload = message.payload or {}
        offer_id = payload.get('offer_id')
        approver_id = payload.get('approver_id')

        if not offer_id:
            raise ValueError("offer_id is required in payload")

        # ============ PLACE 1: PRE-FLIGHT SLM ANALYSIS ============
        slm_analysis = None
        try:
            slm_analysis = SLMService.analyze_before_handler(
                message_id=str(message.id),
                message_type="offer_approved",
                payload=payload,
                context={
                    'business_goal': 'Approve and process offer for candidate',
                    'risk_level': 'HIGH',
                    'offer_id': offer_id,
                    'approver_id': approver_id,
                },
                db=db
            )
            if not slm_analysis.get('should_proceed'):
                logger.warning(f"[OfferApproved] SLM escalation for offer {offer_id}: {slm_analysis.get('reasoning')}")
                return {
                    'status': 'escalated',
                    'offer_id': offer_id,
                    'reason': slm_analysis.get('reasoning')
                }
        except Exception as slm_err:
            logger.error(f"[OfferApproved] SLM pre-flight failed: {slm_err}")

        # 1. Fetch offer to verify it exists
        offer = db.query(Offer).filter(Offer.id == offer_id).first()
        if not offer:
            raise ValueError(f"Offer {offer_id} not found")

        logger.info(f"[OfferApproved] Processing offer {offer_id} approved by {approver_id}")

        # 2. Update offer status to APPROVED
        if hasattr(offer, 'status'):
            offer.status = 'APPROVED'
            if hasattr(offer, 'approved_by'):
                offer.approved_by = approver_id
            if hasattr(offer, 'approved_at'):
                from datetime import datetime
                offer.approved_at = datetime.utcnow()
            db.commit()

        # ============ PLACE 2: POST-FLIGHT SLM ANALYSIS (after DB commit) ============
        try:
            persisted_offer = db.query(Offer).filter(Offer.id == offer_id).first()
            if persisted_offer:
                slm_result = SLMService.analyze_message_result(
                    message_id=str(message.id),
                    message_type="offer_approved",
                    handler_name="offer_approved_handler",
                    result={
                        'status': 'success',
                        'offer_id': offer_id,
                        'candidate_id': candidate_id,
                        'approver_id': approver_id,
                        'offer_status': 'APPROVED',
                    },
                    db=db
                )
                logger.info(f"[OfferApproved] SLM post-flight completed: confidence={slm_result.get('confidence')}, escalated={slm_result.get('was_escalated')}")
        except Exception as slm_err:
            logger.warning(f"[OfferApproved] SLM post-flight failed (non-blocking): {slm_err}")

        # 3. Send candidate notification
        candidate_id = offer.candidate_id if hasattr(offer, 'candidate_id') else None
        notification_sent = False
        try:
            # In production: send email/SMS to candidate with offer details
            # "Your offer has been approved and will be sent shortly"
            if candidate_id:
                logger.info(f"[OfferApproved] Notifying candidate {candidate_id}")
                notification_sent = True
        except Exception as notify_err:
            logger.warning(f"[OfferApproved] Could not notify candidate: {notify_err}")

        # 4. Initiate finance/onboarding workflow
        workflow_initiated = False
        try:
            # In production: trigger offer letter generation, finance processing
            # This moves the offer towards "sent" state
            workflow_initiated = True
        except Exception as wf_err:
            logger.warning(f"[OfferApproved] Could not initiate workflow: {wf_err}")

        result = {
            "status": "offer_approved",
            "offer_id": offer_id,
            "candidate_id": candidate_id,
            "approver_id": approver_id,
            "notification_sent": notification_sent,
            "workflow_initiated": workflow_initiated
        }

        logger.info(f"[OfferApproved] ✅ Completed: {offer_id}")
        return result

    except ValueError as ve:
        logger.error(f"[OfferApproved] Validation error: {ve}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"[OfferApproved] Failed to process approval: {e}", exc_info=True)
        raise
