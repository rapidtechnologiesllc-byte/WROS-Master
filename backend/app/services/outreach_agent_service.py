"""
import logging
HRMS-1104 -- Automated Outreach Agent (Phase 3 Workstream 1 / Recruit).

Bridges HRMS-1103's promoted candidates to Thunder's conversation
engine. Every send goes through app.services.thunder_service.
send_thunder_message() (BR-1104-01) -- this agent composes and times
messages, it never implements its own send logic, matching Thunder's
own "no bypass" rule and reusing its R-08/consent/debounce gates rather
than duplicating them.

Note on tenant_id: OutreachSequence.tenant_id (Integer, FK tenants.id)
and CandidateConversation.tenant_id (String, actually users.UserID) are
two different, already-documented conventions in this codebase (see
whatsapp_routing_service.py's module docstring). start_outreach_sequence()
takes both explicitly rather than silently deriving one from the other.

Only 'whatsapp' has a real transport wired in thunder_service today.
When the fallback sequence advances to 'linkedin' or 'email',
send_thunder_message() raises NotImplementedError -- caught here and
recorded as a skipped touch (channel not provisioned), distinct from an
R-08 BLOCKED_OWNERSHIP halt. Not in scope to fake those transports (the
story's own "Not In Scope" section rules out raw channel API calls
entirely -- sendThunderMessage() only).
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.demand import Demand
from app.models.outreach import MAX_TOUCHES, OutreachSequence
from app.services.ai_conversation_service import AI_AGENT_NAME
from app.services.notification_service import _is_within_business_hours
from app.services.thunder_service import (
    ConsentNotGiven,
    DuplicateMessageSuppressed,
    ThunderPausedError,
    has_active_consent,
    send_thunder_message,
)
from app.services.whatsapp_routing_service import ConversationOwnedByHuman

DEBOUNCE_WINDOW_HOURS = 24   # Step 2
RESPONSE_WAIT_HOURS = 48     # Step 6

logger = logging.getLogger(__name__)

class OutreachDebounced(Exception):
    """Step 2: an active sequence already exists for this candidate+demand
    within the debounce window -- do not start a second one."""


def _get_or_create_conversation(db: Session, candidate: Candidate, *, conversation_tenant_id: str) -> CandidateConversation:
    conversation = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate.candidateID)
        .order_by(CandidateConversation.id.desc())
        .first()
    )
    if conversation is not None:
        return conversation

    conversation = CandidateConversation(
        tenant_id=conversation_tenant_id, candidate_id=candidate.candidateID,
        status="open", ai_agent_name=AI_AGENT_NAME, channel_preference="whatsapp",
        owner_type="ai_agent", owner_id=AI_AGENT_NAME,
    )
    db.add(conversation)
    db.flush()
    return conversation


def _has_active_sequence_within_debounce(db: Session, candidate_id: str, demand_id: str) -> bool:
    # Compared against real wall-clock time, not a caller-supplied `now`
    # -- OutreachSequence.created_at is a real DB-server timestamp
    # (func.now()), same reasoning as thunder_service's debounce check.
    window_start = datetime.utcnow() - timedelta(hours=DEBOUNCE_WINDOW_HOURS)
    return (
        db.query(OutreachSequence)
        .filter(
            OutreachSequence.candidate_id == candidate_id,
            OutreachSequence.demand_id == demand_id,
            OutreachSequence.created_at >= window_start,
        )
        .first()
        is not None
    )


def _candidate_has_replied(db: Session, candidate_id: str, *, since: Optional[datetime]) -> bool:
    if since is None:
        return False
    conversation = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate_id)
        .order_by(CandidateConversation.id.desc())
        .first()
    )
    if conversation is None:
        return False
    return (
        db.query(ConversationEvent)
        .filter(
            ConversationEvent.conversation_id == conversation.id,
            ConversationEvent.triggered_by == "candidate",
            ConversationEvent.created_at >= since,
        )
        .first()
        is not None
    )


def start_outreach_sequence(
    db: Session,
    candidate: Candidate,
    demand: Demand,
    *,
    tenant_id=None,
    conversation_tenant_id: Optional[str] = None,
    message_composer: Optional[Callable[[dict], dict]] = None,
    router_evaluate: Optional[Callable[..., object]] = None,
    whatsapp_client=None,
    now: Optional[datetime] = None,
) -> OutreachSequence:
    """
    Steps 2-5. Debounced per candidate+demand (24h, real wall-clock).
    BR-1104-03: consent is checked BEFORE composition, not just before
    send -- send_thunder_message() re-checks it again regardless, since
    a snapshot is never trusted alone (Data Mapping note).
    """
    now = now or datetime.utcnow()

    if _has_active_sequence_within_debounce(db, candidate.candidateID, demand.id):
        raise OutreachDebounced(
            f"An active outreach sequence already exists for candidate "
            f"{candidate.candidateID} + demand {demand.id} within the last "
            f"{DEBOUNCE_WINDOW_HOURS}h."
        )

    consent_ok = has_active_consent(db, candidate.candidateID)

    sequence = OutreachSequence(
        tenant_id=tenant_id, candidate_id=candidate.candidateID, demand_id=demand.id,
        primary_channel="whatsapp", fallback_sequence=json.dumps(["linkedin", "email"]),
        consent_given_snapshot=consent_ok, status="QUEUED",
    )
    db.add(sequence)
    db.flush()

    if not consent_ok:
        # BR-1104-03: no message is composed, and nothing is sent.
        sequence.blocked_reason = "Consent not given -- no message composed."
        db.add(sequence)
        return sequence

    message_text = None
    if message_composer is not None:
        try:
            result = message_composer({
                "candidate_id": candidate.candidateID,
                "demand_id": demand.id,
                "required_skills": demand.required_skills,
            })
            message_text = result.get("message_text")
        except Exception:
            message_text = None
    if not message_text:
        sequence.blocked_reason = "Message composition unavailable -- queued for manual recruiter compose."
        db.add(sequence)
        return sequence

    sequence.message_text = message_text
    db.add(sequence)

    return _attempt_send(
        db, sequence, candidate, demand, channel="whatsapp",
        conversation_tenant_id=conversation_tenant_id,
        router_evaluate=router_evaluate, whatsapp_client=whatsapp_client, now=now,
    )


def _attempt_send(
    db: Session, sequence: OutreachSequence, candidate: Candidate, demand: Demand,
    *, channel: str, conversation_tenant_id, router_evaluate, whatsapp_client, now: datetime,
) -> OutreachSequence:
    if sequence.touch_count >= MAX_TOUCHES:
        sequence.status = "COMPLETE_NO_RESPONSE"
        db.add(sequence)
        return sequence

    # AC-6: outside business hours and not p1_emergency -> deferred, not
    # dropped. Demand.p1_emergency doesn't exist as a column in this
    # codebase yet (02-DATA-MODEL.md's sketch has it, the built Demand
    # model doesn't) -- defaults False via getattr rather than assumed.
    p1_emergency = bool(getattr(demand, "p1_emergency", False))
    if not p1_emergency and not _is_within_business_hours(now, candidate.timezone):
        sequence.status = "QUEUED"
        db.add(sequence)
        return sequence

    if router_evaluate is not None:
        try:
            router_evaluate(
                agent_id="HRMS-1104", entity_type="candidate", entity_id=candidate.candidateID,
                action_type="outreach_send", risk_tier="LOW", tenant_id=sequence.tenant_id,
            )
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            # Covers both ActionBlocked (e.g. BR-1101-01's outreach-vs-
            # Core-Pull collision) and any other router-raised halt --
            # do not send this touch; leave it retryable later.
            sequence.blocked_reason = f"Orchestration Router blocked this send: {exc}"
            db.add(sequence)
            return sequence

            conversation = _get_or_create_conversation(
        db, candidate, conversation_tenant_id=conversation_tenant_id or candidate.candidateID,
    )

    try:
        send_thunder_message(
            db, conversation, candidate, sequence.message_text,
            sender_type="ai_agent", channel=channel, whatsapp_client=whatsapp_client,
        )
    except ConversationOwnedByHuman:
        # BR-1104-02: halt, do NOT auto-switch channel -- escalate instead.
        sequence.status = "BLOCKED_OWNERSHIP"
        sequence.blocked_reason = "R-08: conversation is owned by a human -- escalated to recruiter queue."
        db.add(sequence)
        return sequence
    except ConsentNotGiven:
        sequence.blocked_reason = "Consent revoked between composition and send -- send blocked."
        db.add(sequence)
        return sequence
    except DuplicateMessageSuppressed:
        sequence.blocked_reason = "Duplicate message suppressed by Thunder's debounce window."
        db.add(sequence)
        return sequence
    except ThunderPausedError:
        # S-075/HRMS-0475 BR-01/BR-03: paused per-candidate or globally --
        # do not send this touch; leave it retryable for a later run,
        # same posture as the ownership-lock branch above.
        sequence.blocked_reason = "Thunder is paused for this candidate or tenant -- touch skipped."
        db.add(sequence)
        return sequence
    except NotImplementedError:
        # Channel not provisioned (linkedin/email) -- not an R-08 lock,
        # just an unavailable transport. Logged, not faked.
        sequence.blocked_reason = f"Channel '{channel}' has no transport wired -- touch skipped."
        db.add(sequence)
        return sequence

    sequence.status = "SENT"
    sequence.sent_via = "sendThunderMessage"  # BR-1104-01/AC-5 -- constant, for audit clarity
    sequence.touch_count += 1
    sequence.last_touch_sent_at = now
    db.add(sequence)
    return sequence


def advance_outreach_sequence(
    db: Session,
    sequence: OutreachSequence,
    candidate: Candidate,
    demand: Demand,
    *,
    conversation_tenant_id: Optional[str] = None,
    router_evaluate: Optional[Callable[..., object]] = None,
    whatsapp_client=None,
    now: Optional[datetime] = None,
) -> OutreachSequence:
    """
    Step 6 -- the idempotent function a cron would call per open
    sequence (not wired to a scheduler here, same posture as every
    other cron-shaped story in this codebase). Checks for a candidate
    reply since the last touch; if none after RESPONSE_WAIT_HOURS,
    advances to the next fallback channel, capped at MAX_TOUCHES.
    """
    now = now or datetime.utcnow()

    if sequence.status not in ("SENT", "QUEUED"):
        return sequence  # terminal (RESPONDED/COMPLETE_NO_RESPONSE) or BLOCKED_OWNERSHIP -- nothing to advance

    if _candidate_has_replied(db, candidate.candidateID, since=sequence.last_touch_sent_at):
        sequence.status = "RESPONDED"
        db.add(sequence)
        return sequence

    if sequence.status == "SENT":
        if sequence.last_touch_sent_at is None or now - sequence.last_touch_sent_at < timedelta(hours=RESPONSE_WAIT_HOURS):
            return sequence  # not yet time to advance

    if sequence.touch_count >= MAX_TOUCHES:
        sequence.status = "COMPLETE_NO_RESPONSE"
        db.add(sequence)
        return sequence

    remaining = json.loads(sequence.fallback_sequence or "[]")
    if not remaining:
        sequence.status = "COMPLETE_NO_RESPONSE"
        db.add(sequence)
        return sequence

    next_channel = remaining.pop(0)
    sequence.fallback_sequence = json.dumps(remaining)
    sequence.primary_channel = next_channel
    db.add(sequence)

    return _attempt_send(
        db, sequence, candidate, demand, channel=next_channel,
        conversation_tenant_id=conversation_tenant_id,
        router_evaluate=router_evaluate, whatsapp_client=whatsapp_client, now=now,
    )
