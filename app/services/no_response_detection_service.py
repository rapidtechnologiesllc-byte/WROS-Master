"""
S-042/HRMS-0442 -- No Response Detection.

Real architecture adaptations:
- candidate_no_response_log is genuinely new (see its model docstring).
- No conversation_messages table -- same ConversationEvent mapping
  follow_up_scheduler_service.py uses ('ai_message_sent'/'candidate_reply').
- BR-02's "QUALIFYING/QUALIFIED, not COMPLETED/ESCALATED/PAUSED" maps
  onto is_ai_owner(conversation) (excludes PAUSED -- a human owns it)
  AND conversation.status != 'closed' (excludes COMPLETED) AND
  escalation_state != 'escalated' (excludes ESCALATED) -- the same
  mapping follow_up_scheduler_service.py's execution job already uses
  for the identical spec language.
- No internal event bus -- Step 3's "publish candidate.no_response_detected"
  and "publish candidate.no_response_after_3_followups" are both
  adapted to direct, real actions instead of fabricated events:
  candidate.no_response_detected has two real consumers per the spec's
  own integrations table -- HRMS-0420 SLA Monitoring (already live,
  already independently detects NO_CONTACT breaches on its own 30-min
  cycle against the real candidate_sla_breaches table -- this job does
  NOT duplicate that write, since sla_monitoring_service already owns
  it) and HRMS-0443 Ghosting Detection (does not exist in this codebase
  yet -- genuinely nothing to call). candidate.no_response_after_3_followups
  is this job's own real transition to detect and log (detection_type
  POST_THIRD) -- see follow_up_scheduler_service's own module docstring
  for the cross-story event-ownership conflict this resolves (S-041
  does NOT also claim this transition).
- This job's real, narrow scope given what's actually live: (1) detect
  a candidate who has NEVER had a follow-up scheduled and is now stale
  -> log FIRST_NO_RESPONSE + schedule follow-up #1. (2) detect a
  candidate whose 3rd follow-up SENT with no PENDING follow-up left ->
  log POST_THIRD (the real "confirms 3 unanswered follow-ups" HRMS-0443
  is blocked on, per S-042's own "Blocks" field -- HRMS-0443 itself
  isn't built this round, so this is as far as the real chain goes).
  Follow-ups #2/#3 in between are already self-chained by
  follow_up_scheduler_service's own execution job (Step 3.8) -- BR-01
  ("do not re-detect if PENDING already scheduled") means this job has
  nothing to do for a candidate mid-chain, so it doesn't try.
"""
from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_no_response_log import CandidateNoResponseLog
from app.models.follow_up_schedule import FollowUpSchedule, MAX_FOLLOWUPS
from app.services.follow_up_scheduler_service import followup_hours_for_channel, max_followup_count_for_tenant, schedule_follow_up
from app.services.whatsapp_routing_service import is_ai_owner


def _log_detection(db: Session, tenant_id: str, candidate_id: str, conversation_id: int, last_outbound_id, detection_type: str, follow_up_scheduled_at=None) -> None:
    db.add(CandidateNoResponseLog(
        tenant_id=tenant_id, candidate_id=candidate_id, conversation_id=conversation_id,
        last_outbound_message_id=last_outbound_id, detection_type=detection_type,
        follow_up_scheduled_at=follow_up_scheduled_at,
    ))


def _eligible_conversation(conversation: CandidateConversation) -> bool:
    """BR-02 -- see module docstring for the real state mapping."""
    return is_ai_owner(conversation) and conversation.status != "closed" and conversation.escalation_state != "escalated"


def run_no_response_detection_job(db: Session) -> Dict:
    """Step 1. Runs every 30 min. Never raises -- a failure on one
    conversation is logged and skipped, same defensive posture as every
    other periodic job this round."""
    result = {"checked": 0, "first_detected": 0, "post_third": 0}

    conversations = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.owner_type == "ai_agent", CandidateConversation.status != "closed", CandidateConversation.escalation_state != "escalated")
        .all()
    )

    for conversation in conversations:
        try:
            if not _eligible_conversation(conversation):
                continue

            last_outbound = (
                db.query(ConversationEvent)
                .filter(ConversationEvent.conversation_id == conversation.id, ConversationEvent.event_type == "ai_message_sent")
                .order_by(ConversationEvent.created_at.desc())
                .first()
            )
            if last_outbound is None:
                continue  # nothing sent yet -- no silence to detect

            has_replied = (
                db.query(ConversationEvent)
                .filter(ConversationEvent.conversation_id == conversation.id, ConversationEvent.event_type == "candidate_reply", ConversationEvent.created_at > last_outbound.created_at)
                .first()
            ) is not None
            if has_replied:
                continue

            result["checked"] += 1
            channel = (last_outbound.event_data or {}).get("channel", "whatsapp")
            threshold = timedelta(hours=followup_hours_for_channel(channel, db, conversation.tenant_id))
            stale = last_outbound.created_at <= datetime.utcnow() - threshold

            existing_rows = (
                db.query(FollowUpSchedule)
                .filter(FollowUpSchedule.candidate_id == conversation.candidate_id, FollowUpSchedule.tenant_id == conversation.tenant_id)
                .all()
            )
            has_pending = any(r.status == "PENDING" for r in existing_rows)
            sent_count = sum(1 for r in existing_rows if r.status == "SENT")

            if has_pending:
                continue  # BR-01 -- do not re-detect while a follow-up is already scheduled

            if not existing_rows and stale:
                scheduled = schedule_follow_up(db, conversation.candidate_id, conversation.tenant_id, conversation.id, channel, last_outbound.id, 1)
                _log_detection(db, conversation.tenant_id, conversation.candidate_id, conversation.id, last_outbound.id, "FIRST_NO_RESPONSE", scheduled.scheduled_at if scheduled else None)
                db.commit()
                result["first_detected"] += 1
            elif sent_count >= max_followup_count_for_tenant(db, conversation.tenant_id) and not has_pending:
                already_logged = (
                    db.query(CandidateNoResponseLog)
                    .filter(CandidateNoResponseLog.candidate_id == conversation.candidate_id, CandidateNoResponseLog.tenant_id == conversation.tenant_id, CandidateNoResponseLog.detection_type == "POST_THIRD")
                    .first()
                )
                if not already_logged:
                    _log_detection(db, conversation.tenant_id, conversation.candidate_id, conversation.id, last_outbound.id, "POST_THIRD")
                    db.commit()
                    result["post_third"] += 1
        except Exception as exc:
            logger.error(f"[NoResponseDetection] Failed processing conversation {conversation.id}: {exc}")
            db.rollback()

    return result
