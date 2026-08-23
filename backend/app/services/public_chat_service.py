"""
Public Thunder Chat -- the real, production candidate-facing web chat
widget for external visitors (careers page / job listing), alongside
WhatsApp. Not a test/preview tool: a genuine visitor who has never
talked to anyone at BlitzenX can open this, get matched against real
open roles, and become a real Candidate row -- through the exact same
create_candidate_safe()/assign_ai_agent() paths every other candidate-
creation entry point in this codebase uses (see
app.api.v1.endpoints.create_job.apply_for_job for the other one). No
shadow data model, no fabricated replies -- every message after the
opening greeting goes through the real, context-aware
generate_thunder_reply_with_fallback().

Session model: there's no login. The candidate_id returned by
start_public_chat() (a "CAN-<uuid4>", effectively unguessable) is what
the browser holds onto (e.g. localStorage) to resume a conversation --
functionally a bearer token, same trust model as any other opaque
session id. Nothing about a candidate's real identity is derivable
from it.
"""
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.consent import ConsentRecord
from app.models.user import Jobs, Users
from app.services.ai_conversation_service import assign_ai_agent, resolve_default_tenant_id
from app.services.candidate_service import create_candidate_safe, find_duplicate_candidate
from app.services.escalation_detection_service import ESCALATION_EXIT_MESSAGE, check_escalation, execute_escalation
from app.services.objection_handling_service import ObjectionEscalatedError, handle_objection
from app.services.sentiment_analysis_service import analyze_sentiment
from app.services.thunder_service import (
    WEB_CHAT_CONSENT_TYPE,
    ConsentNotGiven,
    ConversationOwnedByHuman,
    DuplicateMessageSuppressed,
    ThunderPausedError,
    generate_thunder_reply_with_fallback,
    send_thunder_message,
)


class PublicChatConsentRequired(Exception):
    """The visitor didn't tick the consent checkbox -- fail closed, same
    posture as every other consent gate in this codebase."""


class PublicChatSessionNotFound(Exception):
    """candidate_id doesn't correspond to a real chat session -- either
    it was never created, or the client lost/fabricated it."""


class PublicChatNoTenantAvailable(Exception):
    """No Super User account exists to own this conversation. Real
    misconfiguration, not something to paper over with a fake tenant."""


def _get_or_open_conversation(db: Session, candidate: Candidate, tenant_id: str) -> CandidateConversation:
    conversation = (
        db.query(CandidateConversation)
        .filter(
            CandidateConversation.candidate_id == candidate.candidateID,
            CandidateConversation.status != "closed",
        )
        .order_by(CandidateConversation.id.desc())
        .first()
    )
    if conversation:
        return conversation

    assign_ai_agent(candidate_id=candidate.candidateID, tenant_id=tenant_id, assigned_by=None, db=db)
    db.flush()
    conversation = (
        db.query(CandidateConversation)
        .filter(
            CandidateConversation.candidate_id == candidate.candidateID,
            CandidateConversation.status != "closed",
        )
        .order_by(CandidateConversation.id.desc())
        .first()
    )
    # assign_ai_agent() defaults every conversation to channel_preference
    # "email" -- correct for the manual-assignment path it primarily
    # serves, wrong here: this visitor is talking to Thunder over the
    # web widget right now, not email.
    conversation.channel_preference = "web_chat"
    db.add(conversation)
    return conversation


def _capture_web_chat_consent(db: Session, candidate_id: str) -> None:
    db.add(ConsentRecord(
        subject_type="candidate",
        subject_id=candidate_id,
        consent_type=WEB_CHAT_CONSENT_TYPE,
        consent_given=True,
        captured_by="public_web_chat",
    ))


def _opening_message(candidate: Candidate, job: Optional[Jobs], resumed: bool) -> str:
    """Deterministic, not LLM-generated -- there's no real inbound
    candidate message to reply to yet, so there's nothing for the LLM
    to ground a reply in. Writing a real greeting directly is more
    honest than inventing a fake first message just to get an LLM
    response out of generate_thunder_reply()."""
    name = candidate.candidateFirstName or "there"
    if resumed:
        return f"Welcome back, {name}! How can I help you today?"
    if job:
        return (
            f"Hi {name}, thanks for your interest in the {job.jobTitle} role at BlitzenX! "
            f"Ask me anything about it, or tell me a bit about your background and I'll "
            f"let you know how you match up."
        )
    return (
        f"Hi {name}, I'm Thunder, BlitzenX's hiring assistant. Ask me about any of our "
        f"open roles, or tell me about your background and I'll match you against what's "
        f"currently open."
    )


def start_public_chat(
    db: Session,
    *,
    full_name: str,
    email: str,
    phone: Optional[str],
    job_id: Optional[str],
    consent: bool,
) -> Dict:
    if not consent:
        raise PublicChatConsentRequired("Consent is required to start a chat with Thunder.")

    name_parts = full_name.strip().split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else None

    job: Optional[Jobs] = db.query(Jobs).filter(Jobs.jobID == job_id).first() if job_id else None

    existing, _matched_on = find_duplicate_candidate(db, email=email, mobile=phone)
    resumed = bool(existing)
    if existing:
        candidate = existing
    else:
        candidate = create_candidate_safe(
            db,
            email=email,
            mobile=phone,
            candidateFirstName=first_name,
            candidateLastName=last_name,
            candidateRole="Candidate",
            candidateSource="public_web_chat",
            job_id=job_id,
        )
        db.flush()

    # 2026-08-12: was per-branch (job.recuriterID/contactPerson when a
    # job was linked, else a locally-duplicated copy of "first Super
    # User") -- neither value was ever read back out by anything
    # downstream, and it diverged from what /activity-feed and every
    # other real reader filter by. Single shared resolver now, always.
    tenant_id = resolve_default_tenant_id(db)
    if not tenant_id:
        raise PublicChatNoTenantAvailable(
            "No Super User account exists to own this conversation -- Thunder can't be "
            "assigned. This is a real configuration gap, not a per-visitor error."
        )

    conversation = _get_or_open_conversation(db, candidate, tenant_id)
    _capture_web_chat_consent(db, candidate.candidateID)
    db.commit()
    db.refresh(candidate)
    db.refresh(conversation)

    reply_text = _opening_message(candidate, job, resumed)
    reply_event = send_thunder_message(
        db, conversation, candidate, reply_text,
        sender_type="ai_agent", channel="web_chat", auto_generated=True,
    )
    db.commit()

    logger.info(
        f"[PublicChat] {'resumed' if resumed else 'started'} chat for candidate "
        f"{candidate.candidateID} (job_id={job_id})"
    )

    return {
        "candidate_id": candidate.candidateID,
        "status": "resumed" if resumed else "started",
        "message": reply_text,
        "created_at": reply_event.created_at,
    }


def send_public_chat_message(db: Session, *, candidate_id: str, message: str, background_tasks: Optional[BackgroundTasks] = None) -> Dict:
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise PublicChatSessionNotFound(f"No chat session found for candidate_id={candidate_id!r}.")

    conversation = (
        db.query(CandidateConversation)
        .filter(
            CandidateConversation.candidate_id == candidate_id,
            CandidateConversation.status != "closed",
        )
        .order_by(CandidateConversation.id.desc())
        .first()
    )
    if not conversation:
        raise PublicChatSessionNotFound(f"No open conversation for candidate_id={candidate_id!r}.")

    inbound_event = ConversationEvent(
        conversation_id=conversation.id,
        event_type="candidate_reply",
        event_data={"channel": "web_chat", "body": message},
        triggered_by="candidate",
    )
    db.add(inbound_event)
    db.flush()

    # S-041/HRMS-0441 BR-02: cancel ALL pending follow-ups the moment any
    # inbound message arrives, on any channel. Never raises -- see
    # follow_up_scheduler_service.cancel_pending_follow_ups().
    from app.services.follow_up_scheduler_service import cancel_pending_follow_ups
    cancel_pending_follow_ups(db, candidate_id, conversation.tenant_id)

    # S-043/HRMS-0443 Step 4/BR-03: any inbound message immediately
    # reactivates a ghosted candidate. Cheap no-op for the common
    # non-ghosted case.
    from app.services.ghosting_detection_service import reactivate_candidate
    reactivate_candidate(db, candidate_id, conversation.tenant_id, conversation.id)

    # S-044/HRMS-0444 BR-01: cancel the outreach campaign the moment any
    # inbound message arrives. Never raises -- cheap no-op if no
    # ACTIVE campaign exists.
    from app.services.outreach_campaign_service import cancel_campaign_on_reply
    cancel_campaign_on_reply(db, candidate_id, conversation.tenant_id)

    # S-036/HRMS-0436 BR-01: genuinely asynchronous -- scheduled via
    # FastAPI BackgroundTasks (same real mechanism whatsapp_webhook.py/
    # create_job.py/onboarding.py already use), so it runs after this
    # response is sent and never delays Thunder's reply. Deliberately
    # NOT run synchronously when background_tasks isn't supplied (e.g. a
    # caller invoking this function directly, outside a request) --
    # running it inline would violate BR-01's own "never blocks
    # Thunder's response" requirement, so skipping is more correct here
    # than a same-behavior-different-timing fallback would be.
    if background_tasks is not None:
        background_tasks.add_task(
            analyze_sentiment, db, conversation.tenant_id, candidate_id, message,
            conversation_id=conversation.id, message_event_id=inbound_event.id,
        )

    # S-035/HRMS-0435 Step 1-3: checked before Thunder generates any
    # reply, on every inbound message, per that story's own step order.
    escalation = check_escalation(db, conversation.tenant_id, candidate_id, message)
    if escalation["needs_escalation"]:
        execute_escalation(db, conversation, candidate, reason=escalation["reason"], trigger_type=escalation["trigger_type"])
        return {"reply": ESCALATION_EXIT_MESSAGE, "created_at": datetime.utcnow(), "escalated": True}

    # S-072/HRMS-0472: the first live wiring of S-033's detect_intent()
    # (previously built but never called from any real inbound path --
    # see that module's own docstring). Only the "objecting" branch is
    # acted on here; every other intent still goes through the normal
    # reply path below, unchanged.
    from app.services.detect_intent_service import detect_intent
    intent_result = detect_intent(db, conversation.tenant_id, candidate_id, message, conversation_id=conversation.id, message_event_id=inbound_event.id)

    if intent_result["intent"] == "objecting":
        try:
            objection_result = handle_objection(db, conversation, candidate, message)
            reply_text, _used_fallback = objection_result["response"], False
        except ObjectionEscalatedError as exc:
            execute_escalation(db, conversation, candidate, reason=str(exc), trigger_type="OBJECTION_REPEATED")
            return {"reply": ESCALATION_EXIT_MESSAGE, "created_at": datetime.utcnow(), "escalated": True}
    else:
        reply_text, _used_fallback = generate_thunder_reply_with_fallback(
            db, candidate, message, channel="web_chat", conversation=conversation,
        )

    try:
        reply_event = send_thunder_message(
            db, conversation, candidate, reply_text,
            sender_type="ai_agent", channel="web_chat", auto_generated=True,
        )
    except (ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError) as exc:
        # Real, pre-existing gap this send call never guarded against --
        # newly reachable via S-072/HRMS-0472's SALARY objection
        # fallback, which (deliberately, per BR-02) returns the exact
        # same text every time, so a 2nd SALARY objection inside the
        # 60s debounce window would otherwise 500 instead of degrading
        # gracefully. Same catch-tuple convention every other real send
        # site in this codebase already uses.
        logger.info(f"[PublicChat] Reply suppressed for candidate {candidate_id!r}: {exc}")
        return {"reply": reply_text, "created_at": datetime.utcnow(), "suppressed": True}
    db.commit()

    if not _used_fallback:
        # S-064/HRMS-0464: real explanation capture -- only for a genuine
        # LLM-reasoned reply, not the hardcoded safe-fallback message.
        from app.services.thunder_explanation_service import attach_explanation
        attach_explanation(db, reply_event, candidate, conversation.tenant_id)

    return {"reply": reply_text, "created_at": reply_event.created_at}


def get_public_chat_history(db: Session, *, candidate_id: str) -> List[Dict]:
    conversation = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate_id)
        .order_by(CandidateConversation.id.desc())
        .first()
    )
    if not conversation:
        return []

    events = (
        db.query(ConversationEvent)
        .filter(
            ConversationEvent.conversation_id == conversation.id,
            ConversationEvent.event_type.in_(("candidate_reply", "ai_message_sent", "hr_message_sent")),
        )
        .order_by(ConversationEvent.created_at.asc(), ConversationEvent.id.asc())
        .all()
    )
    # assign_ai_agent() (called the first time a conversation opens) may
    # also fire a real "missing profile fields" EMAIL and log it as an
    # ai_message_sent event -- a legitimate event, just on a different
    # channel. Filtering to channel="web_chat" keeps that email out of
    # the web widget's own transcript instead of showing the visitor an
    # empty bubble for a message that actually went to their inbox.
    return [
        {
            "sender": "candidate" if event.event_type == "candidate_reply" else "thunder",
            "body": (event.event_data or {}).get("body", ""),
            "created_at": event.created_at,
        }
        for event in events
        if (event.event_data or {}).get("channel") == "web_chat"
    ]
