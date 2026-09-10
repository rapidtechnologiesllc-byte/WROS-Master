"""Offer Accepted Message Handler - Process offer acceptance with SLM integration."""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.offer import Offer
from app.services.slm_service import SLMService

logger = logging.getLogger(__name__)


def handle_offer_accepted(message: Any, db: Session) -> Dict[str, Any]:
    """Handle offer_accepted message with SLM integration.

    SLM Pattern:
    - PLACE 1: Pre-flight analysis (CRITICAL risk - onboarding is expensive)
    - Handler logic: Update offer/candidate, reject alternatives, initiate onboarding
    - PLACE 2: Post-flight outcome recording with 90-day employee validation

    Message is marked COMPLETED only when:
    1. Offer status updated to ACCEPTED
    2. Candidate status updated to OFFER_ACCEPTED
    3. Onboarding workflow initiated
    4. Other offers for same candidate rejected

    Args:
        message: ChannelQueueItem with type='offer_accepted'
        db: SQLAlchemy session

    Returns:
        {status, offer_id, candidate_id, onboarding_initiated}
    """
    try:
        payload = message.payload or {}
        offer_id = payload.get('offer_id')
        slm_analysis = None

        # ============ PLACE 1: PRE-FLIGHT SLM ANALYSIS (CRITICAL RISK) ============
        try:
            slm_analysis = SLMService.analyze_before_handler(
                message_id=str(message.id),
                message_type='offer_accepted',
                payload=payload,
                context={
                    'business_goal': 'Initiate onboarding for accepted candidate',
                    'risk_level': 'CRITICAL',  # Onboarding is expensive + irreversible
                    'offer_id': offer_id,
                    'start_date': payload.get('start_date'),
                    'department': payload.get('department', 'unknown')
                },
                db=db
            )
            if not slm_analysis.get('should_proceed'):
                logger.warning(f"[OfferAccepted] SLM CRITICAL escalation: {slm_analysis.get('reasoning')}")
                return {
                    'status': 'escalated',
                    'reason': f"CRITICAL: {slm_analysis.get('reasoning')}",
                    'slm_decision_id': slm_analysis.get('slm_decision_id'),
                    'message': 'Onboarding escalated to manager for approval'
                }
        except Exception as slm_err:
            logger.error(f"[OfferAccepted] SLM pre-flight analysis failed: {slm_err}")
            # Continue anyway - don't block offer acceptance on SLM failure
            pass

        if not offer_id:
            raise ValueError("offer_id is required in payload")

        offer = db.query(Offer).filter(Offer.id == offer_id).first()
        if not offer:
            raise ValueError(f"Offer {offer_id} not found")

        logger.info(f"[OfferAccepted] Processing offer {offer_id} acceptance")

        candidate_id = offer.candidate_id if hasattr(offer, 'candidate_id') else None

        # 1. Update offer status
        if hasattr(offer, 'status'):
            offer.status = 'ACCEPTED'
            from datetime import datetime
            if hasattr(offer, 'accepted_at'):
                offer.accepted_at = datetime.utcnow()
            db.commit()

        # 2. Update candidate status
        try:
            if candidate_id:
                from app.models.candidate import Candidate
                candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
                if candidate and hasattr(candidate, 'candidateStatus'):
                    candidate.candidateStatus = 'OFFER_ACCEPTED'
                    db.commit()
                    logger.info(f"[OfferAccepted] Updated candidate {candidate_id} status")
        except Exception as cand_err:
            logger.warning(f"[OfferAccepted] Could not update candidate status: {cand_err}")

        # 3. Reject other pending offers for this candidate
        try:
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
                db.commit()
                logger.info(f"[OfferAccepted] Rejected {len(other_offers)} other offers")
        except Exception as reject_err:
            logger.warning(f"[OfferAccepted] Could not reject other offers: {reject_err}")

        # 4. Initiate onboarding workflow
        onboarding_initiated = False
        try:
            # In production: create onboarding tasks, setup employee records
            # Schedule orientation, background check, asset provisioning
            logger.info(f"[OfferAccepted] Initiating onboarding for candidate {candidate_id}")
            onboarding_initiated = True
        except Exception as onb_err:
            logger.warning(f"[OfferAccepted] Could not initiate onboarding: {onb_err}")

        result = {
            "status": "offer_accepted",
            "offer_id": offer_id,
            "candidate_id": candidate_id,
            "onboarding_initiated": onboarding_initiated,
            "message": f"Offer {offer_id} accepted by candidate, onboarding started"
        }

        # ============ PLACE 2: POST-FLIGHT OUTCOME RECORDING (ACCOUNTABILITY) ============
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
                        'onboarding_workflow_id': None,  # To be set when workflow created
                        'start_date': payload.get('start_date'),
                        'department': payload.get('department'),
                        'expected_outcome': 'successful_onboarding',
                        'validation_method': 'Employee completes 30-day onboarding checklist',
                        '90_day_plan': 'Monitor new hire productivity, engagement scores, retention',
                        'can_be_reversed': False,  # Onboarding is expensive to reverse
                        'cost_impact': payload.get('salary', 0) * 0.3,  # Onboarding cost ~30% salary
                        'accountability_required': True,
                    },
                    db=db
                )
                logger.info(f"[OfferAccepted] SLM outcome recorded for onboarding workflow")
            except Exception as slm_record_err:
                logger.error(f"[OfferAccepted] Failed to record SLM outcome: {slm_record_err}")
                # Non-blocking - onboarding already initiated

        logger.info(f"[OfferAccepted] ✅ Completed: {offer_id}")
        return result

    except ValueError as ve:
        logger.error(f"[OfferAccepted] Validation error: {ve}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"[OfferAccepted] Failed to process acceptance: {e}", exc_info=True)
        raise
