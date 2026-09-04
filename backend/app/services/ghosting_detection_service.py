"""
import logging
S-043/HRMS-0443 -- Candidate Ghosting Detection.

Real architecture adaptations:
- candidate_ghosting_status is genuinely new (see its model docstring).
- No internal event bus -- "listens for candidate.no_response_after_3_followups"
  is adapted to a direct, real consumer of what that spec-fictional
  event actually maps onto: a CandidateNoResponseLog row with
  detection_type='POST_THIRD', already written by
  no_response_detection_service.run_no_response_detection_job() (S-042,
  every 30 min via APScheduler). run_ghosting_detection_job() queries
  for POST_THIRD rows with no corresponding CandidateGhostingStatus row
  yet, rather than re-deriving "3 sent, no reply" a third time from
  FollowUpSchedule -- POST_THIRD IS the real signal.
- transitionState(conversation_id, 'PAUSED', ...) is NOT called anywhere
  here -- 'PAUSED' isn't a legal value on this codebase's real 3-axis
  conversation model (status is only open/awaiting_candidate/closed;
  the only real "paused" concept is owner_type='hr_user' via
  conversation_state_service.pause_for_recruiter_queue(), which means
  something semantically different -- a human recruiter queue handoff,
  S-035 -- and would incorrectly surface ghosted candidates in that
  queue). Real enforcement instead follows the pattern this round's
  scoring/follow-up services already established: gate at the point of
  ACTION (is_candidate_ghosted() checked before every outbound send),
  not via a fabricated global state value.
- No system_configuration table -- GHOSTING_REACTIVATION_DAYS is an
  env-var-overridable module constant, same honest trade-off S-020/
  S-041 already made for their own tenant-configurable thresholds.
- "publish candidate.ghosted, consumed by HRMS-0445" -- HRMS-0445
  Reactivation Campaign doesn't exist in this codebase yet, so there is
  genuinely nothing to call; candidate_ghosting_status itself is the
  real, durable row a future HRMS-0445 build would read directly.
- Self-reactivation (Step 4/BR-03) is wired into the same 3 real live
  inbound entry points S-041's cancel_pending_follow_ups() already
  hooks: whatsapp_webhook_service.store_inbound_whatsapp_message(),
  ai_conversation_service.process_candidate_reply() (email), and
  public_chat_service.send_public_chat_message() (web_chat) -- not a
  fabricated "message.received event."
- Notification reuses the exact "assigned recruiter, else tenant owner"
  recipient-resolution pattern already established twice this round
  (sla_monitoring_service._notify_recruiter_of_breach,
  escalation_detection_service._notify_escalation) -- not reinvented.
"""
import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.candidate_no_response_log import CandidateNoResponseLog
from app.models.user import Users
from app.services.follow_up_scheduler_service import cancel_pending_follow_ups
from app.services.notification_service import send_notification

GHOSTING_REACTIVATION_DAYS = int(os.getenv("GHOSTING_REACTIVATION_DAYS", "14"))  # BR-02 default

def _candidate_name(candidate: Candidate) -> str:
    parts = [candidate.candidateFirstName, candidate.candidateLastName]
    name = " ".join(p for p in parts if p).strip()
    return name or candidate.candidateEmail

def _assigned_recruiter(db: Session, candidate_id: str) -> Optional[Users]:
    """Mirrors sla_monitoring_service's own resolver -- kept local since
    that one is a private (underscore-prefixed) helper of its own module."""
    assignment = (
        db.query(CandidateAIAssignment)
        .filter(CandidateAIAssignment.candidate_id == candidate_id, CandidateAIAssignment.is_active == True)
        .order_by(CandidateAIAssignment.assigned_at.desc())
        .first()
    )
    if assignment and assignment.assigned_by:
        return db.query(Users).filter(Users.UserID == assignment.assigned_by).first()
    return None

def is_candidate_ghosted(db: Session, candidate_id: str, tenant_id: str) -> bool:
    """Step 3's real enforcement primitive -- checked at the point of
    every outbound send, not via a fabricated conversation state."""
    row = (
        db.query(CandidateGhostingStatus)
        .filter(CandidateGhostingStatus.tenant_id == tenant_id, CandidateGhostingStatus.candidate_id == candidate_id, CandidateGhostingStatus.is_reactivated == False)
        .first()
    )
    return row is not None

def _notify_recruiter_of_ghosting(db: Session, tenant_id: str, candidate: Candidate, reactivation_date: datetime) -> None:
    recipient = _assigned_recruiter(db, candidate.candidateID) or db.query(Users).filter(Users.UserID == tenant_id).first()
    if not recipient:
        return
    try:
        send_notification(
            db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient,
            priority_tier="P1", channel_preference="IN_APP",
            message=(
                f"{_candidate_name(candidate)} has not responded after 3 follow-ups and has been "
                f"marked as ghosted. Thunder will try again on {reactivation_date.strftime('%b %d, %Y')}."
            ),
        )
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[GhostingDetection] Failed to notify recruiter for candidate {candidate.candidateID!r}: {exc}")

def run_ghosting_detection_job(db: Session) -> dict:
    """Step 2. Real consumer of the POST_THIRD signal S-042 already
    produces. Never raises -- a failure on one candidate is logged and
    skipped, same defensive posture as every other periodic job this round."""
    result = {"ghosted": 0}

    post_third_logs = db.query(CandidateNoResponseLog).filter(CandidateNoResponseLog.detection_type == "POST_THIRD").all()

    for log_row in post_third_logs:
        try:
            already_ghosted = (
                db.query(CandidateGhostingStatus)
                .filter(CandidateGhostingStatus.tenant_id == log_row.tenant_id, CandidateGhostingStatus.candidate_id == log_row.candidate_id)
                .first()
            )
            if already_ghosted:
                continue

            candidate = db.query(Candidate).filter(Candidate.candidateID == log_row.candidate_id).first()
            conversation = db.query(CandidateConversation).filter(CandidateConversation.id == log_row.conversation_id).first()
            if candidate is None or conversation is None:
                continue

            now = datetime.utcnow()
            reactivation_days = GHOSTING_REACTIVATION_DAYS
            try:
                from app.services.tenant_ai_config_service import get_ghosting_reactivation_days
                reactivation_days = get_ghosting_reactivation_days(db, log_row.tenant_id)
            except Exception:
                pass
            reactivation_at = now + timedelta(days=reactivation_days)

            db.add(CandidateGhostingStatus(
                tenant_id=log_row.tenant_id, candidate_id=log_row.candidate_id, conversation_id=log_row.conversation_id,
                ghosted_at=now, reactivation_scheduled_at=reactivation_at,
            ))

            cancel_pending_follow_ups(db, log_row.candidate_id, log_row.tenant_id)  # Step 2, idempotent/harmless if already empty

            db.add(ConversationEvent(
                conversation_id=log_row.conversation_id, event_type="CANDIDATE_GHOSTED",
                event_data={"reason": "No response after 3 follow-up messages", "reactivation_scheduled_at": reactivation_at.isoformat()},
                triggered_by="system",
            ))
            db.commit()

            _notify_recruiter_of_ghosting(db, log_row.tenant_id, candidate, reactivation_at)

            result["ghosted"] += 1
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.error(f"[GhostingDetection] Failed processing POST_THIRD log id={log_row.id}: {exc}")
            db.rollback()

    return result

def reactivate_candidate(db: Session, candidate_id: str, tenant_id: str, conversation_id: int) -> bool:
    """Step 4/BR-03: self-reactivation always wins. Returns whether a
    reactivation actually happened (False is the common, cheap no-op
    case for a candidate who was never ghosted)."""
    row = (
        db.query(CandidateGhostingStatus)
        .filter(CandidateGhostingStatus.tenant_id == tenant_id, CandidateGhostingStatus.candidate_id == candidate_id, CandidateGhostingStatus.is_reactivated == False)
        .first()
    )
    if row is None:
        return False

    row.is_reactivated = True
    row.reactivated_at = datetime.utcnow()
    db.add(row)
    db.add(ConversationEvent(
        conversation_id=conversation_id, event_type="CANDIDATE_SELF_REACTIVATED",
        event_data={"ghosted_at": row.ghosted_at.isoformat() if row.ghosted_at else None}, triggered_by="candidate",
    ))
    db.commit()
    return True
