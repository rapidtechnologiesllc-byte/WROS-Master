"""
Handler: Interview Scheduled Events

Triggers when interview created for candidate

Actions:
- Notify Thunder: Candidate advanced, pause other outreach
- Sync interview context to Thunder conversation (date, time, panel)
- Add briefing notes for panel (from Thunder analysis)
- Set interview reminder

Note: Pausing other outreach prevents candidate from getting multiple offers.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def handle_interview_scheduled(
    event_payload: Dict[str, Any],
    db: Optional[object] = None
) -> Dict[str, Any]:
    """
    Handle interview scheduled events.

    Args:
        event_payload: Event data including interview details
        db: Database session

    Returns:
        Handler result: {"status": "processed", "interview_id": "...", "actions": [...]}
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
        interview_id = data.get("interview_id")
        interview_date = data.get("interview_date")
        interview_panel = data.get("interview_panel", [])

        # Fetch candidate
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.warning(f"[INTERVIEW_HANDLER] Candidate {candidate_id} not found")
            return {"status": "skipped", "reason": "candidate not found"}

        actions_taken = []

        # Pause other outreach
        if candidate.thunder_enabled:
            candidate.thunder_enabled = False
            actions_taken.append("paused_other_outreach")
            logger.info(f"[INTERVIEW_HANDLER] Paused Thunder for candidate {candidate_id}: interview scheduled")

        # Log briefing context for panel
        logger.info(f"[INTERVIEW_HANDLER] Interview {interview_id} scheduled for {candidate_id}")
        logger.info(f"  Interview date: {interview_date}")
        logger.info(f"  Panel members: {', '.join(interview_panel)}")
        actions_taken.append("logged_interview_context")

        db.commit()

        return {
            "status": "processed",
            "candidate_id": candidate_id,
            "interview_id": interview_id,
            "interview_date": interview_date,
            "actions": actions_taken
        }

    except Exception as e:
        logger.error(
            f"[INTERVIEW_HANDLER] Error processing interview for {event_payload.get('candidate_id')}: {e}",
            exc_info=True
        )
        if db:
            db.rollback()
        return {"status": "failed", "error": str(e)}

    finally:
        if should_close and db:
            db.close()
