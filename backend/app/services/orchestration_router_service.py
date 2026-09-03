"""
import logging
Phase 3 Part A2 -- HRMS-1101 System Orchestration Router.

Per S-270_HRMS-1101.docx's own "How is Agentic AI Used" section, this
is deliberately NOT an LLM arbitration layer: "an unsupervised
judgment-making layer sitting above every other agent is the single
biggest point of overnight failure in the whole system." It is a
deterministic rule table. The only AI-adjacent behavior is severity
CLASSIFICATION of a brand-new, never-seen conflict pattern -- and even
then it can only ESCALATE_ONLY, never BLOCK or DELAY (BR-1101-03).

Two concrete conflict_rules rows are actually specified in the story
doc's Business Rules section (BR-1101-01 outreach-vs-Core-Pull,
BR-1101-02 Thunder ownership lock) -- `03-THUNDER-AGENTIC-LAYER.md`'s
summary calls this "six seeded conflict rules," but BR-1101-03 through
-06 are platform behaviors (novel patterns escalate-only, HIGH pages
within 5 minutes, Admin-only rule edits, fail-open), not additional
rule rows. Flagged here rather than inventing four more rules to match
a rounded-off phase-doc summary.

HRMS-1102 through HRMS-1108 (the nine agents this router arbitrates
between) do not exist in this codebase yet -- they're Phase 3 Part B,
built after this Part A gate passes. There is also no event bus here
(a pre-existing, already-documented gap elsewhere in this project);
`evaluate_action_intent()` is the direct-call equivalent of subscribing
to `agent.action.intent` -- a future agent calls it synchronously
before acting, exactly the "idempotent function exists, wiring is
follow-up" posture already established for every cron-shaped story in
this codebase.

Concurrency note, documented rather than silently assumed away: two
agents proposing near-simultaneous intents on the same entity_id could
both read the collision window before either has committed its own
OrchestrationEvent row, missing each other. Closing that race needs a
DB-level advisory lock or SELECT ... FOR UPDATE keyed on entity_id,
which needs a decision on which real database this runs against in
production (SQL Server) plus a session-scoped locking strategy --
correctly out of scope for this pass, same as Phase 1's multi-worker
rate-limiter gap. Every call in this module still executes inside a
single DB transaction (caller commits), so the window is narrow, not
absent.
"""
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.models.candidate_ai import CandidateConversation
from app.models.orchestration import RESOLUTION_ACTIONS, SEVERITIES, ConflictRule, OrchestrationEvent
from app.models.user import Users
from app.services.notification_service import send_notification
from app.core.logging import logger

NOVEL_PATTERN_WINDOW_MINUTES = 5   # BR-1101 Step 4
HIGH_SEVERITY_PAGE_SLA_SECONDS = 300  # BR-1101-04

# The two rules the story doc actually specifies in Business Rules --
# see module docstring on why this isn't six.
OUTREACH_VS_COREPULL_RULE_NAME = "outreach_vs_corepull"
THUNDER_OWNERSHIP_LOCK_RULE_NAME = "thunder_ownership_lock"

ANY_SEND_ACTION_TYPE = "any_send"
CANDIDATE_CONVERSATION_ENTITY_TYPE = "candidate_conversation"

logger = logging.getLogger(__name__)

class RuleEditForbidden(Exception):
    """BR-1101-05: only Admin may create, edit, or deactivate a conflict_rules row."""


class InvalidConflictRule(Exception):
    """Rejects a rule definition that can't be evaluated as written."""


class ActionBlocked(Exception):
    """BR-1101-01/02: the caller (a future agent) must not proceed. Carries the
    OrchestrationEvent so the caller can log/inspect why."""

    def __init__(self, event: OrchestrationEvent):
        self.event = event
        super().__init__(
            f"Action blocked by rule '{event.matched_rule_id}' on "
            f"{event.entity_type}:{event.entity_id} (agent {event.agent_id})."
        )


class ActionDelayed(Exception):
    """BR: the DELAY resolution -- caller must hold the action for
    delay_minutes and re-evaluate, not proceed now and not abandon it."""

    def __init__(self, event: OrchestrationEvent, delay_minutes: int):
        self.event = event
        self.delay_minutes = delay_minutes
        super().__init__(
            f"Action delayed {delay_minutes} min by rule '{event.matched_rule_id}' on "
            f"{event.entity_type}:{event.entity_id} (agent {event.agent_id})."
        )


# ---------------------------------------------------------------------------
# Rule management -- BR-1101-05
# ---------------------------------------------------------------------------

def create_conflict_rule(
    db: Session,
    *,
    actor_role: str,
    rule_name: str,
    entity_type_a: str,
    action_type_a: str,
    entity_type_b: str,
    action_type_b: str,
    collision_window_minutes: int,
    resolution_action: str,
    delay_minutes: Optional[int] = None,
    tenant_id: Optional[int] = None,
) -> ConflictRule:
    """BR-1101-05: write access gated by role=Admin, full stop -- there is
    no "trusted service account" bypass, matching this codebase's
    Development & Review Standard posture on role checks living
    server-side, never assumed from the caller's good intentions."""
    if actor_role != "Admin":
        raise RuleEditForbidden(f"conflict_rules may only be written by Admin, got role '{actor_role}'.")
    if resolution_action not in RESOLUTION_ACTIONS:
        raise InvalidConflictRule(f"resolution_action must be one of {RESOLUTION_ACTIONS}, got '{resolution_action}'.")
    if not (1 <= collision_window_minutes <= 1440):
        raise InvalidConflictRule("collision_window_minutes must be between 1 and 1440 (UI field spec).")
    if resolution_action == "DELAY" and not delay_minutes:
        raise InvalidConflictRule("delay_minutes is required when resolution_action='DELAY'.")

    rule = ConflictRule(
        tenant_id=tenant_id, rule_name=rule_name,
        entity_type_a=entity_type_a, action_type_a=action_type_a,
        entity_type_b=entity_type_b, action_type_b=action_type_b,
        collision_window_minutes=collision_window_minutes,
        resolution_action=resolution_action, delay_minutes=delay_minutes,
    )
    db.add(rule)
    db.flush()
    return rule


def deactivate_conflict_rule(db: Session, rule: ConflictRule, *, actor_role: str) -> ConflictRule:
    """"Deactivate a rule without deleting audit history" (UI field spec) --
    is_active=False, the row and every OrchestrationEvent that ever
    snapshotted its resolution_action stay exactly as they were."""
    if actor_role != "Admin":
        raise RuleEditForbidden(f"conflict_rules may only be written by Admin, got role '{actor_role}'.")
    rule.is_active = False
    db.add(rule)
    return rule


def seed_default_conflict_rules(db: Session, *, tenant_id: Optional[int] = None) -> list:
    """Idempotent -- seeds the two rules the story doc's Business Rules
    section actually specifies. Safe to call more than once (skips a
    rule_name that already exists)."""
    existing_names = {
        name for (name,) in db.query(ConflictRule.rule_name)
        .filter(ConflictRule.rule_name.in_([OUTREACH_VS_COREPULL_RULE_NAME, THUNDER_OWNERSHIP_LOCK_RULE_NAME]))
        .all()
    }
    created = []

    if OUTREACH_VS_COREPULL_RULE_NAME not in existing_names:
        # BR-1101-01: HRMS-1105 Core-pull flag within 60 min of HRMS-1104
        # outreach on the same entity_id -> outreach BLOCKED.
        created.append(create_conflict_rule(
            db, actor_role="Admin", rule_name=OUTREACH_VS_COREPULL_RULE_NAME,
            entity_type_a="candidate", action_type_a="core_pull_flag",
            entity_type_b="candidate", action_type_b="outreach_send",
            collision_window_minutes=60, resolution_action="BLOCK",
            tenant_id=tenant_id,
        ))

    if THUNDER_OWNERSHIP_LOCK_RULE_NAME not in existing_names:
        # BR-1101-02: R-08 ownership lock, checked here as a SECOND gate --
        # send_thunder_message() already enforces this independently
        # (app.services.whatsapp_routing_service.is_ai_owner). This rule
        # exists so any future agent that calls the Router directly (not
        # through send_thunder_message) is still caught.
        created.append(create_conflict_rule(
            db, actor_role="Admin", rule_name=THUNDER_OWNERSHIP_LOCK_RULE_NAME,
            entity_type_a=CANDIDATE_CONVERSATION_ENTITY_TYPE, action_type_a=ANY_SEND_ACTION_TYPE,
            entity_type_b=CANDIDATE_CONVERSATION_ENTITY_TYPE, action_type_b=ANY_SEND_ACTION_TYPE,
            collision_window_minutes=1, resolution_action="BLOCK",
            tenant_id=tenant_id,
        ))

    return created


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _rule_side_and_counterpart(rule: ConflictRule, entity_type: str, action_type: str):
    """Returns (matched, counterpart_entity_type, counterpart_action_type)
    for whichever side of the two-sided rule this intent matches, or
    (False, None, None) if it matches neither side."""
    if rule.entity_type_a == entity_type and rule.action_type_a == action_type:
        return True, rule.entity_type_b, rule.action_type_b
    if rule.entity_type_b == entity_type and rule.action_type_b == action_type:
        return True, rule.entity_type_a, rule.action_type_a
    return False, None, None


def _active_rules_for(db: Session, entity_type: str, action_type: str, tenant_id: Optional[int]):
    query = db.query(ConflictRule).filter(ConflictRule.is_active.is_(True))
    if tenant_id is not None:
        query = query.filter(ConflictRule.tenant_id == tenant_id)
    return [
        rule for rule in query.all()
        if _rule_side_and_counterpart(rule, entity_type, action_type)[0]
    ]


def _find_counterpart_event(
    db: Session, *, entity_id: str, counterpart_entity_type: str, counterpart_action_type: str,
    agent_id: str, proposed_at: datetime, window_minutes: int,
) -> Optional[OrchestrationEvent]:
    """BR-1101-01-style match: a prior intent on the SAME entity_id, from
    a DIFFERENT agent, on the rule's counterpart (entity_type, action_type),
    within window_minutes of this proposal -- either direction, since
    "within 60 minutes of" doesn't specify which side happened first."""
    window_start = proposed_at - timedelta(minutes=window_minutes)
    window_end = proposed_at + timedelta(minutes=window_minutes)
    return (
        db.query(OrchestrationEvent)
        .filter(
            OrchestrationEvent.entity_id == entity_id,
            OrchestrationEvent.entity_type == counterpart_entity_type,
            OrchestrationEvent.action_type == counterpart_action_type,
            OrchestrationEvent.agent_id != agent_id,
            OrchestrationEvent.proposed_at >= window_start,
            OrchestrationEvent.proposed_at <= window_end,
        )
        .order_by(OrchestrationEvent.proposed_at.desc())
        .first()
    )


def _find_novel_collision(
    db: Session, *, entity_id: str, agent_id: str, proposed_at: datetime,
) -> Optional[OrchestrationEvent]:
    """Step 4: "two events share entity_id within 5 minutes from different
    agent_id values" with no rule match on either side."""
    window_start = proposed_at - timedelta(minutes=NOVEL_PATTERN_WINDOW_MINUTES)
    window_end = proposed_at + timedelta(minutes=NOVEL_PATTERN_WINDOW_MINUTES)
    return (
        db.query(OrchestrationEvent)
        .filter(
            OrchestrationEvent.entity_id == entity_id,
            OrchestrationEvent.agent_id != agent_id,
            OrchestrationEvent.proposed_at >= window_start,
            OrchestrationEvent.proposed_at <= window_end,
        )
        .order_by(OrchestrationEvent.proposed_at.desc())
        .first()
    )


def _conversation_is_owned_by_human(db: Session, conversation_id: str) -> bool:
    """BR-1101-02's direct check -- this rule doesn't need a counterpart
    agent event, current ownership state IS the signal."""
    conversation = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.id == int(conversation_id))
        .first()
    )
    return bool(conversation and conversation.owner_type == "hr_user")


# ---------------------------------------------------------------------------
# Escalation -- BR-1101-04
# ---------------------------------------------------------------------------

def _escalate(
    db: Session, event: OrchestrationEvent, *, director: Optional[Users], tenant_id: Optional[int],
) -> None:
    """HIGH -> HRMS-0113 P0 channel, immediate (measured against
    detected_at for the 5-minute SLA). MEDIUM/LOW -> logged only here;
    HRMS-1110's Daily System Activity Report reads orchestration_events
    directly for the next-morning digest, this function does not also
    duplicate that read path.

    On-call Director roster resolution is not built in this codebase --
    `director` is caller-supplied. Escalation is real and tested when a
    recipient is supplied; roster lookup is the follow-up piece, same
    "notification path is real, resolving WHO gets it is deferred"
    posture as HRMS-0113 itself before this session wired real call sites."""
    if event.severity != "HIGH" or director is None:
        return
    try:
        send_notification(
            db, calling_context_tenant_id=tenant_id, recipient=director,
            priority_tier="P0", channel_preference="WHATSAPP",
            message=(
                f"[Orchestration Router] HIGH severity conflict on "
                f"{event.entity_type}:{event.entity_id} -- agent {event.agent_id}, "
                f"action {event.action_type}. Review required immediately."
            ),
        )
        event.escalated_at = datetime.utcnow()
        db.add(event)
    except Exception:
        pass  # best-effort -- never blocks the underlying agent action


# ---------------------------------------------------------------------------
# The one entry point every future agent must call before acting
# ---------------------------------------------------------------------------

def evaluate_action_intent(
    db: Session,
    *,
    agent_id: str,
    entity_type: str,
    entity_id: str,
    action_type: str,
    risk_tier: str = "MEDIUM",
    tenant_id: Optional[int] = None,
    proposed_at: Optional[datetime] = None,
    llm_classifier: Optional[Callable[[OrchestrationEvent, OrchestrationEvent], str]] = None,
    director: Optional[Users] = None,
) -> OrchestrationEvent:
    """
    HRMS-1101's evaluate step -- the direct-call equivalent of publishing
    to `agent.action.intent` and waiting for a response, since this
    codebase has no event bus. Raises ActionBlocked / ActionDelayed when
    the caller must not proceed; otherwise returns the logged
    OrchestrationEvent and the caller may proceed (this covers
    ESCALATE_ONLY and no-match alike -- both mean "go").

    BR-1101-06 fail-open: only the DETECTION logic below is guarded.
    create_conflict_rule()/deactivate_conflict_rule() are not -- a bad
    Admin action should fail loudly, not open. A detection-path failure
    here fails open (logs a best-effort CRITICAL page if `director` is
    given, then behaves as if nothing matched) because an agent
    incorrectly blocked by a router bug is exactly the silent-failure
    mode BR-1101-06 calls out as worse than an occasional missed check.
    """
    proposed_at = proposed_at or datetime.utcnow()

    try:
        blocked_event = _evaluate_ownership_lock(
            db, agent_id=agent_id, entity_type=entity_type, entity_id=entity_id,
            action_type=action_type, risk_tier=risk_tier, tenant_id=tenant_id, proposed_at=proposed_at,
        )
        if blocked_event is not None:
            raise ActionBlocked(blocked_event)

        rule_event = _evaluate_rule_matches(
            db, agent_id=agent_id, entity_type=entity_type, entity_id=entity_id,
            action_type=action_type, risk_tier=risk_tier, tenant_id=tenant_id, proposed_at=proposed_at,
        )
        if rule_event is not None:
            if rule_event.resolution_action == "BLOCK":
                raise ActionBlocked(rule_event)
            if rule_event.resolution_action == "DELAY":
                matched_rule = db.query(ConflictRule).filter(ConflictRule.id == rule_event.matched_rule_id).first()
                raise ActionDelayed(rule_event, matched_rule.delay_minutes if matched_rule else 0)
            # ESCALATE_ONLY
            _escalate(db, rule_event, director=director, tenant_id=tenant_id)
            return rule_event

    except (ActionBlocked, ActionDelayed):
        raise
    except Exception:
        # BR-1101-06: fail open, alert, never fail closed silently.
        failure_event = OrchestrationEvent(
            tenant_id=tenant_id, agent_id=agent_id, entity_type=entity_type,
            entity_id=entity_id, action_type=action_type, risk_tier=risk_tier,
            proposed_at=proposed_at, resolution_action=None, severity="HIGH",
            llm_classified=False,
        )
        db.add(failure_event)
        _escalate(db, failure_event, director=director, tenant_id=tenant_id)
        return failure_event

    # No rule matched either side -- check the novel-pattern fallback.
    novel_event = _evaluate_novel_pattern(
        db, agent_id=agent_id, entity_type=entity_type, entity_id=entity_id,
        action_type=action_type, risk_tier=risk_tier, tenant_id=tenant_id,
        proposed_at=proposed_at, llm_classifier=llm_classifier,
    )
    if novel_event is not None:
        _escalate(db, novel_event, director=director, tenant_id=tenant_id)
        return novel_event

    # Nothing matched at all -- still logged (audit view requirement).
    plain_event = OrchestrationEvent(
        tenant_id=tenant_id, agent_id=agent_id, entity_type=entity_type,
        entity_id=entity_id, action_type=action_type, risk_tier=risk_tier,
        proposed_at=proposed_at, resolution_action=None, llm_classified=False,
    )
    db.add(plain_event)
    return plain_event


def _evaluate_ownership_lock(
    db, *, agent_id, entity_type, entity_id, action_type, risk_tier, tenant_id, proposed_at,
) -> Optional[OrchestrationEvent]:
    if not (entity_type == CANDIDATE_CONVERSATION_ENTITY_TYPE and action_type == ANY_SEND_ACTION_TYPE):
        return None
    if not _conversation_is_owned_by_human(db, entity_id):
        return None

    rule = db.query(ConflictRule).filter(ConflictRule.rule_name == THUNDER_OWNERSHIP_LOCK_RULE_NAME).first()
    event = OrchestrationEvent(
        tenant_id=tenant_id, agent_id=agent_id, entity_type=entity_type, entity_id=entity_id,
        action_type=action_type, risk_tier=risk_tier, proposed_at=proposed_at,
        matched_rule_id=rule.id if rule else None, resolution_action="BLOCK",
        llm_classified=False,
    )
    db.add(event)
    return event


def _evaluate_rule_matches(
    db, *, agent_id, entity_type, entity_id, action_type, risk_tier, tenant_id, proposed_at,
) -> Optional[OrchestrationEvent]:
    for rule in _active_rules_for(db, entity_type, action_type, tenant_id):
        _, counterpart_entity_type, counterpart_action_type = _rule_side_and_counterpart(rule, entity_type, action_type)
        prior = _find_counterpart_event(
            db, entity_id=entity_id, counterpart_entity_type=counterpart_entity_type,
            counterpart_action_type=counterpart_action_type, agent_id=agent_id,
            proposed_at=proposed_at, window_minutes=rule.collision_window_minutes,
        )
        if prior is None:
            continue
        event = OrchestrationEvent(
            tenant_id=tenant_id, agent_id=agent_id, entity_type=entity_type, entity_id=entity_id,
            action_type=action_type, risk_tier=risk_tier, proposed_at=proposed_at,
            matched_rule_id=rule.id, resolution_action=rule.resolution_action,
            llm_classified=False,
        )
        db.add(event)
        return event
    return None


def _evaluate_novel_pattern(
    db, *, agent_id, entity_type, entity_id, action_type, risk_tier, tenant_id, proposed_at, llm_classifier,
) -> Optional[OrchestrationEvent]:
    counterpart = _find_novel_collision(db, entity_id=entity_id, agent_id=agent_id, proposed_at=proposed_at)
    if counterpart is None:
        return None

    this_event = OrchestrationEvent(
        tenant_id=tenant_id, agent_id=agent_id, entity_type=entity_type, entity_id=entity_id,
        action_type=action_type, risk_tier=risk_tier, proposed_at=proposed_at,
        resolution_action="ESCALATE_ONLY",  # BR-1101-03 -- hard-coded, never invented
        llm_classified=True,
    )

    severity = "MEDIUM"  # AC: "On Failure: default to MEDIUM severity"
    llm_call_failed = False
    if llm_classifier is not None:
        try:
            severity = llm_classifier(this_event, counterpart)
            if severity not in SEVERITIES:
                severity, llm_call_failed = "MEDIUM", True
        except Exception:
            severity, llm_call_failed = "MEDIUM", True
    else:
        llm_call_failed = True  # no classifier wired -- same as a failed call, per the AC's own fallback

    this_event.severity = severity
    this_event.llm_call_failed = llm_call_failed
    db.add(this_event)
    return this_event
