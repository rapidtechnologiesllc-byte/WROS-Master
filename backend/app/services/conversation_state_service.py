"""
import logging
S-018/HRMS-0418 -- Conversation State Manager.

Adapted to this codebase's real state model, which is deliberately
simpler than -- and predates -- the spec's fictional 10-state enum
(INITIATED/QUALIFYING/QUALIFIED/INTERVIEW_SCHEDULED/OFFER_SENT/
PREBOARDING/COMPLETED/ESCALATED/PAUSED/WITHDRAWN):

- CandidateConversation really has THREE orthogonal axes, not one
  enum -- already established and tested this way across S-002/S-003/
  S-004/S-011/S-015/S-016:
    1. status            -- "open" | "awaiting_candidate" | "closed"
                             (the conversation's own lifecycle)
    2. escalation_state  -- "none" | "pending" | "escalated" | "resolved"
    3. owner_type/owner_id -- "ai_agent" | "hr_user"
                             (who is currently driving the conversation)

  The spec's ESCALATED/PAUSED states map onto axes 2 and 3, not axis 1
  -- which is actually a CLEANER design than the spec's single-enum
  machine: escalating or pausing a conversation never overwrites (and
  therefore never needs to snapshot-and-restore) the lifecycle status,
  so BR-02's "ESCALATED/PAUSED are reversible" is true by construction
  here, not by bookkeeping a previous_state column.

- BR-03's immutable audit trail is the existing ConversationEvent log
  (already documented as "Immutable event log ... never updated"),
  not a new conversation_state_history table -- same "reuse the
  existing append-only event log" pattern this whole EPIC-04 round has
  used instead of inventing a new table per story (S-002/S-003/S-004/
  S-012/S-017). Every transition_status()/escalate()/pause_for_recruiter()
  call below logs a STATE_TRANSITION-shaped ConversationEvent.

- transition_status() flushes but does NOT commit -- matching this
  file's sibling _log_event()'s convention, since several existing
  call sites (assign_ai_agent, process_candidate_reply) batch a status
  change together with summary/next_action updates under one caller-
  owned commit. Forcing a commit here would split those into partial
  transactions.

- BR-01 (illegal transitions rejected, no silent overwrites) is
  enforced via ALLOWED_STATUS_TRANSITIONS + InvalidStateTransitionError.
  A same-state call (e.g. "closed" -> "closed") is treated as a no-op,
  not an error -- the spec's transition table doesn't address
  idempotent re-calls, and several real call sites re-derive the
  target status from live data on every reply, so rejecting a same-
  state call would turn an idempotent recompute into a hard failure.
"""
import logging
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.core.logging import logger

# Axis 1: conversation lifecycle. "closed" is terminal -- matches BR-02's
# "COMPLETED cannot go back to QUALIFYING" (forward-only, non-reversible).
ALLOWED_STATUS_TRANSITIONS = {
    "open": {"awaiting_candidate", "closed"},
    "awaiting_candidate": {"open", "closed"},
    "closed": set(),
}

logger = logging.getLogger(__name__)

class InvalidStateTransitionError(Exception):
    def __init__(self, from_state: str, to_state: str):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Cannot transition from {from_state!r} to {to_state!r}")

def _get_conversation(db: Session, conversation_id: int, tenant_id: str) -> CandidateConversation:
    conversation = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.id == conversation_id, CandidateConversation.tenant_id == tenant_id)
        .first()
    )
    if not conversation:
        raise ValueError(f"Conversation {conversation_id} not found for tenant {tenant_id}.")
    return conversation

def transition_status(
    db: Session,
    conversation: CandidateConversation,
    new_status: str,
    *,
    reason: str,
    triggered_by: str,
) -> CandidateConversation:
    """
    BR-01: the only sanctioned way to change CandidateConversation.status.
    Raises InvalidStateTransitionError on an illegal transition -- never
    silently overwrites. A same-state call is a no-op (still logged).
    """
    current_status = conversation.status
    if new_status != current_status and new_status not in ALLOWED_STATUS_TRANSITIONS.get(current_status, set()):
        raise InvalidStateTransitionError(current_status, new_status)

    conversation.status = new_status
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)

    event = ConversationEvent(
        conversation_id=conversation.id,
        event_type="STATE_TRANSITION",
        event_data={"from_state": current_status, "to_state": new_status, "reason": reason, "triggered_by": triggered_by},
        triggered_by=triggered_by if triggered_by in ("ai_agent", "candidate", "hr_user", "system") else "system",
    )
    db.add(event)
    db.flush()
    return conversation

def transition_status_by_id(
    db: Session, conversation_id: int, tenant_id: str, new_status: str, *, reason: str, triggered_by: str,
) -> CandidateConversation:
    conversation = _get_conversation(db, conversation_id, tenant_id)
    return transition_status(db, conversation, new_status, reason=reason, triggered_by=triggered_by)

def get_conversation_state(db: Session, conversation_id: int, tenant_id: str) -> Dict:
    conversation = _get_conversation(db, conversation_id, tenant_id)
    return {
        "conversation_id": conversation.id,
        "status": conversation.status,
        "escalation_state": conversation.escalation_state,
        "owner_type": conversation.owner_type,
        "owner_id": conversation.owner_id,
        "entered_at": conversation.updated_at,
    }

# ---------------------------------------------------------------------------
# Axis 2: escalation. Reversible by construction -- see module docstring.
# ---------------------------------------------------------------------------

# S-062/HRMS-0462 BR-01: CRITICAL escalations (legal keywords) sort to
# the very top of the intervention queue regardless of age.
LEGAL_ESCALATION_KEYWORDS = ("legal", "lawyer", "attorney", "lawsuit", "sue", "discriminat")

def escalate(db: Session, conversation: CandidateConversation, *, reason: str, triggered_by: str = "ai_agent") -> CandidateConversation:
    conversation.escalation_state = "escalated"
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="escalation_triggered",
        event_data={"reason": reason, "triggered_by": triggered_by}, triggered_by=triggered_by,
    ))
    db.flush()

    # S-062/HRMS-0462: the one real trigger point every escalation
    # source funnels through -- see that story's own module docstring.
    from app.services.intervention_queue_service import PRIORITY_CRITICAL, PRIORITY_HIGH, add_to_queue
    # S-077/HRMS-0477: real per-tenant escalation_keywords MERGE with
    # (never replace) the built-in legal-keyword list above.
    critical_keywords = LEGAL_ESCALATION_KEYWORDS
    try:
        from app.services.tenant_ai_config_service import get_escalation_keywords
        tenant_keywords = get_escalation_keywords(db, conversation.tenant_id)
        if tenant_keywords:
            critical_keywords = tuple(LEGAL_ESCALATION_KEYWORDS) + tuple(tenant_keywords)
    except Exception:
        pass
    priority = PRIORITY_CRITICAL if any(k.lower() in reason.lower() for k in critical_keywords) else PRIORITY_HIGH
    add_to_queue(db, conversation.candidate_id, conversation.tenant_id, "ESCALATION", f"Escalation: {reason}", priority, commit=False)

    return conversation

def resolve_escalation(db: Session, conversation: CandidateConversation, *, reason: str, triggered_by: str) -> CandidateConversation:
    conversation.escalation_state = "resolved"
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="escalation_resolved",
        event_data={"reason": reason, "triggered_by": triggered_by}, triggered_by=triggered_by,
    ))
    db.flush()

    from app.services.intervention_queue_service import resolve_queue_items
    resolve_queue_items(db, conversation.candidate_id, conversation.tenant_id, ["ESCALATION"], note=f"Escalation resolved: {reason}", commit=False)

    return conversation

# ---------------------------------------------------------------------------
# Axis 3: ownership ("PAUSED" = a human owns it; hand-back = AI owns it
# again). Reversible by construction -- see module docstring.
# ---------------------------------------------------------------------------

def pause_for_recruiter(db: Session, conversation: CandidateConversation, *, recruiter_user_id: str, reason: str) -> CandidateConversation:
    conversation.owner_type = "hr_user"
    conversation.owner_id = recruiter_user_id
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="ownership_changed",
        event_data={"new_owner_type": "hr_user", "new_owner_id": recruiter_user_id, "reason": reason},
        triggered_by="hr_user",
    ))
    db.flush()
    return conversation

def pause_for_recruiter_queue(db: Session, conversation: CandidateConversation, *, reason: str) -> CandidateConversation:
    """S-035/HRMS-0435 escalation hand-off: unlike pause_for_recruiter()
    (a specific HR user explicitly taking over), this clears AI
    ownership to an UNASSIGNED recruiter -- "any recruiter can pick up"
    is explicitly in scope per that story's own "what not to build"
    list (no specific-recruiter routing). owner_id=None until someone
    calls take_over_conversation()."""
    conversation.owner_type = "hr_user"
    conversation.owner_id = None
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="ownership_changed",
        event_data={"new_owner_type": "hr_user", "new_owner_id": None, "reason": reason},
        triggered_by="ai_agent",
    ))
    db.flush()
    return conversation

def resume_to_thunder(db: Session, conversation: CandidateConversation, *, ai_agent_name: str, reason: str) -> CandidateConversation:
    conversation.owner_type = "ai_agent"
    conversation.owner_id = ai_agent_name
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="ownership_changed",
        event_data={"new_owner_type": "ai_agent", "new_owner_id": ai_agent_name, "reason": reason},
        triggered_by="hr_user",
    ))
    db.flush()
    return conversation
