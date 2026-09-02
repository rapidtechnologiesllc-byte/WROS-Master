"""
Mellow keep-warm outreach -- the ENGAGED/QUALIFYING/SCREENED-stage
cadence tier of the real stage-aware cadence Avinash specified
(2026-08-04, [[wros_outreach_cadence_by_stage_backlog]]): "once a
week, once every 2 weeks, or even once a month, just to keep the
candidate warm... not daily or weekly [aggressive follow-up]." Weekly
is the code-constant default (env-overridable), the middle of that
stated range, same "flag the real default, don't fake a config UI"
posture follow_up_scheduler_service already takes for its own
import logging
thresholds.

Also the real integration point for the separate, older multichannel
backlog note ([[wros_multichannel_outreach_backlog]]): this new
mechanism sends BOTH WhatsApp and email (not either/or), since it's
new code with no already-shipped single-channel behavior to preserve --
deliberately NOT retrofitted into the already-shipped S-012/S-013
first-engagement services, which stay single-channel per
channel_preference exactly as that backlog note's own "needs a real
design pass before touching already-shipped code" caution says.

A simple templated message, not LLM-generated -- this fires
automatically, unprompted, on a real cadence across every eligible
candidate; a fixed, BA-reviewable template is safer here than a fresh
LLM call per candidate per week (same posture as S-055's
DEFAULT_FAQ_CONTENT placeholder).
"""
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent

MELLOW_KEEPWARM_INTERVAL_DAYS = int(os.getenv("MELLOW_KEEPWARM_INTERVAL_DAYS", "7"))
MELLOW_KEEPWARM_STAGES = ("ENGAGED", "QUALIFYING", "SCREENED")
JOB_BATCH_SIZE = 100

KEEPWARM_WHATSAPP_TEMPLATE = (
    "Hi {name}, just checking in -- we haven't forgotten about you! We're still reviewing "
    "roles that could be a fit for your background. We'll reach out the moment something "
    "matches. No action needed from you right now."
)
KEEPWARM_EMAIL_SUBJECT = "Still on our radar, {name}"
KEEPWARM_EMAIL_BODY = (
    "<p>Hi {name},</p><p>Just a quick note to let you know we haven't forgotten about you. "
    "We're still reviewing open roles for a good fit with your background, and we'll reach "
    "out the moment something matches.</p><p>No action needed from you right now.</p>"
)


def _last_outbound_at(db: Session, conversation_id: int) -> Optional[datetime]:
    event = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type == "ai_message_sent")
        .order_by(ConversationEvent.created_at.desc())
        .first()
    )
    return event.created_at if event else None


def run_mellow_keepwarm_job(db: Session, *, now: Optional[datetime] = None) -> Dict:
    from app.services.candidate_journey_service import get_candidate_journey
    from app.services.email_service import EmailService
    from app.services.ghosting_detection_service import is_candidate_ghosted
    from app.services.thunder_service import (
        ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError, send_thunder_message,
    )
    from app.services.whatsapp_routing_service import is_ai_owner

    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=MELLOW_KEEPWARM_INTERVAL_DAYS)

    open_conversations = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.status != "closed", CandidateConversation.escalation_state != "escalated")
        .limit(JOB_BATCH_SIZE)
        .all()
    )

    result = {"considered": 0, "nudged": 0, "skipped": 0}

    for conversation in open_conversations:
        result["considered"] += 1
        if not is_ai_owner(conversation):
            result["skipped"] += 1
            continue

        candidate = db.query(Candidate).filter(Candidate.candidateID == conversation.candidate_id).first()
        if not candidate:
            result["skipped"] += 1
            continue

        stage = get_candidate_journey(db, candidate.candidateID, conversation.tenant_id)["current_stage"]
        if stage not in MELLOW_KEEPWARM_STAGES:
            result["skipped"] += 1
            continue

        if is_candidate_ghosted(db, candidate.candidateID, conversation.tenant_id):
            result["skipped"] += 1
            continue

        last_outbound = _last_outbound_at(db, conversation.id)
        if last_outbound is not None and last_outbound > cutoff:
            result["skipped"] += 1  # nudged recently enough -- not due yet
            continue

        name = candidate.candidateFirstName or "there"
        try:
            send_thunder_message(
                db, conversation, candidate, KEEPWARM_WHATSAPP_TEMPLATE.format(name=name),
                sender_type="ai_agent", channel="whatsapp", auto_generated=True,
            )
        except (ConversationOwnedByHuman, ConsentNotGiven, DuplicateMessageSuppressed, ThunderPausedError):
            pass  # whatsapp leg may legitimately not fire -- email leg below is independent, per BOTH-not-either/or

        if candidate.candidateEmail:
            EmailService.send_email(
                candidate.candidateEmail, KEEPWARM_EMAIL_SUBJECT.format(name=name), KEEPWARM_EMAIL_BODY.format(name=name),
            )

        db.add(ConversationEvent(
            conversation_id=conversation.id, event_type="MELLOW_KEEPWARM_SENT",
            event_data={"stage": stage}, triggered_by="system",
        ))
        db.commit()
        result["nudged"] += 1

    return result
