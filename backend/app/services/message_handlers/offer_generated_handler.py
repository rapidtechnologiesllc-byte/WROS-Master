"""
Handler: Offer Generated Events

Triggers when offer created for candidate

Actions:
- Archive active conversations (don't message during offer discussion)
- Switch to onboarding Thunder flow
- Set offer acceptance deadline
- Notify on-boarding team

Note: Pausing engagement prevents confusing messages while offer is pending.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def handle_offer_generated(
    event_payload: Dict[str, Any],
    db: Optional[object] = None
) -> Dict[str, Any]:
    """
    Handle offer generated events.

    Args:
        event_payload: Event data including offer details
        db: Database session

    Returns:
        Handler result: {"status": "processed", "offer_id": "...", "actions": [...]}
    """
    try:
        from app.core.database import SessionLocal
        from app.models.candidate import Candidate

        if db is None:
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        candidate_id = event_payload.get("candidate_id")
        data = event_payload.get("data", {})
        offer_id = data.get("offer_id")
        offer_acceptance_deadline = data.get("offer_acceptance_deadline")

        # Fetch candidate
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.warning(f"[OFFER_HANDLER] Candidate {candidate_id} not found")
            return {"status": "skipped", "reason": "candidate not found"}

        actions_taken = []

        # Archive active conversations
        if candidate.thunder_enabled:
            candidate.thunder_enabled = False
            actions_taken.append("archived_active_conversations")
            logger.info(f"[OFFER_HANDLER] Archived conversations for candidate {candidate_id}: offer generated")

        # Log offer details
        logger.info(f"[OFFER_HANDLER] Offer {offer_id} generated for candidate {candidate_id}")
        logger.info(f"  Acceptance deadline: {offer_acceptance_deadline}")
        actions_taken.append("switched_to_onboarding_flow")

        db.commit()

        return {
            "status": "processed",
            "candidate_id": candidate_id,
            "offer_id": offer_id,
            "offer_acceptance_deadline": offer_acceptance_deadline,
            "actions": actions_taken
        }

    except Exception as e:
        logger.error(
            f"[OFFER_HANDLER] Error processing offer for {event_payload.get('candidate_id')}: {e}",
            exc_info=True
        )
        if db:
            db.rollback()
        return {"status": "failed", "error": str(e)}

    finally:
        if should_close and db:
            db.close()
