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

        # PHASE 1: Fetch candidate
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.warning(f"[INTERVIEW_HANDLER] Candidate {candidate_id} not found")
            return {"status": "skipped", "reason": "candidate not found"}

        # PHASE 2: Extract interview details
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        meeting_link = data.get("meeting_link")
        panel_id = data.get("panel_id")

        actions_taken = []

        # PHASE 3: Create Interview record in database (PHASE A FIX #2)
        try:
            from app.models.user import Interview

            interview = Interview(
                candidate_id=candidate_id,
                panel_id=panel_id,
                start_time=start_time,
                end_time=end_time,
                meeting_link=meeting_link,
                status="Scheduled",
                feedback_status="Pending"
            )
            db.add(interview)
            db.flush()  # Get interview.id before commit
            created_interview_id = interview.id
            actions_taken.append("created_interview_record")
            logger.info(f"[INTERVIEW_HANDLER] Interview record created: {created_interview_id}")
        except Exception as create_err:
            logger.error(f"[INTERVIEW_HANDLER] Failed to create interview: {create_err}")
            raise

        # PHASE 4: Pause Thunder outreach for this candidate
        if candidate.thunder_enabled:
            candidate.thunder_enabled = False
            actions_taken.append("paused_thunder_outreach")
            logger.info(f"[INTERVIEW_HANDLER] Paused Thunder for candidate {candidate_id}")

        # PHASE 5: Queue Thunder notification (prevent duplicate outreach during interview)
        try:
            from app.services.message_queue_service import MessageQueueService

            MessageQueueService.enqueue(
                task_name='interview_scheduled_pause_thunder',
                task_id=f"interview_pause_{created_interview_id}",
                data={
                    'candidate_id': candidate_id,
                    'interview_id': created_interview_id,
                    'reason': f'Interview scheduled for {interview_date}',
                    'pause_until': interview_date
                }
            )
            actions_taken.append("queued_thunder_notification")
            logger.info(f"[INTERVIEW_HANDLER] Thunder pause notification queued")
        except Exception as queue_err:
            logger.warning(f"[INTERVIEW_HANDLER] Failed to queue Thunder notification: {queue_err}")
            # Non-blocking - interview already created

        # PHASE 6: Commit transaction
        db.commit()

        return {
            "status": "processed",
            "candidate_id": candidate_id,
            "interview_id": created_interview_id,
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
