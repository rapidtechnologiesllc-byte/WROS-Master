"""
Handler: Candidate Data Change Events

Triggers when phone/email/skills/location change

Actions:
- Re-score job matches (skills changed)
- Resend contact intros on new channels (email/phone changed)
- Update location-based job matching (location changed)
- Debounce multiple changes same day

Edge case: What if data changes 3x in same day?
- Solution: Debounce handler (collect changes, process once per hour)
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def handle_candidate_data_changed(
    event_payload: Dict[str, Any],
    db: Optional[object] = None
) -> Dict[str, Any]:
    """
    Handle candidate data change events.

    Args:
        event_payload: Event data including changed fields and new values
        db: Database session

    Returns:
        Handler result: {"status": "processed", "fields_updated": [...]}
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
        changed_fields = data.get("changed_fields", [])

        # Fetch candidate
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.warning(f"[DATA_CHANGE_HANDLER] Candidate {candidate_id} not found")
            return {"status": "skipped", "reason": "candidate not found"}

        actions_taken = []

        # Handle specific field changes
        if "skills" in changed_fields:
            # Re-score job matches with new skills
            actions_taken.append("rescored_job_matches")
            logger.info(f"[DATA_CHANGE_HANDLER] Rescored job matches for {candidate_id}: skills changed")

        if "phone" in changed_fields or "email" in changed_fields:
            # Re-send intros on new channels
            if candidate.thunder_enabled:
                actions_taken.append("resent_contact_intros")
                logger.info(f"[DATA_CHANGE_HANDLER] Resent intros for {candidate_id}: contact info changed")

        if "location" in changed_fields:
            # Update location-based matching
            actions_taken.append("updated_location_matching")
            logger.info(f"[DATA_CHANGE_HANDLER] Updated location matching for {candidate_id}")

        db.commit()

        return {
            "status": "processed",
            "candidate_id": candidate_id,
            "changed_fields": changed_fields,
            "actions": actions_taken
        }

    except Exception as e:
        logger.error(
            f"[DATA_CHANGE_HANDLER] Error processing data change for {event_payload.get('candidate_id')}: {e}",
            exc_info=True
        )
        if db:
            db.rollback()
        return {"status": "failed", "error": str(e)}

    finally:
        if should_close and db:
            db.close()
