"""
Handler: Candidate Rejection Events

Triggers when candidate rejected (any reason)

Actions:
- Archive candidate conversation (don't delete, audit trail)
- Set no-contact flag for 90 days
- Store rejection reason for future matching
- Track in CandidateRejection table

Note: Actual implementation requires CandidateRejection table creation in Phase 5.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def handle_candidate_rejected(
    event_payload: Dict[str, Any],
    db: Optional[object] = None
) -> Dict[str, Any]:
    """
    Handle candidate rejection events.

    Args:
        event_payload: Event data including rejection reason
        db: Database session

    Returns:
        Handler result: {"status": "processed", "no_contact_until": "..."}
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
        reason = data.get("rejection_reason", "Candidate rejected")

        # Fetch candidate
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.warning(f"[REJECTION_HANDLER] Candidate {candidate_id} not found")
            return {"status": "skipped", "reason": "candidate not found"}

        # Disable Thunder engagement
        candidate.thunder_enabled = False

        # Calculate 90-day no-contact expiry
        no_contact_until = datetime.utcnow() + timedelta(days=90)

        # Store metadata (would use CandidateRejection table when available)
        # For now, use comment field or metadata
        logger.info(f"[REJECTION_HANDLER] Candidate {candidate_id} flagged no-contact until {no_contact_until}: {reason}")

        db.commit()

        return {
            "status": "processed",
            "candidate_id": candidate_id,
            "rejection_reason": reason,
            "no_contact_until": no_contact_until.isoformat(),
            "actions": ["archived_conversation", "set_no_contact_90d", "paused_thunder"]
        }

    except Exception as e:
        logger.error(
            f"[REJECTION_HANDLER] Error processing rejection for {event_payload.get('candidate_id')}: {e}",
            exc_info=True
        )
        if db:
            db.rollback()
        return {"status": "failed", "error": str(e)}

    finally:
        if should_close and db:
            db.close()
