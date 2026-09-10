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
    Handle interview scheduled events with SLM integration.

    SLM Pattern:
    - PLACE 1: Pre-flight analysis before handler logic
    - Handler logic: Create interview record, pause Thunder
    - PLACE 2: Post-flight outcome recording with business impact

    Args:
        event_payload: Event data including interview details
        db: Database session

    Returns:
        Handler result: {"status": "processed", "interview_id": "...", "actions": [...]}
    """
    try:
        from app.core.database import SessionLocal
        from app.models.candidate import Candidate
        from app.services.slm_service import SLMService

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

        # ============ PLACE 1: PRE-FLIGHT SLM ANALYSIS ============
        message_id = event_payload.get("message_id", "unknown")
        slm_analysis = None
        try:
            slm_analysis = SLMService.analyze_before_handler(
                message_id=message_id,
                message_type='interview_scheduled',
                payload=event_payload,
                context={
                    'business_goal': f'Schedule interview for candidate {candidate_id}',
                    'risk_level': 'MEDIUM',
                    'candidate_id': candidate_id,
                    'interview_date': interview_date,
                    'panel_size': len(interview_panel)
                },
                db=db
            )
            if not slm_analysis.get('should_proceed'):
                logger.warning(f"[INTERVIEW_HANDLER] SLM escalation: {slm_analysis.get('reasoning')}")
                return {
                    'status': 'escalated',
                    'reason': slm_analysis.get('reasoning'),
                    'slm_decision_id': slm_analysis.get('slm_decision_id')
                }
        except Exception as slm_err:
            logger.error(f"[INTERVIEW_HANDLER] SLM pre-flight analysis failed: {slm_err}")
            # Continue anyway - don't block interview scheduling on SLM failure
            pass

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

        # ============ PLACE 2: POST-FLIGHT OUTCOME RECORDING ============
        handler_result = {
            "status": "processed",
            "candidate_id": candidate_id,
            "interview_id": created_interview_id,
            "interview_date": interview_date,
            "actions": actions_taken
        }

        if slm_analysis:
            try:
                SLMService.record_outcome(
                    slm_analysis=slm_analysis,
                    message_id=message_id,
                    handler_name='interview_scheduled_handler',
                    handler_result=handler_result,
                    business_impact={
                        'candidate_affected': True,
                        'candidate_id': candidate_id,
                        'interview_id': created_interview_id,
                        'interview_date': interview_date,
                        'position_id': getattr(candidate, 'position_id', None),
                        'expected_outcome': 'schedule_confirmed',
                        'validation_method': 'Check if interview actually occurs on scheduled date',
                        '90_day_plan': 'Monitor interview completion rate and hiring velocity',
                        'can_be_reversed': False,
                    },
                    db=db
                )
                logger.info(f"[INTERVIEW_HANDLER] SLM outcome recorded for interview {created_interview_id}")
            except Exception as slm_record_err:
                logger.error(f"[INTERVIEW_HANDLER] Failed to record SLM outcome: {slm_record_err}")
                # Non-blocking - interview already created

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
