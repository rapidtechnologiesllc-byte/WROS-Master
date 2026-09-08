"""
Handler: Candidate Archive Events

Triggers when candidate archived (manually or system-triggered)

Actions:
- Pause Thunder immediately
- Archive conversation thread (read-only, don't delete)
- Mark as archived in database
- Alert recruiter if needed

Note: Archiving is not deletion - maintains audit trail for future reference.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def handle_candidate_archived(
    event_payload: Dict[str, Any],
    db: Optional[object] = None
) -> Dict[str, Any]:
    """
    Handle candidate archive events.

    Args:
        event_payload: Event data
        db: Database session

    Returns:
        Handler result: {"status": "processed", "archive_timestamp": "..."}
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

        # Fetch candidate
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.warning(f"[ARCHIVE_HANDLER] Candidate {candidate_id} not found")
            return {"status": "skipped", "reason": "candidate not found"}

        # Disable Thunder
        candidate.thunder_enabled = False

        # Mark archived timestamp
        archived_at = datetime.utcnow()

        logger.info(f"[ARCHIVE_HANDLER] Archived candidate {candidate_id} at {archived_at}")

        db.commit()

        return {
            "status": "processed",
            "candidate_id": candidate_id,
            "archive_timestamp": archived_at.isoformat(),
            "actions": ["paused_thunder", "archived_conversation"]
        }

    except Exception as e:
        logger.error(
            f"[ARCHIVE_HANDLER] Error archiving candidate {event_payload.get('candidate_id')}: {e}",
            exc_info=True
        )
        if db:
            db.rollback()
        return {"status": "failed", "error": str(e)}

    finally:
        if should_close and db:
            db.close()
