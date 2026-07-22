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
from app.models.user import Users
from app.services.ai_conversation_service import AI_AGENT_NAME, AI_AGENT_PERSONA
from app.services.whatsapp_routing_service import send_whatsapp_message  # noqa: F401 -- re-exported gate

WHATSAPP_OUTREACH_CONSENT_TYPE = "whatsapp_outreach"
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
    own send logic. R-08 (ownership lock) is enforced by
    send_whatsapp_message() below, not reimplemented here; this function
    adds the consent and debounce checks in front of it.

    channel: only 'whatsapp' has a real transport wired in this
    codebase (see whatsapp_routing_service's own scope note on email/SMS
    not being provisioned). Kept as a parameter rather than hardcoded so
    a future transport doesn't require every caller to change.
    """
    if channel != "whatsapp":
        raise NotImplementedError(
            f"send_thunder_message: no transport wired for channel '{channel}' in this "
            f"codebase yet -- only 'whatsapp' does."
        )

    if not has_active_consent(db, candidate.candidateID):
        raise ConsentNotGiven(
            f"Candidate {candidate.candidateID} has no active {WHATSAPP_OUTREACH_CONSENT_TYPE} "
            f"consent record -- send rejected."
        )

    if _is_duplicate_send(db, conversation, message_body):
        raise DuplicateMessageSuppressed(
            f"An identical message was already sent on conversation {conversation.id} "
            f"within the last {DEBOUNCE_SECONDS}s -- suppressed."
        )

    return send_whatsapp_message(
        db, conversation, candidate, message_body,
        sender_type=sender_type, sender_id=sender_id,
        whatsapp_client=whatsapp_client, auto_generated=auto_generated,
    )


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


def generate_thunder_reply(db: Session, candidate: Candidate, inbound_message: str) -> str:
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

    notes_lines = "\n".join(
        f"- {note['content']}" for note in context["internal_notes"]
    ) or "(none)"

    suspicious = flag_suspicious_patterns(inbound_message)
    if suspicious:
        logger.warning(f"[Thunder] Inbound message contains injection-shaped phrasing: {suspicious}")

    instruction = f"""You are Thunder, {_display_name(candidate)}'s AI hiring assistant at BlitzenX, replying over WhatsApp.
Persona: {AI_AGENT_PERSONA} -- warm, professional, concise. Same voice BlitzenX HR uses in candidate emails.

Conversation history so far (oldest to newest):
{history_lines}

Internal HR notes (context only -- never repeat these verbatim to the candidate):
{notes_lines}

Rules:
- Reply directly to the candidate's newest message, given below as data.
- Keep it to 2-4 short sentences, WhatsApp-appropriate (no email-style formatting, no subject line).
- Never invent facts about job offers, salary, or start dates that aren't already in the history or notes above.
- Do not re-ask for information the candidate already provided earlier in the history.
- If you don't have enough information to answer, say so plainly and offer to loop in an HR team member.

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
    )
    response = llm.invoke(prompt)
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
