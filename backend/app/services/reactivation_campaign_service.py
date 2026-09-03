"""
import logging
S-045/HRMS-0445 -- Reactivation Campaign.

*** REAL, EXPLICIT SPEC OVERRIDE FROM AVINASH -- READ BEFORE TOUCHING ***
The literal spec (Step 4, BR-02, BR-03, AC-7, TC-004, "What NOT to
build") describes a hard terminal state: one reactivation message, one
3-touch campaign, and if THAT also gets no response, archive the
candidate (transitionState -> 'COMPLETED', log
CANDIDATE_ARCHIVED_NO_RESPONSE, notify the recruiter "they have been
archived"), with an explicit "do NOT build a second reactivation"
instruction.

Avinash's direct override, given mid-session while this exact story
was being scoped: **"S-045 instead of ... 'If no response: archive
candidate' should be ... 'If no response: keep trying till I succeed
-- no candidate should ever be left. The goal to 2000 is only possible
if each of them is converted.'"**

This module implements THAT rule, not the literal spec. There is no
archive/terminal state anywhere in this file. reactivation_attempt_count
is tracked for observability only and is NEVER used as a cutoff.
Instead of "reactivate once, then give up," a candidate whose
reactivation campaign completes with no reply is simply rescheduled
for another reactivation attempt later (RETRY_INTERVAL_DAYS, env-var,
deliberately longer than the initial 14-day wait to avoid genuine spam
while still being unbounded) -- forever, until they reply (at which
point the existing, already-real reactivate_candidate() wiring in
whatsapp_webhook_service/ai_conversation_service/public_chat_service
immediately reactivates them) or a human recruiter intervenes.

Other real architecture adaptations:
- reactivation_scheduled_at (CandidateGhostingStatus, S-043) was
  write-only before this story -- set by ghosting_detection_service,
  never read anywhere. This is exactly the real "due for reactivation"
  signal Step 2 describes; queried directly, not re-derived.
- No prompt_templates.js/HRMS-0431-style prompt-type catalog exists in
  this Python backend -- generation is
  thunder_service.generate_reactivation_message_with_fallback(), a
  second proactive-generation path alongside S-041's follow-up one,
  with its own "fresh angle, no reference to prior silence" instruction.
- transitionState(..., 'PAUSED' -> 'QUALIFYING') has no home on this
  codebase's real 3-axis conversation model (same finding S-043 already
  made) -- not applicable. The real "paused" state IS
  is_reactivated=false itself, gating every outbound send already;
  once reactivate_candidate() flips it, normal flow resumes with no
  separate state transition needed.
- startCampaign() (S-044) is reused directly, called with
  campaign_type="REACTIVATION_CAMPAIGN" so it's distinguishable from a
  standard post-first-contact campaign; already idempotent.
- "candidate.campaign_completed_no_response event, consumed here" --
  no event bus. Polled directly: OutreachCampaign rows with
  campaign_type="REACTIVATION_CAMPAIGN", status="COMPLETED",
  stop_reason="CAMPAIGN_COMPLETED_NO_RESPONSE" are the real signal.
- Send/generation reuse: thunder_service.send_outbound_campaign_message()
  (the shared whatsapp/email dispatch consolidated during this story
  from two prior duplicates -- see its own docstring).
"""
import os
from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.outreach_campaign import OutreachCampaign

RETRY_INTERVAL_DAYS = int(os.getenv("REACTIVATION_RETRY_INTERVAL_DAYS", "21"))  # longer than the initial 14-day wait
JOB_BATCH_SIZE = 50


def run_reactivation_job(db: Session) -> Dict:
    """Step 2. Runs every 30 min. Sends one reactivation message to
    every candidate whose reactivation_scheduled_at is due, then starts
    a REACTIVATION_CAMPAIGN. Never raises."""
    from app.services.ghosting_detection_service import reactivate_candidate
    from app.services.outreach_campaign_service import start_campaign
    from app.services.thunder_service import ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError, generate_reactivation_message_with_fallback
    from app.services.whatsapp_routing_service import is_ai_owner

    now = datetime.utcnow()
    due = (
        db.query(CandidateGhostingStatus)
        .filter(CandidateGhostingStatus.is_reactivated == False, CandidateGhostingStatus.reactivation_scheduled_at != None, CandidateGhostingStatus.reactivation_scheduled_at <= now)
        .limit(JOB_BATCH_SIZE)
        .all()
    )

    result = {"processed": 0, "sent": 0, "skipped": 0}

    for status_row in due:
        result["processed"] += 1
        try:
            conversation = db.query(CandidateConversation).filter(CandidateConversation.id == status_row.conversation_id).first()
            candidate = db.query(Candidate).filter(Candidate.candidateID == status_row.candidate_id).first()
            if conversation is None or candidate is None:
                result["skipped"] += 1
                continue

            # Step 2.1 -- a reply since ghosting means self-reactivation
            # (already wired into the 3 live inbound entry points) should
            # already have handled this; this is a cheap belt-and-braces
            # re-check, not the primary mechanism.
            replied_since_ghosting = (
                db.query(ConversationEvent)
                .filter(ConversationEvent.conversation_id == status_row.conversation_id, ConversationEvent.event_type == "candidate_reply", ConversationEvent.created_at > status_row.ghosted_at)
                .first()
            ) is not None
            if replied_since_ghosting:
                reactivate_candidate(db, status_row.candidate_id, status_row.tenant_id, status_row.conversation_id)
                result["skipped"] += 1
                continue

            if not is_ai_owner(conversation) or conversation.status == "closed" or conversation.escalation_state == "escalated":
                result["skipped"] += 1
                continue

            channel = conversation.channel_preference if conversation.channel_preference in ("whatsapp", "email") else "whatsapp"
            days_since_contact = max((now - status_row.ghosted_at).days, 0)

            message, used_fallback = generate_reactivation_message_with_fallback(
                db, candidate, days_since_contact, channel=channel, conversation=conversation,
            )
            if used_fallback:
                db.add(ConversationEvent(
                    conversation_id=conversation.id, event_type="REACTIVATION_GENERATION_FAILED",
                    event_data={"days_since_contact": days_since_contact}, triggered_by="system",
                ))

            from app.services.thunder_service import send_outbound_campaign_message
            send_outbound_campaign_message(db, conversation, candidate, message, channel, email_subject="We'd love to hear from you again")

            db.add(ConversationEvent(
                conversation_id=conversation.id, event_type="REACTIVATION_SENT",
                event_data={"days_since_contact": days_since_contact, "channel": channel}, triggered_by="ai_agent",
            ))

            status_row.reactivation_attempt_count += 1  # observability only -- never a cutoff, see module docstring
            status_row.last_reactivation_sent_at = now
            status_row.reactivation_scheduled_at = None  # now "in flight" via the campaign below, not due again until it resolves
            db.add(status_row)

            start_campaign(db, status_row.candidate_id, status_row.tenant_id, status_row.conversation_id, campaign_type="REACTIVATION_CAMPAIGN")

            db.commit()
            result["sent"] += 1
        except (ConversationOwnedByHuman, ConsentNotGiven, DuplicateMessageSuppressed, ThunderPausedError) as exc:
            logger.info(f"[Reactivation] Reactivation for candidate {status_row.candidate_id!r} skipped: {exc}")
            result["skipped"] += 1
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.error(f"[Reactivation] Unexpected failure processing candidate {status_row.candidate_id!r}: {exc}")
            db.rollback()
            result["skipped"] += 1

    return result


def run_reactivation_reschedule_job(db: Session) -> Dict:
    """No archive, ever -- see module docstring's override. When a
    REACTIVATION_CAMPAIGN completes with no reply, this reschedules the
    NEXT reactivation attempt instead of giving up. Never raises."""
    result = {"rescheduled": 0}

    completed_campaigns = (
        db.query(OutreachCampaign)
        .filter(OutreachCampaign.campaign_type == "REACTIVATION_CAMPAIGN", OutreachCampaign.status == "COMPLETED", OutreachCampaign.stop_reason == "CAMPAIGN_COMPLETED_NO_RESPONSE")
        .all()
    )

    for campaign in completed_campaigns:
        try:
            status_row = (
                db.query(CandidateGhostingStatus)
                .filter(CandidateGhostingStatus.tenant_id == campaign.tenant_id, CandidateGhostingStatus.candidate_id == campaign.candidate_id, CandidateGhostingStatus.is_reactivated == False)
                .first()
            )
            if status_row is None or status_row.reactivation_scheduled_at is not None:
                continue  # already reactivated, or already has a next attempt queued

            status_row.reactivation_scheduled_at = datetime.utcnow() + timedelta(days=RETRY_INTERVAL_DAYS)
            db.add(status_row)
            db.commit()
            result["rescheduled"] += 1
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.error(f"[Reactivation] Failed to reschedule candidate {campaign.candidate_id!r}: {exc}")
            db.rollback()

    return result
