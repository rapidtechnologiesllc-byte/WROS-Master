"""
Handler: Candidate Created Events

Triggers when new candidate enters system

Actions:
- Assign to Thunder autonomous agent (auto-qualification)
- Schedule first outreach message
- Set initial Thunder engagement parameters
- Log candidate entry

Note: Every new candidate automatically enters Thunder flow for qualification.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def handle_candidate_created(
    event_payload: Dict[str, Any],
    db: Optional[object] = None
) -> Dict[str, Any]:
    """
    Handle candidate creation events.

    Args:
        event_payload: Event data including candidate details
        db: Database session

    Returns:
        Handler result: {"status": "processed", "assigned_to_thunder": true}
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
            logger.warning(f"[CREATED_HANDLER] Candidate {candidate_id} not found")
            return {"status": "skipped", "reason": "candidate not found"}

        actions_taken = []

        # Ensure Thunder is enabled (default for new candidates)
        if not candidate.thunder_enabled:
            candidate.thunder_enabled = True
            actions_taken.append("enabled_thunder_engagement")

        logger.info(f"[CREATED_HANDLER] New candidate {candidate_id} entered Thunder autonomous flow")
        logger.info(f"  Email: {candidate.candidateEmail}")
        logger.info(f"  Name: {candidate.candidateFirstName} {candidate.candidateLastName}")
        actions_taken.append("assigned_to_thunder")

        db.commit()

        return {
            "status": "processed",
            "candidate_id": candidate_id,
            "assigned_to_thunder": True,
            "actions": actions_taken
        }

    except Exception as e:
        logger.error(
            f"[CREATED_HANDLER] Error processing candidate creation {event_payload.get('candidate_id')}: {e}",
            exc_info=True
        )
        if db:
            db.rollback()
        return {"status": "failed", "error": str(e)}

    finally:
        if should_close and db:
            db.close()
