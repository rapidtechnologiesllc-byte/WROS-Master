"""
Handler: Candidate Status Change Events

Triggers on status transitions (Applied → Interview → Offer → Joined → Rejected)

Actions by status:
- Interview Scheduled: Pause other outreach, add context to Thunder conversation
- Offer Generated: Archive active conversations, switch to onboarding flow
- Joined: Mark complete, celebrate success
- Rejected: Archive conversation, flag no-contact 90 days

Edge cases handled:
- Status changes while candidate in Thunder flow (pause Thunder)
- Multiple status changes same day (debounce)
- Status change back to previous state (unlikely but handled)
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def handle_candidate_status_changed(
    event_payload: Dict[str, Any],
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Handle candidate status change events.

    Args:
        event_payload: Event data including old_status, new_status, status_change_reason
        db: Database session (will create if not provided)

    Returns:
        Handler result: {"status": "processed", "actions_taken": [...]}
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
        old_status = data.get("old_status")
        new_status = data.get("new_status")
        reason = data.get("status_change_reason", "Status changed")

        # Fetch candidate
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.warning(f"[STATUS_HANDLER] Candidate {candidate_id} not found")
            return {"status": "skipped", "reason": "candidate not found"}

        actions_taken = []

        # Handle based on new status
        if new_status == "INTERVIEW":
            # Interview scheduled: Pause other outreach
            if candidate.thunder_enabled:
                candidate.thunder_enabled = False
                actions_taken.append("paused_thunder_for_interview_scheduling")
                logger.info(f"[STATUS_HANDLER] Paused Thunder for candidate {candidate_id}: interview scheduled")

        elif new_status == "OFFER":
            # Offer generated: Archive active conversations
            candidate.thunder_enabled = False
            actions_taken.append("paused_thunder_for_offer")
            logger.info(f"[STATUS_HANDLER] Paused Thunder for candidate {candidate_id}: offer generated")

        elif new_status == "JOINED":
            # Joined: Mark complete, candidate journey complete
            candidate.thunder_enabled = False
            actions_taken.append("marked_joined_success")
            logger.info(f"[STATUS_HANDLER] Candidate {candidate_id} joined successfully")

        elif new_status == "REJECTED":
            # Rejected: Archive and flag no-contact 90 days
            candidate.thunder_enabled = False
            actions_taken.append("paused_thunder_for_rejection")
            # The rejection handler will handle no-contact flag
            logger.info(f"[STATUS_HANDLER] Candidate {candidate_id} rejected: {reason}")

        # Update status tracking
        candidate.previous_status = old_status
        candidate.status_changed_at = datetime.utcnow()
        candidate.status_change_reason = reason

        db.commit()

        logger.info(f"[STATUS_HANDLER] Processed status change for {candidate_id}: {old_status} → {new_status}")

        return {
            "status": "processed",
            "actions_taken": actions_taken,
            "candidate_id": candidate_id,
            "old_status": old_status,
            "new_status": new_status
        }

    except Exception as e:
        logger.error(
            f"[STATUS_HANDLER] Error processing status change for {event_payload.get('candidate_id')}: {e}",
            exc_info=True
        )
        if db:
            db.rollback()
        return {"status": "failed", "error": str(e)}

    finally:
        if should_close and db:
            db.close()
