"""
S-041/HRMS-0441 -- Follow-Up Scheduler.

Real architecture adaptations:
- follow_up_schedule is genuinely new (see its model docstring).
- No conversation_messages table -- ConversationEvent is the real
  message log. "OUTBOUND, sender_type=AI" maps to event_type
  'ai_message_sent'; "INBOUND" maps to 'candidate_reply'.
  triggered_by_message_id/original_message_id both FK
  ConversationEvent.id (see the model's own naming note).
- No system_configuration table / tenant-admin-editable-without-deploy
  UI -- same trade-off S-020/HRMS-0420 already made for its own SLA
  threshold: WHATSAPP_FOLLOWUP_HOURS/EMAIL_FOLLOWUP_HOURS are module
  constants, overridable via env var. A real, honest gap against BR-04's
  literal "admin-editable without deploy" ask -- flagged, not silently
  pretended to be a UI setting.
- generateThunderResponse(..., 'FOLLOW_UP', {...}) is
  thunder_service.generate_followup_message_with_fallback() (new,
  proactive-generation path -- see its own module section for why it's
  not a call to the existing reply-generation function).
- Channel send: whatsapp reuses thunder_service.send_thunder_message()
  as-is (real, tested, ownership+consent+debounce-gated). Email has no
  equivalent gated path in this codebase -- every existing candidate-
  facing email (e.g. the missing-fields email in
  ai_conversation_service.py) already goes out ungated via
  EmailService.send_email() directly; this follows that same real,
  established convention rather than inventing a new gated email path
  unilaterally.
- No internal event bus. Step 3.9's "publish candidate.third_followup_sent"
  is NOT implemented as a formal event -- S-042/HRMS-0442's own spec
  independently claims ownership of the "3 follow-ups sent, still no
  reply" transition and publishes a differently-named event of its own
  (a real, unresolved cross-story naming conflict, flagged rather than
  silently picked). Resolution: S-041 only ever marks the 3rd follow-up
  SENT and logs FOLLOWUP_GENERATION_FAILED on fallback; S-042's
  detection job is the sole owner of noticing "3 SENT, no reply" and
  logging that transition -- a direct read, not a fabricated event.
- Step 4 cancellation (BR-02) is wired directly into the real inbound
  entry points -- whatsapp_webhook_service.store_inbound_whatsapp_message(),
  ai_conversation_service.process_candidate_reply() (email), and
  public_chat_service.send_public_chat_message() (web_chat) -- rather
  than a "message.received event," since none exists.
- "QUALIFYING/QUALIFIED" (Step 3.3) maps onto this codebase's real
  conversation.status != 'closed', same mapping S-018/S-020 already
  established for these exact spec state names.
"""
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.follow_up_schedule import FOLLOWUP_STATUSES, MAX_FOLLOWUPS, FollowUpSchedule

WHATSAPP_FOLLOWUP_HOURS = int(os.getenv("WHATSAPP_FOLLOWUP_HOURS", "24"))  # BR-04 default
EMAIL_FOLLOWUP_HOURS = int(os.getenv("EMAIL_FOLLOWUP_HOURS", "48"))  # BR-04 default
JOB_BATCH_SIZE = 50


def followup_hours_for_channel(channel: str) -> int:
    """Public (not underscore-prefixed) -- shared with
    no_response_detection_service (S-042), which needs the same
    per-channel threshold to detect staleness."""
    return WHATSAPP_FOLLOWUP_HOURS if channel == "whatsapp" else EMAIL_FOLLOWUP_HOURS


def schedule_follow_up(
    db: Session, candidate_id: str, tenant_id: str, conversation_id: int, channel: str,
    original_message_id: Optional[int], follow_up_number: int,
) -> Optional[FollowUpSchedule]:
    """Step 2. Returns the new PENDING record, or None if a duplicate
    was found (dedupe, per this function's own spec check) or
    follow_up_number exceeds BR-01's cap."""
    if follow_up_number > MAX_FOLLOWUPS:  # BR-01
        logger.warning(f"[FollowUpScheduler] Refusing to schedule follow-up #{follow_up_number} for candidate {candidate_id!r} -- exceeds max {MAX_FOLLOWUPS}.")
        return None

    existing = (
        db.query(FollowUpSchedule)
        .filter(FollowUpSchedule.tenant_id == tenant_id, FollowUpSchedule.candidate_id == candidate_id,
                FollowUpSchedule.channel == channel, FollowUpSchedule.status == "PENDING")
        .first()
    )
    if existing:
        return None

    scheduled_at = datetime.utcnow() + timedelta(hours=followup_hours_for_channel(channel))
    record = FollowUpSchedule(
        tenant_id=tenant_id, candidate_id=candidate_id, conversation_id=conversation_id, channel=channel,
        scheduled_at=scheduled_at, status="PENDING", follow_up_number=follow_up_number,
        triggered_by_message_id=original_message_id,
    )
    db.add(record)
    db.commit()
    return record


def cancel_pending_follow_ups(db: Session, candidate_id: str, tenant_id: str) -> int:
    """Step 4/BR-02. Cancels ALL pending follow-ups the moment any
    inbound message arrives, regardless of which channel it came in
    on. Returns the number cancelled."""
    rows = (
        db.query(FollowUpSchedule)
        .filter(FollowUpSchedule.tenant_id == tenant_id, FollowUpSchedule.candidate_id == candidate_id, FollowUpSchedule.status == "PENDING")
        .all()
    )
    for row in rows:
        row.status = "CANCELLED"
        db.add(row)
    if rows:
        db.commit()
    return len(rows)


def _has_replied_since(db: Session, conversation_id: int, since: Optional[datetime]) -> bool:
    if since is None:
        return False
    reply = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type == "candidate_reply", ConversationEvent.created_at > since)
        .first()
    )
    return reply is not None


def _send_followup(db: Session, conversation: CandidateConversation, candidate: Candidate, message_body: str, channel: str) -> None:
    """Step 3.5/3.6. Delegates to thunder_service's shared send helper
    -- see that function's own docstring on why this was consolidated
    (previously duplicated identically in outreach_campaign_service)."""
    from app.services.thunder_service import send_outbound_campaign_message
    send_outbound_campaign_message(db, conversation, candidate, message_body, channel)


def run_follow_up_execution_job(db: Session) -> Dict:
    """Step 3. FOLLOWUP_EXECUTION_JOB body, run every 15 min. Never lets
    one bad row abort the batch -- catches per-row, marks SKIPPED, moves on."""
    from app.services.ghosting_detection_service import is_candidate_ghosted
    from app.services.thunder_service import ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError, generate_followup_message_with_fallback
    from app.services.whatsapp_routing_service import is_ai_owner

    now = datetime.utcnow()
    due = (
        db.query(FollowUpSchedule)
        .filter(FollowUpSchedule.status == "PENDING", FollowUpSchedule.scheduled_at <= now)
        .order_by(FollowUpSchedule.scheduled_at.asc())
        .limit(JOB_BATCH_SIZE)
        .all()
    )

    result = {"processed": 0, "sent": 0, "cancelled": 0, "skipped": 0}

    for row in due:
        result["processed"] += 1
        conversation = db.query(CandidateConversation).filter(CandidateConversation.id == row.conversation_id).first()
        candidate = db.query(Candidate).filter(Candidate.candidateID == row.candidate_id).first()
        if conversation is None or candidate is None:
            row.status = "SKIPPED"
            db.add(row)
            db.commit()
            result["skipped"] += 1
            continue

        try:
            trigger_event = db.query(ConversationEvent).filter(ConversationEvent.id == row.triggered_by_message_id).first() if row.triggered_by_message_id else None
            if _has_replied_since(db, row.conversation_id, trigger_event.created_at if trigger_event else row.created_at):
                row.status = "CANCELLED"  # Step 3.1 -- candidate already responded
                result["cancelled"] += 1
            elif not is_ai_owner(conversation):
                row.status = "SKIPPED"  # Step 3.2 -- BR: recruiter owns
                result["skipped"] += 1
            elif conversation.status == "closed" or conversation.escalation_state == "escalated":
                row.status = "SKIPPED"  # Step 3.3 -- not QUALIFYING/QUALIFIED (real mapping)
                result["skipped"] += 1
            elif is_candidate_ghosted(db, row.candidate_id, row.tenant_id):  # S-043 BR-01
                row.status = "SKIPPED"
                result["skipped"] += 1
            else:
                message, used_fallback = generate_followup_message_with_fallback(
                    db, candidate, row.follow_up_number, channel=row.channel, conversation=conversation,
                )
                if used_fallback:
                    db.add(ConversationEvent(
                        conversation_id=conversation.id, event_type="FOLLOWUP_GENERATION_FAILED",
                        event_data={"follow_up_number": row.follow_up_number}, triggered_by="system",
                    ))
                _send_followup(db, conversation, candidate, message, row.channel)
                row.status = "SENT"
                row.sent_at = now
                result["sent"] += 1

                if row.follow_up_number < MAX_FOLLOWUPS:  # Step 3.8
                    schedule_follow_up(db, row.candidate_id, row.tenant_id, row.conversation_id, row.channel, row.triggered_by_message_id, row.follow_up_number + 1)
                # Step 3.9: no formal event published here -- see module docstring.

            db.add(row)
            db.commit()
        except (ConversationOwnedByHuman, ConsentNotGiven, DuplicateMessageSuppressed, ThunderPausedError) as exc:
            logger.info(f"[FollowUpScheduler] Follow-up #{row.follow_up_number} for candidate {row.candidate_id!r} skipped: {exc}")
            row.status = "SKIPPED"
            db.add(row)
            db.commit()
            result["skipped"] += 1
        except Exception as exc:
            logger.error(f"[FollowUpScheduler] Unexpected failure processing follow-up id={row.id}: {exc}")
            db.rollback()
            row = db.query(FollowUpSchedule).filter(FollowUpSchedule.id == row.id).first()
            if row:
                row.status = "SKIPPED"
                db.add(row)
                db.commit()
            result["skipped"] += 1

    return result
