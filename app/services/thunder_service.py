"""
Phase 3 Part A1 -- Thunder Conversation Core.

`03-THUNDER-AGENTIC-LAYER.md` calls for exactly two functions every
other story in this platform must call instead of reimplementing:

  build_candidate_context() -- read cross-channel history before
                                generating any candidate-facing response.
  send_thunder_message()    -- the one send path, enforcing R-08,
                                consent, and duplicate-send prevention
                                every time, no bypass.

Neither is built from scratch. `app.services.whatsapp_routing_service.
send_whatsapp_message()` already IS the real, tested R-08 ownership gate
(HRMS-0410 BR-01 -- "Thunder must never send when a recruiter owns the
conversation") and the one place `conversation_inactivity_service.py`
sends from. This module wraps it rather than duplicating that logic,
and adds the two guarantees the Phase 3 doc calls for that the existing
gate doesn't cover yet: consent and debounce.

Consent: the doc says "candidates.consent_given must be true" -- that
column does not exist in this codebase. `app.models.consent.ConsentRecord`
(Phase 1 B6) is the real, general-purpose consent table its own
docstring says every story should honor instead of inventing a flag --
same doc-vs-reality gap pattern already flagged elsewhere in this
project (Locale/Currency, SQL Server vs Postgres). This module reads
that table, not a fictional column.

candidate_desire_profiles (02-DATA-MODEL.md Domain 2) does not exist in
this codebase -- it's EPIC-11 scope (HRMS-1101-1110, Phase 3 Workstream
1 / Recruit), not Part A. build_candidate_context() returns
desire_profile=None rather than fabricating one, so a caller can tell
"not built yet" apart from "built and empty."
"""
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy.orm import Session

from app.core.llm_prompt_safety import build_safe_prompt, flag_suspicious_patterns
from app.core.logging import logger
from app.core.security import get_password_hash
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.consent import ConsentRecord
from app.models.internal_note import InternalNote
from app.models.user import Jobs, Users
from app.services.ai_conversation_service import AI_AGENT_NAME, AI_AGENT_PERSONA, resolve_thunder_config
from app.services.conversation_state_service import escalate as escalate_conversation
from app.services.thunder_pause_service import (  # noqa: F401 -- re-exported for callers
    ThunderPausedError,
    raise_if_thunder_paused,
)
from app.services.whatsapp_routing_service import (  # noqa: F401 -- re-exported gate
    ConversationOwnedByHuman,
    is_ai_owner,
    send_whatsapp_message,
    take_over_conversation,
)

WHATSAPP_OUTREACH_CONSENT_TYPE = "whatsapp_outreach"
# 2026-07-23 -- public web chat (see app.services.public_chat_service) is a
# second real candidate-facing channel, not a mock of the WhatsApp one. Its
# own consent type so a visitor who only ever used the web widget is never
# treated as having consented to WhatsApp outreach, or vice versa.
WEB_CHAT_CONSENT_TYPE = "web_chat_outreach"
DEBOUNCE_SECONDS = 60

# Reply-generation -- reuses the exact Gemini pattern already wired for
# candidate-facing AI in app.services.ai_conversation_service (same env
# var, same model family) rather than standing up a second LLM client
# for this codebase. See that module for the established convention.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
THUNDER_REPLY_MODEL = "gemini-3-flash-preview"


class ConsentNotGiven(Exception):
    """A1: no active whatsapp_outreach ConsentRecord for this candidate."""


class DuplicateMessageSuppressed(Exception):
    """A1's debounce guarantee -- the same message body was already sent
    on this conversation within DEBOUNCE_SECONDS."""


def has_active_consent(
    db: Session, candidate_id: str, *, consent_type: str = WHATSAPP_OUTREACH_CONSENT_TYPE,
) -> bool:
    """Most recent ConsentRecord for this subject+type wins -- a later
    revocation overrides an earlier grant, same convention as every
    other "latest row wins" status field in this codebase."""
    record = (
        db.query(ConsentRecord)
        .filter(
            ConsentRecord.subject_type == "candidate",
            ConsentRecord.subject_id == candidate_id,
            ConsentRecord.consent_type == consent_type,
        )
        .order_by(ConsentRecord.captured_at.desc(), ConsentRecord.id.desc())
        .first()
    )
    return bool(record and record.consent_given)


def _is_duplicate_send(
    db: Session, conversation: CandidateConversation, message_body: str,
) -> bool:
    # Filtered in Python, not SQL -- event_data is a JSON-encoded column
    # (Text-backed on SQL Server, per this codebase's architecture notes)
    # and per-conversation volume is small enough that this is cheap.
    #
    # Compared against real wall-clock time, not a caller-supplied `now`
    # -- the ConversationEvent this guards against was itself inserted
    # with a real DB-server timestamp (send_whatsapp_message's created_at
    # is func.now(), never caller-controlled), so the window check has
    # to use the same clock or it silently stops working (a synthetic
    # `now` would never fall near a real inserted timestamp).
    window_start = datetime.utcnow() - timedelta(seconds=DEBOUNCE_SECONDS)
    recent = (
        db.query(ConversationEvent)
        .filter(
            ConversationEvent.conversation_id == conversation.id,
            ConversationEvent.event_type.in_(("ai_message_sent", "hr_message_sent")),
            ConversationEvent.created_at >= window_start,
        )
        .all()
    )
    return any((event.event_data or {}).get("body") == message_body for event in recent)


# Which consent type gates a send on each real channel. 'whatsapp' has
# an external transport (see send_whatsapp_message); 'web_chat' doesn't
# need one -- the reply IS the HTTP response the browser is waiting on
# (see send_web_chat_message below) -- but it still goes through the
# exact same consent/debounce/ownership gates, because it's a real
# candidate-facing channel, not a mock.
CHANNEL_CONSENT_TYPES = {
    "whatsapp": WHATSAPP_OUTREACH_CONSENT_TYPE,
    "web_chat": WEB_CHAT_CONSENT_TYPE,
}


def send_web_chat_message(
    db: Session,
    conversation: CandidateConversation,
    candidate: Candidate,
    message_body: str,
    *,
    sender_type: str,
    sender_id: Optional[str] = None,
) -> ConversationEvent:
    """
    Web-chat's send path. Same R-08 ownership gate as
    send_whatsapp_message() (is_ai_owner/take_over_conversation, both
    from whatsapp_routing_service) -- Thunder still can't send once a
    human has taken the conversation over, regardless of which channel
    it came in on. No external transport to call: the reply is returned
    directly in the HTTP response, so delivery is unconditional once
    this function returns.
    """
    if sender_type == "ai_agent":
        if not is_ai_owner(conversation):
            raise ConversationOwnedByHuman(
                f"Conversation {conversation.id} is owned by {conversation.owner_type}:"
                f"{conversation.owner_id} -- Thunder may not send."
            )
    elif sender_type == "hr_user":
        if not sender_id:
            raise ValueError("sender_id is required when sender_type='hr_user'.")
        take_over_conversation(db, conversation, sender_id)
    else:
        raise ValueError(f"sender_type must be 'ai_agent' or 'hr_user', got '{sender_type}'.")

    event = ConversationEvent(
        conversation_id=conversation.id,
        event_type="ai_message_sent" if sender_type == "ai_agent" else "hr_message_sent",
        event_data={
            "channel": "web_chat",
            "body": message_body,
            "delivered": True,
        },
        triggered_by=sender_type,
    )
    db.add(event)
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    return event


def send_thunder_message(
    db: Session,
    conversation: CandidateConversation,
    candidate: Candidate,
    message_body: str,
    *,
    sender_type: str,
    sender_id: Optional[str] = None,
    channel: str = "whatsapp",
    whatsapp_client=None,
    auto_generated: bool = False,
) -> ConversationEvent:
    """
    A1's sendThunderMessage() -- the single send path every candidate-
    facing story in this platform must call instead of hand-rolling its
    own send logic. R-08 (ownership lock) is enforced per-channel
    (send_whatsapp_message / send_web_chat_message below), not
    reimplemented here; this function adds the consent and debounce
    checks in front of it, for every channel alike.

    channel: 'whatsapp' or 'web_chat' -- see CHANNEL_CONSENT_TYPES.
    Kept as a parameter rather than hardcoded so a future channel
    doesn't require every caller to change.
    """
    raise_if_thunder_paused(db, conversation)

    consent_type = CHANNEL_CONSENT_TYPES.get(channel)
    if consent_type is None:
        raise NotImplementedError(
            f"send_thunder_message: no transport wired for channel '{channel}' in this "
            f"codebase yet -- only {sorted(CHANNEL_CONSENT_TYPES)} do."
        )

    if not has_active_consent(db, candidate.candidateID, consent_type=consent_type):
        raise ConsentNotGiven(
            f"Candidate {candidate.candidateID} has no active {consent_type} "
            f"consent record -- send rejected."
        )

    if _is_duplicate_send(db, conversation, message_body):
        raise DuplicateMessageSuppressed(
            f"An identical message was already sent on conversation {conversation.id} "
            f"within the last {DEBOUNCE_SECONDS}s -- suppressed."
        )

    if channel == "whatsapp":
        return send_whatsapp_message(
            db, conversation, candidate, message_body,
            sender_type=sender_type, sender_id=sender_id,
            whatsapp_client=whatsapp_client, auto_generated=auto_generated,
        )
    return send_web_chat_message(
        db, conversation, candidate, message_body,
        sender_type=sender_type, sender_id=sender_id,
    )


def send_outbound_campaign_message(db: Session, conversation: CandidateConversation, candidate: Candidate, message_body: str, channel: str, *, email_subject: str = "Following up on your application") -> None:
    """Shared whatsapp/email send dispatch for the automated outreach
    stack (S-041 follow-ups, S-044 campaign touchpoints, S-045
    reactivation messages) -- previously duplicated identically across
    follow_up_scheduler_service._send_followup() and
    outreach_campaign_service._send_touchpoint(); consolidated here
    once a third caller needed the exact same logic. whatsapp reuses
    the real, gated send_thunder_message(); email reuses this
    codebase's existing ungated candidate-email convention (every
    other candidate email in this codebase, e.g. the missing-fields
    email, already goes out this way).

    S-075/HRMS-0475: checked directly here too (not just inside
    send_thunder_message()) since the email branch below never calls
    that function -- without this, a paused/globally-disabled candidate
    would still get automated outreach email."""
    raise_if_thunder_paused(db, conversation)

    if channel == "whatsapp":
        send_thunder_message(db, conversation, candidate, message_body, sender_type="ai_agent", channel="whatsapp", auto_generated=True)
        return

    from app.services.email_service import EmailService
    try:
        EmailService.send_email(candidate.candidateEmail, email_subject, message_body, is_html=False)
    except Exception as exc:
        logger.error(f"[Thunder] Email send failed for candidate {candidate.candidateID!r}: {exc}")
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="ai_message_sent",
        event_data={"channel": "email", "body": message_body, "auto_generated": True},
        triggered_by="ai_agent",
    ))
    db.flush()


# Real-world bug, reported directly by Avinash: a candidate asked "what
# roles do you have" for a Lead Guidewire Business Analyst-shaped
# background, and Thunder deflected to "I'll loop in our HR team"
# instead of actually looking at current openings -- because nothing
# fed it any job data at all, so the LLM had nothing to match against
# and correctly followed its own "say so plainly" fallback instruction.
# This is the fix: real open jobs, capped and ordered by newest first so
# the prompt stays a bounded size regardless of how many jobs exist.
MAX_OPEN_JOBS_IN_CONTEXT = 40


def _get_open_jobs_summary(db: Session) -> List[Dict]:
    """Real currently-open jobs (jobStatus != Closed), for Thunder to
    actually match a candidate against instead of deflecting to HR.
    "Lean" is treated as open (reduced but still active staffing), only
    "Closed" is excluded."""
    jobs: List[Jobs] = (
        db.query(Jobs)
        .filter(Jobs.jobStatus != "Closed")
        .order_by(Jobs.jobCreatedAt.desc())
        .limit(MAX_OPEN_JOBS_IN_CONTEXT)
        .all()
    )
    return [
        {
            "job_id": job.jobID,
            "title": job.jobTitle,
            "skills": job.jobSkills,
            "experience_required": job.jobExperience,
            "location": job.jobLocation,
            "positions_open": job.noOfPositions,
            "status": job.jobStatus,
        }
        for job in jobs
    ]


def build_candidate_context(db: Session, candidate: Candidate) -> Dict:
    """
    A1's buildCandidateContext() -- must be called before any future
    Thunder response-generation path produces a candidate-facing reply,
    so Thunder never re-asks something already answered on a different
    channel. Unifies email (ai_conversation_service) and WhatsApp
    (whatsapp_routing_service) history for the first time -- both
    already log into the same conversation_events table keyed by
    conversation_id, but nothing previously read them back as one
    ordered timeline.

    Also includes the candidate's own profile (title/skills/experience)
    and real currently-open jobs (see _get_open_jobs_summary) -- without
    both of these, Thunder has nothing concrete to match a candidate
    against when asked about openings, and correctly (per its own
    instructions) falls back to "I'll loop in HR" instead of answering.
    """
    conversations: List[CandidateConversation] = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate.candidateID)
        .order_by(CandidateConversation.id.asc())
        .all()
    )

    history: List[Dict] = []
    for conversation in conversations:
        events = (
            db.query(ConversationEvent)
            .filter(ConversationEvent.conversation_id == conversation.id)
            .order_by(ConversationEvent.created_at.asc(), ConversationEvent.id.asc())
            .all()
        )
        for event in events:
            data = event.event_data or {}
            history.append({
                "conversation_id": conversation.id,
                "event_type": event.event_type,
                "triggered_by": event.triggered_by,
                "channel": data.get("channel"),
                "body": data.get("body"),
                "created_at": event.created_at,
            })
    history.sort(key=lambda item: item["created_at"] or datetime.min)

    notes = (
        db.query(InternalNote)
        .filter(InternalNote.candidate_id == candidate.candidateID)
        .order_by(InternalNote.created_at.asc())
        .all()
    )

    active_conversation = next(
        (conv for conv in reversed(conversations) if conv.status != "closed"), None,
    )

    return {
        "candidate_id": candidate.candidateID,
        "message_history": history,
        "internal_notes": [
            {"content": note.content, "category": note.category, "created_at": note.created_at}
            for note in notes
        ],
        "desire_profile": None,  # not built yet -- EPIC-11 scope, see module docstring
        "active_conversation_id": active_conversation.id if active_conversation else None,
        "current_owner_type": active_conversation.owner_type if active_conversation else None,
        "current_owner_id": active_conversation.owner_id if active_conversation else None,
        "tenant_id": active_conversation.tenant_id if active_conversation else None,
        "candidate_profile": {
            "job_title": candidate.candidateJobTitle,
            "skills": candidate.candidateSkills,
            "experience_text": candidate.candidateExperience,
            "total_experience_months": candidate.total_experience_months,
            "current_location": candidate.candidateCurrentLocation,
        },
        "open_jobs": _get_open_jobs_summary(db),
    }


# ===========================================================================
# Reply generation -- the piece that was missing: turning
# build_candidate_context() + a new inbound message into Thunder's
# actual reply text, ready to hand to send_thunder_message().
# ===========================================================================

class ThunderReplyGenerationFailed(Exception):
    """Raised when Gemini can't be called (no API key) or returns nothing
    usable -- callers must not fall back to a fabricated reply."""


def _display_name(candidate: Candidate) -> str:
    parts = [candidate.candidateFirstName, candidate.candidateLastName]
    name = " ".join(p for p in parts if p).strip()
    return name or candidate.candidateEmail


CHANNEL_LABELS = {"whatsapp": "WhatsApp", "web_chat": "our website chat widget", "portal": "the candidate portal chat widget"}


def generate_thunder_reply(
    db: Session, candidate: Candidate, inbound_message: str, *, channel: str = "whatsapp",
) -> str:
    """
    Turns a candidate's new inbound message into Thunder's reply text.

    Always calls build_candidate_context() first (per that function's
    own docstring) so Thunder never re-asks something already answered
    on a different channel and never contradicts an HR-left internal
    note.

    Persona: reuses AI_AGENT_PERSONA ("friendly-hr") -- the same
    warm/professional BlitzenX HR voice already established in
    ai_conversation_service.py's candidate emails, per Avinash's
    explicit choice (2026-07-22) rather than inventing a separate
    "Thunder" voice from scratch.

    inbound_message is candidate-supplied, untrusted content -- routed
    through app.core.llm_prompt_safety.build_safe_prompt(), this
    codebase's non-negotiable for every LLM call (same discipline
    ai_conversation_service.py's extract_fields_from_reply() applies to
    email replies).
    """
    if not GEMINI_API_KEY:
        raise ThunderReplyGenerationFailed(
            "GEMINI_API_KEY not configured -- cannot generate a Thunder reply."
        )

    context = build_candidate_context(db, candidate)

    history_lines = "\n".join(
        f"[{item['channel'] or 'system'}] {item['event_type']} ({item['triggered_by']}): {item['body']}"
        for item in context["message_history"][-20:]
        if item.get("body")
    ) or "(no prior messages)"

    # Internal HR notes (context["internal_notes"]) are deliberately NOT
    # included in this prompt -- every candidate on every channel is an
    # external party, and "never repeat these verbatim" is a soft LLM
    # instruction, not a real guarantee against prompt injection or the
    # model simply erring. Data the LLM never sees can't leak. Per
    # Avinash's explicit instruction, 2026-07-23: "make sure external
    # candidates do not get any internal information."

    profile = context["candidate_profile"]
    profile_lines = (
        f"Current/last job title: {profile['job_title'] or 'not on file'}\n"
        f"Skills: {profile['skills'] or 'not on file'}\n"
        f"Experience: {profile['experience_text'] or 'not on file'}"
        + (
            f" ({profile['total_experience_months']} months verified)"
            if profile["total_experience_months"] is not None
            else ""
        )
        + f"\nLocation: {profile['current_location'] or 'not on file'}"
    )

    open_jobs = context["open_jobs"]
    open_jobs_lines = "\n".join(
        f"- [{job['job_id']}] {job['title']} | required skills: {job['skills']} | "
        f"required experience: {job['experience_required']} | location: {job['location']} | "
        f"positions open: {job['positions_open']}"
        for job in open_jobs
    ) or "(no roles currently open)"

    suspicious = flag_suspicious_patterns(inbound_message)
    if suspicious:
        logger.warning(f"[Thunder] Inbound message contains injection-shaped phrasing: {suspicious}")

    channel_label = CHANNEL_LABELS.get(channel, channel)
    # S-011/HRMS-0411 -- Thunder's name/persona are admin-configurable
    # per tenant (GET/PATCH /admin/tenant/ai-config), not hardcoded.
    # Falls back to "Thunder" + the default persona when unconfigured,
    # so this is a no-op for every tenant that hasn't set anything.
    agent_config = resolve_thunder_config(db, context.get("tenant_id"))
    instruction = f"""You are {agent_config['name']}, {_display_name(candidate)}'s AI hiring assistant at BlitzenX, replying over {channel_label}.
Persona: {agent_config['persona']}

Conversation history so far (oldest to newest):
{history_lines}

This candidate's own profile on file:
{profile_lines}

Currently open roles at BlitzenX (the ONLY roles you may reference -- never mention a role not in this list):
{open_jobs_lines}

Rules:
- Reply directly to the candidate's newest message, given below as data.
- Keep it to 2-4 short sentences, chat-appropriate (no email-style formatting, no subject line).
- Never invent facts about job offers, salary, or start dates that aren't already in the history above.
- Never share internal company information -- compensation bands, other candidates, headcount, hiring strategy, or anything not directly about this candidate's own application. If asked, say that's not something you can share and offer to loop in an HR team member.
- Do not re-ask for information the candidate already provided earlier in the history.
- When the candidate asks about open roles, or whether they're a fit for something, compare their profile above against the open-roles list above and answer directly and specifically -- name the matching role(s) by title if there's a real match on skills/experience/title, or say plainly that nothing currently open matches if there isn't. Do NOT deflect to "I'll loop in our HR team" for this kind of question when the open-roles list above already answers it -- only offer to loop in HR for things that list genuinely can't answer (e.g. compensation negotiation, an interview reschedule).
- If you don't have enough information to answer something outside of role-matching, say so plainly and offer to loop in an HR team member.

Write ONLY Thunder's reply text -- no labels, no quotation marks, no explanation."""

    prompt = build_safe_prompt(
        instruction=instruction,
        untrusted_label="CANDIDATE_MESSAGE",
        untrusted_content=inbound_message,
    )

    llm = ChatGoogleGenerativeAI(
        model=THUNDER_REPLY_MODEL,
        google_api_key=GEMINI_API_KEY,
        temperature=0.4,
        # No timeout at all is this client's own default (None) -- a
        # slow/stuck Gemini call then hangs the whole request instead of
        # failing. Real bug, reported live: "I need a Guidewire
        # developer" timed out with no bound. A WhatsApp-style 2-4
        # sentence reply doesn't need more than this to generate.
        timeout=30,
    )
    try:
        response = llm.invoke(prompt)
    except Exception as exc:
        raise ThunderReplyGenerationFailed(f"Gemini call failed or timed out: {exc}") from exc
    content = response.content
    if isinstance(content, list):
        reply_text = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        ).strip()
    else:
        reply_text = str(content).strip()

    if not reply_text:
        raise ThunderReplyGenerationFailed("Gemini returned an empty reply.")

    return reply_text


# ===========================================================================
# S-034/HRMS-0434 -- response validation + safe fallback.
#
# The doc's own literal spec (thunder_response_log table, prompt_type
# framework, explainability panel) depends on HRMS-0431/0433, which
# don't exist in this codebase -- generate_thunder_reply() above already
# IS this codebase's real response-generation path (context-aware via
# build_candidate_context(), ownership-gated via send_thunder_message()).
# What was genuinely missing, and is real business value on its own:
# validating the LLM's output before it reaches a candidate, and never
# leaving a candidate with no reply at all when generation fails.
#
# Deliberately NOT used by run_test_chat_turn() -- that internal demo
# tool surfaces ThunderReplyGenerationFailed as a real error so the HR
# tester sees what actually broke (e.g. a missing GEMINI_API_KEY),
# rather than silently swallowing it behind the fallback message.
# ===========================================================================

SAFE_FALLBACK_MESSAGE = "Thank you for your message. Our recruiting team will be in touch shortly."
MIN_REPLY_LENGTH = 10
MAX_REPLY_LENGTH = 4096
_TEMPLATE_VAR_RE = re.compile(r"\{\{.*?\}\}")


def validate_thunder_reply(text: Optional[str]) -> bool:
    """AC: minimum 10 chars, maximum 4096 (WhatsApp limit), no un-replaced
    {{...}} template variables."""
    if not text:
        return False
    if not (MIN_REPLY_LENGTH <= len(text) <= MAX_REPLY_LENGTH):
        return False
    if _TEMPLATE_VAR_RE.search(text):
        return False
    return True


def generate_thunder_reply_with_fallback(
    db: Session, candidate: Candidate, inbound_message: str, *, channel: str = "whatsapp",
    conversation: Optional[CandidateConversation] = None,
) -> Tuple[str, bool]:
    """
    Generates a validated Thunder reply, regenerating once on a failed
    or invalid attempt. Returns (reply_text, used_fallback).

    A candidate must never receive no response due to a technical
    failure -- if both attempts fail or fail validation, returns the
    hardcoded SAFE_FALLBACK_MESSAGE (never LLM-generated, never fails).

    S-034/HRMS-0434 BR-01: when `conversation` is supplied, ownership is
    checked FIRST -- before build_candidate_context() or any LLM call --
    so a recruiter-owned conversation never burns a Gemini call. Raises
    ConversationOwnedByHuman in that case (same exception
    send_thunder_message() itself raises); callers should catch it and
    skip sending, not treat it as a failure needing the safe fallback.
    `conversation` is optional (default None, ownership unchecked here)
    so existing callers that already gate ownership at their own
    send_thunder_message() call -- or don't have a conversation object
    yet -- are unaffected.

    S-034's revised canonical spec ("Thunder never responds cold"): if
    build_candidate_context() itself fails (generate_thunder_reply()
    calls it as its very first step), that's not a retry-and-hope
    situation -- escalate to the recruiter queue via
    conversation_state_service.escalate() (when a conversation was
    supplied) and go straight to the safe fallback, no second attempt.
    """
    if conversation is not None and not is_ai_owner(conversation):
        raise ConversationOwnedByHuman(
            f"Conversation {conversation.id} is owned by {conversation.owner_type}:"
            f"{conversation.owner_id} -- Thunder may not generate a reply."
        )

    context_build_failed = False
    for attempt in range(2):
        try:
            reply = generate_thunder_reply(db, candidate, inbound_message, channel=channel)
        except ThunderReplyGenerationFailed as exc:
            logger.error(f"[Thunder] reply generation failed (attempt {attempt + 1}): {exc}")
            continue
        except Exception as exc:
            logger.error(f"[Thunder] context build or unexpected failure (attempt {attempt + 1}): {exc}")
            context_build_failed = True
            break
        if validate_thunder_reply(reply):
            return reply, False
        logger.warning(
            f"[Thunder] generated reply failed validation (attempt {attempt + 1}): {reply!r}"
        )

    if context_build_failed and conversation is not None:
        escalate_conversation(db, conversation, reason="context_build_failed", triggered_by="ai_agent")
        db.commit()

    return SAFE_FALLBACK_MESSAGE, True


# ===========================================================================
# S-041/HRMS-0441 -- proactive follow-up generation.
#
# generate_thunder_reply() always replies TO something -- it builds its
# prompt around inbound_message via build_safe_prompt() (the untrusted-
# content wrapper). A follow-up has no inbound message at all: Thunder
# is speaking first, unprompted, because the candidate went silent. So
# this is a real second generation path, not a call to the existing one
# with an empty message -- reuses the same context/config/validation/
# fallback machinery, but its own instruction framing and no untrusted-
# content wrapping (there's no candidate text to inject).
# ===========================================================================

SAFE_FOLLOWUP_FALLBACK_MESSAGE = (
    "Just checking in -- we haven't heard back and wanted to make sure you saw "
    "our last message. Let us know if you have any questions, or if you're "
    "still interested in moving forward!"
)

# Data Mapping table: follow_up_number -> message tone.
FOLLOWUP_TONE_BY_NUMBER = {
    1: "This is a gentle, warm first follow-up -- assume they simply missed the earlier message.",
    2: "This is the second follow-up -- be a little more direct than the first, while staying polite and professional.",
    3: "This is the third and FINAL follow-up before we stop reaching out -- make that plain (politely), so they know this is their last chance to respond if they're still interested.",
}


def generate_followup_message(db: Session, candidate: Candidate, follow_up_number: int, *, channel: str = "whatsapp") -> str:
    """Step 3.4's generateThunderResponse(..., 'FOLLOW_UP', {follow_up_number}).
    Raises ThunderReplyGenerationFailed on any failure -- same contract
    as generate_thunder_reply(), never a fabricated reply."""
    if not GEMINI_API_KEY:
        raise ThunderReplyGenerationFailed("GEMINI_API_KEY not configured -- cannot generate a follow-up message.")

    context = build_candidate_context(db, candidate)

    history_lines = "\n".join(
        f"[{item['channel'] or 'system'}] {item['event_type']} ({item['triggered_by']}): {item['body']}"
        for item in context["message_history"][-20:]
        if item.get("body")
    ) or "(no prior messages)"

    channel_label = CHANNEL_LABELS.get(channel, channel)
    agent_config = resolve_thunder_config(db, context.get("tenant_id"))
    tone = FOLLOWUP_TONE_BY_NUMBER.get(follow_up_number, FOLLOWUP_TONE_BY_NUMBER[3])

    instruction = f"""You are {agent_config['name']}, {_display_name(candidate)}'s AI hiring assistant at BlitzenX, writing a follow-up message over {channel_label}. The candidate has not replied to your last message.
Persona: {agent_config['persona']}

Conversation history so far (oldest to newest):
{history_lines}

{tone}

Rules:
- This is a proactive check-in, not a reply -- there is no new candidate message to respond to.
- Keep it to 1-3 short sentences, chat-appropriate (no email-style formatting, no subject line).
- Never invent facts about job offers, salary, or start dates that aren't already in the history above.
- Do not re-ask for information the candidate already provided earlier in the history.
- Write ONLY the follow-up message text -- no labels, no quotation marks, no explanation."""

    llm = ChatGoogleGenerativeAI(
        model=THUNDER_REPLY_MODEL,
        google_api_key=GEMINI_API_KEY,
        temperature=0.4,
        timeout=30,
    )
    try:
        response = llm.invoke(instruction)
    except Exception as exc:
        raise ThunderReplyGenerationFailed(f"Gemini call failed or timed out: {exc}") from exc
    content = response.content
    if isinstance(content, list):
        reply_text = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        ).strip()
    else:
        reply_text = str(content).strip()

    if not reply_text:
        raise ThunderReplyGenerationFailed("Gemini returned an empty follow-up message.")

    return reply_text


def generate_followup_message_with_fallback(
    db: Session, candidate: Candidate, follow_up_number: int, *, channel: str = "whatsapp",
    conversation: Optional[CandidateConversation] = None,
) -> Tuple[str, bool]:
    """Same shape as generate_thunder_reply_with_fallback(): BR-01-style
    ownership check first (raises ConversationOwnedByHuman before any
    LLM call), retry-once, validate, hardcoded safe fallback on
    repeated failure -- never leaves a follow-up unsent due to a
    technical failure. Unlike a reply, "no fallback at all" isn't an
    option here since Step 3.4/BR-01 require sending SOMETHING for
    every due follow-up; SAFE_FOLLOWUP_FALLBACK_MESSAGE (not the
    reply-shaped SAFE_FALLBACK_MESSAGE) is used instead."""
    if conversation is not None and not is_ai_owner(conversation):
        raise ConversationOwnedByHuman(
            f"Conversation {conversation.id} is owned by {conversation.owner_type}:"
            f"{conversation.owner_id} -- Thunder may not generate a follow-up."
        )

    for attempt in range(2):
        try:
            message = generate_followup_message(db, candidate, follow_up_number, channel=channel)
        except ThunderReplyGenerationFailed as exc:
            logger.error(f"[Thunder] follow-up generation failed (attempt {attempt + 1}): {exc}")
            continue
        except Exception as exc:
            logger.error(f"[Thunder] follow-up context build or unexpected failure (attempt {attempt + 1}): {exc}")
            break
        if validate_thunder_reply(message):
            return message, False
        logger.warning(f"[Thunder] generated follow-up failed validation (attempt {attempt + 1}): {message!r}")

    return SAFE_FOLLOWUP_FALLBACK_MESSAGE, True


# ===========================================================================
# S-045/HRMS-0445 -- reactivation message generation.
#
# A second proactive-generation path, distinct from a follow-up: it
# needs a genuinely different angle/tone (fresh, warm, no reference to
# the prior silence) and real days-since-contact context. Reuses the
# same context/config/validation/fallback machinery as
# generate_followup_message() -- see that function's own comment for
# why this isn't built as a call to it with different arguments.
# ===========================================================================

SAFE_REACTIVATION_FALLBACK_MESSAGE = (
    "Hi again! It's been a little while, but we wanted to reach back out -- "
    "we'd still love to hear from you if you're interested in exploring "
    "opportunities with us. No pressure at all, just let us know!"
)


def generate_reactivation_message(db: Session, candidate: Candidate, days_since_last_contact: int, *, channel: str = "whatsapp") -> str:
    """Step 1's REACTIVATION prompt, adapted to a direct instruction
    string (no prompt-type catalog exists in this codebase's real
    thunder_service -- see prompt_framework_service's own module
    docstring on why the ~7 existing ad-hoc-prompting services,
    including this one, were never retrofitted onto that framework).
    Raises ThunderReplyGenerationFailed on any failure -- same contract
    as generate_thunder_reply()/generate_followup_message()."""
    if not GEMINI_API_KEY:
        raise ThunderReplyGenerationFailed("GEMINI_API_KEY not configured -- cannot generate a reactivation message.")

    context = build_candidate_context(db, candidate)

    channel_label = CHANNEL_LABELS.get(channel, channel)
    agent_config = resolve_thunder_config(db, context.get("tenant_id"))

    instruction = f"""You are {agent_config['name']}, {_display_name(candidate)}'s AI hiring assistant at BlitzenX, writing a reactivation message over {channel_label}. It has been {days_since_last_contact} days since this candidate last heard from us, and they never replied to our earlier messages.
Persona: {agent_config['persona']}

Rules:
- Write a fresh, warm message with a genuinely different angle than a typical follow-up -- do NOT reference or apologize for the earlier silence, do NOT say things like "we haven't heard back" or "following up again."
- Acknowledge that some time has passed in a natural way, and offer new context or value (e.g. new roles, renewed interest) rather than repeating the original pitch verbatim.
- Keep it to 2-3 short sentences, chat-appropriate (no email-style formatting, no subject line).
- Never invent facts about job offers, salary, or start dates.
- Write ONLY the message text -- no labels, no quotation marks, no explanation."""

    llm = ChatGoogleGenerativeAI(
        model=THUNDER_REPLY_MODEL,
        google_api_key=GEMINI_API_KEY,
        temperature=0.5,
        timeout=30,
    )
    try:
        response = llm.invoke(instruction)
    except Exception as exc:
        raise ThunderReplyGenerationFailed(f"Gemini call failed or timed out: {exc}") from exc
    content = response.content
    if isinstance(content, list):
        reply_text = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        ).strip()
    else:
        reply_text = str(content).strip()

    if not reply_text:
        raise ThunderReplyGenerationFailed("Gemini returned an empty reactivation message.")

    return reply_text


def generate_reactivation_message_with_fallback(
    db: Session, candidate: Candidate, days_since_last_contact: int, *, channel: str = "whatsapp",
    conversation: Optional[CandidateConversation] = None,
) -> Tuple[str, bool]:
    """Same shape as generate_followup_message_with_fallback(): ownership
    check first, retry-once, validate, hardcoded safe fallback --
    reactivation must never leave a candidate without an actual
    message due to a technical failure."""
    if conversation is not None and not is_ai_owner(conversation):
        raise ConversationOwnedByHuman(
            f"Conversation {conversation.id} is owned by {conversation.owner_type}:"
            f"{conversation.owner_id} -- Thunder may not generate a reactivation message."
        )

    for attempt in range(2):
        try:
            message = generate_reactivation_message(db, candidate, days_since_last_contact, channel=channel)
        except ThunderReplyGenerationFailed as exc:
            logger.error(f"[Thunder] reactivation generation failed (attempt {attempt + 1}): {exc}")
            continue
        except Exception as exc:
            logger.error(f"[Thunder] reactivation context build or unexpected failure (attempt {attempt + 1}): {exc}")
            break
        if validate_thunder_reply(message):
            return message, False
        logger.warning(f"[Thunder] generated reactivation message failed validation (attempt {attempt + 1}): {message!r}")

    return SAFE_REACTIVATION_FALLBACK_MESSAGE, True


# ===========================================================================
# "Test Thunder" mode -- lets a real internal user chat with Thunder
# without a live WhatsApp Business API (none is provisioned in this
# codebase -- see whatsapp_routing_service's module docstring). The
# mock transport below is injected as send_thunder_message()'s
# whatsapp_client, so R-08, consent, and the debounce guard all run
# exactly as they would for a real send; only the wire transport at
# the very bottom is fake, and it says so.
# ===========================================================================

# The candidate ID stays obviously synthetic ("THUNDER-TEST-<UserID>")
# so this row can never be mistaken for a real candidate intake. But
# the rest of the identity (name/email/WhatsApp number) is derived from
# WHICHEVER internal user is actually logged in and testing -- not one
# shared hardcoded identity. Two different staff members testing
# Thunder each get addressed as themselves, not as whoever happened to
# test first (that was a real bug: an earlier version of this hardcoded
# one person's real contact info as a single global test candidate, so
# every tester saw Thunder reply to that same identity regardless of
# who was actually logged in). The consent record is still
# captured_by="thunder_test_chat_demo_setup", i.e. explicitly logged as
# a demo/test bootstrap action, not a real candidate opt-in flow.
TEST_CANDIDATE_ID_PREFIX = "THUNDER-TEST-"
DEFAULT_TEST_MOBILE = "+10005559999"  # used only if the tester has no whatsapp_number registered -- never dialed


def test_candidate_id_for(tenant_id: str) -> str:
    return f"{TEST_CANDIDATE_ID_PREFIX}{tenant_id}"[:50]


def _split_display_name(name: Optional[str], fallback: str) -> Tuple[str, str]:
    parts = (name or "").split()
    if not parts:
        return fallback, ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _unique_test_email(db: Session, current_user: Users, candidate_id: str) -> str:
    """Prefer the tester's own real email, so Thunder addresses them as
    themselves. candidateEmail is unique, so fall back to an obviously-
    test alias only in the unlikely event that email is already taken
    by a different candidate row."""
    existing = db.query(Candidate).filter(Candidate.candidateEmail == current_user.UserEmail).first()
    if existing is None or existing.candidateID == candidate_id:
        return current_user.UserEmail
    return f"thunder-test+{current_user.UserID}@blitzenx-internal-test.invalid"


def mock_whatsapp_client(to_number: str, from_number: str, body: str) -> bool:
    """
    Honest mock transport for 'Test Thunder' mode: records the send to
    the log and reports it delivered, but never calls a real WhatsApp
    API -- none is provisioned in this codebase. Do not use this
    outside test-chat mode.
    """
    logger.info(f"[ThunderTestChat] MOCK send | to={to_number} from={from_number} | {body[:120]!r}")
    return True


def get_or_create_test_candidate(db: Session, current_user: Users) -> Candidate:
    """
    send_thunder_message() hard-blocks without an active
    whatsapp_outreach ConsentRecord (A1) -- this creates that consent
    for an obviously-labeled test/demo candidate, explicitly, rather
    than bypassing the real gate to make testing convenient.

    One test candidate per internal tester (keyed off current_user.
    UserID), with that tester's own name/email/WhatsApp number -- see
    the module note above on why this isn't a single shared identity.
    """
    candidate_id = test_candidate_id_for(current_user.UserID)
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if candidate:
        return candidate

    first_name, last_name = _split_display_name(
        current_user.UserName, fallback=current_user.UserEmail.split("@")[0],
    )

    candidate = Candidate(
        candidateID=candidate_id,
        candidateFirstName=first_name,
        candidateLastName=last_name,
        candidateEmail=_unique_test_email(db, current_user, candidate_id),
        candidateMobile=current_user.whatsapp_number or DEFAULT_TEST_MOBILE,
        candidatePassword=get_password_hash(secrets.token_urlsafe(24)),
    )
    db.add(candidate)
    db.flush()

    db.add(ConsentRecord(
        subject_type="candidate", subject_id=candidate_id,
        consent_type=WHATSAPP_OUTREACH_CONSENT_TYPE, consent_given=True,
        captured_by="thunder_test_chat_demo_setup",
    ))
    db.flush()
    return candidate


def get_or_create_test_conversation(db: Session, tenant_id: str) -> CandidateConversation:
    """One test conversation per internal tester (scoped by tenant_id),
    so different staff testing Thunder don't share a thread."""
    candidate_id = test_candidate_id_for(tenant_id)
    conversation = (
        db.query(CandidateConversation)
        .filter(
            CandidateConversation.candidate_id == candidate_id,
            CandidateConversation.tenant_id == tenant_id,
            CandidateConversation.status != "closed",
        )
        .order_by(CandidateConversation.id.desc())
        .first()
    )
    if conversation:
        return conversation

    conversation = CandidateConversation(
        tenant_id=tenant_id,
        candidate_id=candidate_id,
        status="open",
        ai_agent_name=AI_AGENT_NAME,
        channel_preference="whatsapp",
        owner_type="ai_agent",
        owner_id=AI_AGENT_NAME,
        escalation_state="none",
        summary="Test Thunder demo conversation.",
    )
    db.add(conversation)
    db.flush()
    return conversation


def run_test_chat_turn(db: Session, *, current_user: Users, message_body: str) -> Dict:
    """
    One full 'Test Thunder' turn: log the tester's message as if it
    came from the candidate, generate Thunder's reply with the real
    LLM (build_candidate_context() -> generate_thunder_reply()), then
    send it back through the real send_thunder_message() gate -- R-08,
    consent, and the 60s debounce all still apply; only the outbound
    WhatsApp transport is mocked.

    Raises ConsentNotGiven / DuplicateMessageSuppressed /
    ConversationOwnedByHuman exactly as a real send would (e.g. if a
    recruiter takes over this test conversation, Thunder is blocked
    here too -- that's the governance working, not a bug to swallow).
    """
    candidate = get_or_create_test_candidate(db, current_user)
    conversation = get_or_create_test_conversation(db, current_user.UserID)

    inbound_event = ConversationEvent(
        conversation_id=conversation.id,
        event_type="candidate_reply",
        event_data={"channel": "whatsapp", "body": message_body},
        triggered_by="candidate",
    )
    db.add(inbound_event)
    db.flush()

    # S-069/HRMS-0469 -- re-detect channel preference on every inbound reply.
    from app.services.channel_preference_service import detect_channel_preference
    detect_channel_preference(db, conversation)

    reply_text = generate_thunder_reply(db, candidate, message_body)

    reply_event = send_thunder_message(
        db, conversation, candidate, reply_text,
        sender_type="ai_agent",
        whatsapp_client=mock_whatsapp_client,
        auto_generated=True,
    )

    db.commit()

    return {
        "conversation_id": conversation.id,
        "candidate_message": message_body,
        "thunder_reply": reply_text,
        "mock_send": True,
        "delivered": bool(reply_event.event_data.get("delivered")),
        "event_id": reply_event.id,
        "created_at": reply_event.created_at,
    }


def get_test_chat_history(db: Session, tenant_id: str) -> List[Dict]:
    """Full message history for this tester's current (non-closed) test
    conversation, in display order. Empty list if none exists yet or
    the last one was reset_test_chat()'d."""
    conversation = (
        db.query(CandidateConversation)
        .filter(
            CandidateConversation.candidate_id == test_candidate_id_for(tenant_id),
            CandidateConversation.tenant_id == tenant_id,
            CandidateConversation.status != "closed",
        )
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
    return [
        {
            "sender": (
                "candidate" if event.event_type == "candidate_reply"
                else "thunder" if event.event_type == "ai_message_sent"
                else "hr"
            ),
            "body": (event.event_data or {}).get("body", ""),
            "created_at": event.created_at,
        }
        for event in events
    ]


def reset_test_chat(db: Session, tenant_id: str) -> None:
    """Closes this tester's current test conversation so the next
    message starts a fresh thread. Non-destructive -- the closed
    conversation and its events stay in the DB (same 'deactivate, never
    delete' convention as the rest of this codebase), just excluded
    from get_or_create_test_conversation()'s and
    get_test_chat_history()'s active-conversation lookups."""
    db.query(CandidateConversation).filter(
        CandidateConversation.candidate_id == test_candidate_id_for(tenant_id),
        CandidateConversation.tenant_id == tenant_id,
        CandidateConversation.status != "closed",
    ).update({"status": "closed"})
    db.commit()
