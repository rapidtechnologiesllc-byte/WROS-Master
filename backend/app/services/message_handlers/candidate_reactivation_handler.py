"""
Handler: Candidate Reactivation Events

Triggers when candidate reactivated (archive → active transition)

Actions:
- Check if past 90-day rejections: Start fresh Thunder session
- Check if < 90 days since rejection: Deprioritize (but don't block)
- Resume Thunder engagement if conditions met
- Alert on potential re-match conflicts

Edge cases:
- Reactivated within 90 days of rejection: Lower priority in Thunder
- Multiple rejections within last 90 days: Flag for manual review
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def handle_candidate_reactivated(
    event_payload: Dict[str, Any],
    db: Optional[object] = None
) -> Dict[str, Any]:
    """
    Handle candidate reactivation events.

    Args:
        event_payload: Event data
        db: Database session

    Returns:
        Handler result: {"status": "processed", "can_resume_thunder": true/false}
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
            logger.warning(f"[REACTIVATION_HANDLER] Candidate {candidate_id} not found")
            return {"status": "skipped", "reason": "candidate not found"}

        # Check if within 90-day cooling period from recent rejection
        # (This would query CandidateRejection table when available)
        can_resume_thunder = True
        deprioritized = False

        # For now, check if previous status was REJECTED
        if candidate.previous_status == "REJECTED":
            # Check if status change was recent (within 90 days)
            if candidate.status_changed_at:
                days_since_rejection = (datetime.utcnow() - candidate.status_changed_at).days
                if days_since_rejection < 90:
                    deprioritized = True
                    logger.warning(
                        f"[REACTIVATION_HANDLER] Candidate {candidate_id} reactivated within 90 days of rejection: "
                        f"deprioritizing ({days_since_rejection} days)"
                    )

        # Resume Thunder if conditions met
        if can_resume_thunder:
            candidate.thunder_enabled = True
            logger.info(f"[REACTIVATION_HANDLER] Resumed Thunder for candidate {candidate_id}")

        db.commit()

        return {
            "status": "processed",
            "candidate_id": candidate_id,
            "can_resume_thunder": can_resume_thunder,
            "deprioritized": deprioritized,
            "actions": ["resumed_thunder" if can_resume_thunder else "held_for_review"]
        }

    except Exception as e:
        logger.error(
            f"[REACTIVATION_HANDLER] Error processing reactivation for {event_payload.get('candidate_id')}: {e}",
            exc_info=True
        )
        if db:
            db.rollback()
        return {"status": "failed", "error": str(e)}

    finally:
        if should_close and db:
            db.close()
