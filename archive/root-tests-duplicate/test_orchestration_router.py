"""
Phase 3 Part A2 -- HRMS-1101 System Orchestration Router
(app.services.orchestration_router_service).

Covers every acceptance criterion in S-270_HRMS-1101.docx that this
codebase can actually exercise without a live event bus or the nine
not-yet-built agents:

  AC-1 BLOCK prevents the action (raises ActionBlocked)
  AC-2 DELAY holds for exactly delay_minutes (raises ActionDelayed)
  AC-3 ESCALATE_ONLY proceeds AND escalates
  AC-4 HIGH severity escalates within the SLA window (tested via the
       escalated_at timestamp being set, not real wall-clock elapsed
       time -- there is no scheduler here to actually delay delivery)
  AC-5 a novel pattern never auto-blocks -- only ESCALATE_ONLY
  AC-6 router failure fails OPEN (never silently blocks) and pages CRITICAL
  AC-7 only Admin may write conflict_rules

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.notification import Notification
from app.models.orchestration import ConflictRule, OrchestrationEvent
from app.models.tenant import Tenant
from app.models.user import Users

from app.services.ai_conversation_service import AI_AGENT_NAME
from app.services.orchestration_router_service import (
    ActionBlocked,
    ActionDelayed,
    InvalidConflictRule,
    RuleEditForbidden,
    THUNDER_OWNERSHIP_LOCK_RULE_NAME,
    ANY_SEND_ACTION_TYPE,
    CANDIDATE_CONVERSATION_ENTITY_TYPE,
    OUTREACH_VS_COREPULL_RULE_NAME,
    create_conflict_rule,
    deactivate_conflict_rule,
    evaluate_action_intent,
    seed_default_conflict_rules,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, Candidate.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, CandidateAIAssignment.__table__,
        Notification.__table__, ConflictRule.__table__, OrchestrationEvent.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def director(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    d = Users(
        UserID="U-DIRECTOR", UserRole="Director", UserEmail="director@blitzenx.com",
        UserPassword="h", tenant_id=tenant.id,
    )
    db_session.add(d)
    db_session.commit()
    return d, tenant


# ---------------------------------------------------------------------------
# AC-7 -- Admin-only rule writes
# ---------------------------------------------------------------------------

def test_create_rule_rejected_for_non_admin(db_session):
    with pytest.raises(RuleEditForbidden):
        create_conflict_rule(
            db_session, actor_role="Recruiter", rule_name="x",
            entity_type_a="candidate", action_type_a="a",
            entity_type_b="candidate", action_type_b="b",
            collision_window_minutes=10, resolution_action="BLOCK",
        )


def test_create_rule_succeeds_for_admin(db_session):
    rule = create_conflict_rule(
        db_session, actor_role="Admin", rule_name="x",
        entity_type_a="candidate", action_type_a="a",
        entity_type_b="candidate", action_type_b="b",
        collision_window_minutes=10, resolution_action="BLOCK",
    )
    assert rule.id is not None
    assert rule.is_active is True


def test_create_rule_rejects_invalid_resolution_action(db_session):
    with pytest.raises(InvalidConflictRule):
        create_conflict_rule(
            db_session, actor_role="Admin", rule_name="x",
            entity_type_a="candidate", action_type_a="a",
            entity_type_b="candidate", action_type_b="b",
            collision_window_minutes=10, resolution_action="MAYBE",
        )


def test_create_rule_rejects_delay_without_delay_minutes(db_session):
    with pytest.raises(InvalidConflictRule):
        create_conflict_rule(
            db_session, actor_role="Admin", rule_name="x",
            entity_type_a="candidate", action_type_a="a",
            entity_type_b="candidate", action_type_b="b",
            collision_window_minutes=10, resolution_action="DELAY",
        )


def test_create_rule_rejects_out_of_range_window(db_session):
    with pytest.raises(InvalidConflictRule):
        create_conflict_rule(
            db_session, actor_role="Admin", rule_name="x",
            entity_type_a="candidate", action_type_a="a",
            entity_type_b="candidate", action_type_b="b",
            collision_window_minutes=0, resolution_action="BLOCK",
        )


def test_deactivate_rule_rejected_for_non_admin(db_session):
    rule = create_conflict_rule(
        db_session, actor_role="Admin", rule_name="x",
        entity_type_a="candidate", action_type_a="a",
        entity_type_b="candidate", action_type_b="b",
        collision_window_minutes=10, resolution_action="BLOCK",
    )
    with pytest.raises(RuleEditForbidden):
        deactivate_conflict_rule(db_session, rule, actor_role="Recruiter")


def test_deactivate_rule_preserves_row_for_audit_history(db_session):
    rule = create_conflict_rule(
        db_session, actor_role="Admin", rule_name="x",
        entity_type_a="candidate", action_type_a="a",
        entity_type_b="candidate", action_type_b="b",
        collision_window_minutes=10, resolution_action="BLOCK",
    )
    deactivate_conflict_rule(db_session, rule, actor_role="Admin")
    db_session.commit()
    still_there = db_session.query(ConflictRule).filter(ConflictRule.id == rule.id).first()
    assert still_there is not None
    assert still_there.is_active is False


def test_seed_default_rules_is_idempotent(db_session):
    first = seed_default_conflict_rules(db_session)
    db_session.commit()
    assert len(first) == 2
    second = seed_default_conflict_rules(db_session)
    db_session.commit()
    assert len(second) == 0
    assert db_session.query(ConflictRule).count() == 2


# ---------------------------------------------------------------------------
# AC-1 -- BR-1101-01 Outreach vs Core-Pull collision
# ---------------------------------------------------------------------------

def test_outreach_blocked_by_prior_corepull_flag_same_entity(db_session):
    seed_default_conflict_rules(db_session)
    db_session.commit()
    t0 = datetime(2026, 4, 1, 9, 0, 0)

    # HRMS-1105 flags Core-pull for candidate C-1.
    evaluate_action_intent(
        db_session, agent_id="HRMS-1105", entity_type="candidate", entity_id="C-1",
        action_type="core_pull_flag", proposed_at=t0,
    )
    db_session.commit()

    # HRMS-1104 tries to start outreach on the SAME candidate 30 min later.
    with pytest.raises(ActionBlocked):
        evaluate_action_intent(
            db_session, agent_id="HRMS-1104", entity_type="candidate", entity_id="C-1",
            action_type="outreach_send", proposed_at=t0 + timedelta(minutes=30),
        )


def test_outreach_allowed_when_corepull_flag_is_for_a_different_candidate(db_session):
    seed_default_conflict_rules(db_session)
    db_session.commit()
    t0 = datetime(2026, 4, 1, 9, 0, 0)

    evaluate_action_intent(
        db_session, agent_id="HRMS-1105", entity_type="candidate", entity_id="C-OTHER",
        action_type="core_pull_flag", proposed_at=t0,
    )
    db_session.commit()

    event = evaluate_action_intent(
        db_session, agent_id="HRMS-1104", entity_type="candidate", entity_id="C-1",
        action_type="outreach_send", proposed_at=t0 + timedelta(minutes=30),
    )
    assert event.resolution_action is None


def test_outreach_allowed_when_corepull_flag_is_outside_collision_window(db_session):
    seed_default_conflict_rules(db_session)
    db_session.commit()
    t0 = datetime(2026, 4, 1, 9, 0, 0)

    evaluate_action_intent(
        db_session, agent_id="HRMS-1105", entity_type="candidate", entity_id="C-1",
        action_type="core_pull_flag", proposed_at=t0,
    )
    db_session.commit()

    event = evaluate_action_intent(
        db_session, agent_id="HRMS-1104", entity_type="candidate", entity_id="C-1",
        action_type="outreach_send", proposed_at=t0 + timedelta(minutes=90),
    )
    assert event.resolution_action is None


def test_outreach_then_corepull_flag_also_blocks_the_later_action(db_session):
    """The doc doesn't specify which side must happen first -- proves the
    match is symmetric, not order-dependent."""
    seed_default_conflict_rules(db_session)
    db_session.commit()
    t0 = datetime(2026, 4, 1, 9, 0, 0)

    evaluate_action_intent(
        db_session, agent_id="HRMS-1104", entity_type="candidate", entity_id="C-1",
        action_type="outreach_send", proposed_at=t0,
    )
    db_session.commit()

    with pytest.raises(ActionBlocked):
        evaluate_action_intent(
            db_session, agent_id="HRMS-1105", entity_type="candidate", entity_id="C-1",
            action_type="core_pull_flag", proposed_at=t0 + timedelta(minutes=10),
        )


def test_matched_rule_id_is_snapshotted_on_the_blocked_event(db_session):
    seed_default_conflict_rules(db_session)
    db_session.commit()
    rule = db_session.query(ConflictRule).filter(ConflictRule.rule_name == OUTREACH_VS_COREPULL_RULE_NAME).first()
    t0 = datetime(2026, 4, 1, 9, 0, 0)

    evaluate_action_intent(
        db_session, agent_id="HRMS-1105", entity_type="candidate", entity_id="C-1",
        action_type="core_pull_flag", proposed_at=t0,
    )
    db_session.commit()

    try:
        evaluate_action_intent(
            db_session, agent_id="HRMS-1104", entity_type="candidate", entity_id="C-1",
            action_type="outreach_send", proposed_at=t0 + timedelta(minutes=5),
        )
    except ActionBlocked as exc:
        assert exc.event.matched_rule_id == rule.id
    else:
        pytest.fail("expected ActionBlocked")


# ---------------------------------------------------------------------------
# BR-1101-02 -- Thunder ownership lock, as a second gate
# ---------------------------------------------------------------------------

def _make_conversation(db, *, owner_type):
    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()
    org_owner = Users(UserID="U-ORG", UserRole="Admin", UserEmail="admin@blitzenx.com", UserPassword="h")
    recruiter = Users(UserID="U-REC", UserRole="Recruiter", UserEmail="rec@blitzenx.com", UserPassword="h")
    db.add_all([org_owner, recruiter])
    db.commit()
    candidate = Candidate(candidateID="C-CONV", candidateEmail="conv@example.com", candidatePassword="h")
    db.add(candidate)
    db.commit()
    conversation = CandidateConversation(
        tenant_id=org_owner.UserID, candidate_id=candidate.candidateID,
        status="open", ai_agent_name=AI_AGENT_NAME,
        owner_type=owner_type, owner_id=recruiter.UserID if owner_type == "hr_user" else AI_AGENT_NAME,
    )
    db.add(conversation)
    db.commit()
    return conversation


def test_send_blocked_when_conversation_owned_by_human(db_session):
    seed_default_conflict_rules(db_session)
    db_session.commit()
    conversation = _make_conversation(db_session, owner_type="hr_user")

    with pytest.raises(ActionBlocked):
        evaluate_action_intent(
            db_session, agent_id="HRMS-1104", entity_type=CANDIDATE_CONVERSATION_ENTITY_TYPE,
            entity_id=str(conversation.id), action_type=ANY_SEND_ACTION_TYPE,
        )


def test_send_allowed_when_conversation_owned_by_ai(db_session):
    seed_default_conflict_rules(db_session)
    db_session.commit()
    conversation = _make_conversation(db_session, owner_type="ai_agent")

    event = evaluate_action_intent(
        db_session, agent_id="HRMS-1104", entity_type=CANDIDATE_CONVERSATION_ENTITY_TYPE,
        entity_id=str(conversation.id), action_type=ANY_SEND_ACTION_TYPE,
    )
    assert event.resolution_action is None


def test_ownership_lock_matched_rule_id_snapshotted(db_session):
    seed_default_conflict_rules(db_session)
    db_session.commit()
    rule = db_session.query(ConflictRule).filter(ConflictRule.rule_name == THUNDER_OWNERSHIP_LOCK_RULE_NAME).first()
    conversation = _make_conversation(db_session, owner_type="hr_user")

    try:
        evaluate_action_intent(
            db_session, agent_id="HRMS-1103", entity_type=CANDIDATE_CONVERSATION_ENTITY_TYPE,
            entity_id=str(conversation.id), action_type=ANY_SEND_ACTION_TYPE,
        )
    except ActionBlocked as exc:
        assert exc.event.matched_rule_id == rule.id
    else:
        pytest.fail("expected ActionBlocked")


# ---------------------------------------------------------------------------
# AC-2 -- DELAY resolution
# ---------------------------------------------------------------------------

def test_delay_resolution_raises_action_delayed_with_correct_minutes(db_session):
    create_conflict_rule(
        db_session, actor_role="Admin", rule_name="delay_test",
        entity_type_a="candidate", action_type_a="a",
        entity_type_b="candidate", action_type_b="b",
        collision_window_minutes=30, resolution_action="DELAY", delay_minutes=15,
    )
    db_session.commit()
    t0 = datetime(2026, 4, 1, 9, 0, 0)

    evaluate_action_intent(
        db_session, agent_id="AGENT-A", entity_type="candidate", entity_id="C-9",
        action_type="a", proposed_at=t0,
    )
    db_session.commit()

    with pytest.raises(ActionDelayed) as exc_info:
        evaluate_action_intent(
            db_session, agent_id="AGENT-B", entity_type="candidate", entity_id="C-9",
            action_type="b", proposed_at=t0 + timedelta(minutes=5),
        )
    assert exc_info.value.delay_minutes == 15


# ---------------------------------------------------------------------------
# AC-3 / AC-5 -- novel-pattern classification, ESCALATE_ONLY only
# ---------------------------------------------------------------------------

def test_novel_pattern_never_blocks_only_escalates(db_session):
    t0 = datetime(2026, 4, 1, 9, 0, 0)
    evaluate_action_intent(
        db_session, agent_id="HRMS-1106", entity_type="employee", entity_id="E-1",
        action_type="something_new", proposed_at=t0,
    )
    db_session.commit()

    event = evaluate_action_intent(
        db_session, agent_id="HRMS-1107", entity_type="employee", entity_id="E-1",
        action_type="something_else_new", proposed_at=t0 + timedelta(minutes=2),
    )
    assert event.resolution_action == "ESCALATE_ONLY"
    assert event.llm_classified is True


def test_novel_pattern_uses_llm_classifier_result(db_session):
    t0 = datetime(2026, 4, 1, 9, 0, 0)
    evaluate_action_intent(
        db_session, agent_id="HRMS-1106", entity_type="employee", entity_id="E-2",
        action_type="a", proposed_at=t0,
    )
    db_session.commit()

    event = evaluate_action_intent(
        db_session, agent_id="HRMS-1107", entity_type="employee", entity_id="E-2",
        action_type="b", proposed_at=t0 + timedelta(minutes=1),
        llm_classifier=lambda a, b: "HIGH",
    )
    assert event.severity == "HIGH"
    assert event.llm_call_failed is False


def test_novel_pattern_defaults_to_medium_when_classifier_raises(db_session):
    t0 = datetime(2026, 4, 1, 9, 0, 0)
    evaluate_action_intent(
        db_session, agent_id="HRMS-1106", entity_type="employee", entity_id="E-3",
        action_type="a", proposed_at=t0,
    )
    db_session.commit()

    def broken_classifier(a, b):
        raise RuntimeError("Anthropic API unavailable")

    event = evaluate_action_intent(
        db_session, agent_id="HRMS-1107", entity_type="employee", entity_id="E-3",
        action_type="b", proposed_at=t0 + timedelta(minutes=1),
        llm_classifier=broken_classifier,
    )
    assert event.severity == "MEDIUM"
    assert event.llm_call_failed is True


def test_novel_pattern_defaults_to_medium_when_no_classifier_wired(db_session):
    t0 = datetime(2026, 4, 1, 9, 0, 0)
    evaluate_action_intent(
        db_session, agent_id="HRMS-1106", entity_type="employee", entity_id="E-4",
        action_type="a", proposed_at=t0,
    )
    db_session.commit()

    event = evaluate_action_intent(
        db_session, agent_id="HRMS-1107", entity_type="employee", entity_id="E-4",
        action_type="b", proposed_at=t0 + timedelta(minutes=1),
    )
    assert event.severity == "MEDIUM"
    assert event.llm_call_failed is True


def test_two_actions_from_the_same_agent_are_not_a_conflict(db_session):
    """Only DIFFERENT agent_id values count as a collision -- one agent
    acting twice on its own entity is normal operation, not a conflict."""
    t0 = datetime(2026, 4, 1, 9, 0, 0)
    evaluate_action_intent(
        db_session, agent_id="HRMS-1106", entity_type="employee", entity_id="E-5",
        action_type="a", proposed_at=t0,
    )
    db_session.commit()

    event = evaluate_action_intent(
        db_session, agent_id="HRMS-1106", entity_type="employee", entity_id="E-5",
        action_type="b", proposed_at=t0 + timedelta(minutes=1),
    )
    assert event.resolution_action is None
    assert event.llm_classified is False


# ---------------------------------------------------------------------------
# AC-4 -- HIGH severity escalation delivery
# ---------------------------------------------------------------------------

def test_high_severity_novel_pattern_escalates_to_director(db_session, director):
    director_user, tenant = director
    t0 = datetime(2026, 4, 1, 9, 0, 0)
    evaluate_action_intent(
        db_session, agent_id="HRMS-1106", entity_type="employee", entity_id="E-6",
        action_type="a", tenant_id=tenant.id, proposed_at=t0,
    )
    db_session.commit()

    event = evaluate_action_intent(
        db_session, agent_id="HRMS-1107", entity_type="employee", entity_id="E-6",
        action_type="b", tenant_id=tenant.id, proposed_at=t0 + timedelta(minutes=1),
        llm_classifier=lambda a, b: "HIGH", director=director_user,
    )
    assert event.escalated_at is not None
    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].priority_tier == "P0"


def test_medium_severity_does_not_page_the_director(db_session, director):
    director_user, tenant = director
    t0 = datetime(2026, 4, 1, 9, 0, 0)
    evaluate_action_intent(
        db_session, agent_id="HRMS-1106", entity_type="employee", entity_id="E-7",
        action_type="a", tenant_id=tenant.id, proposed_at=t0,
    )
    db_session.commit()

    event = evaluate_action_intent(
        db_session, agent_id="HRMS-1107", entity_type="employee", entity_id="E-7",
        action_type="b", tenant_id=tenant.id, proposed_at=t0 + timedelta(minutes=1),
        llm_classifier=lambda a, b: "MEDIUM", director=director_user,
    )
    assert event.escalated_at is None
    assert db_session.query(Notification).count() == 0


def test_escalation_without_a_director_does_not_raise(db_session):
    t0 = datetime(2026, 4, 1, 9, 0, 0)
    evaluate_action_intent(
        db_session, agent_id="HRMS-1106", entity_type="employee", entity_id="E-8",
        action_type="a", proposed_at=t0,
    )
    db_session.commit()

    event = evaluate_action_intent(
        db_session, agent_id="HRMS-1107", entity_type="employee", entity_id="E-8",
        action_type="b", proposed_at=t0 + timedelta(minutes=1),
        llm_classifier=lambda a, b: "HIGH",
    )
    assert event.escalated_at is None  # no director supplied -- logged, not paged


# ---------------------------------------------------------------------------
# AC-6 -- fail-open
# ---------------------------------------------------------------------------

def test_router_internal_failure_fails_open_not_closed(db_session, monkeypatch, director):
    director_user, tenant = director
    import app.services.orchestration_router_service as router

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated router outage")

    monkeypatch.setattr(router, "_active_rules_for", _boom)

    # Must NOT raise ActionBlocked/ActionDelayed -- the agent proceeds.
    event = evaluate_action_intent(
        db_session, agent_id="HRMS-1104", entity_type="candidate", entity_id="C-FAIL",
        action_type="outreach_send", tenant_id=tenant.id, director=director_user,
    )
    assert event.resolution_action is None
    assert event.severity == "HIGH"
    # CRITICAL alert fired.
    assert db_session.query(Notification).count() == 1


# ---------------------------------------------------------------------------
# No match at all -- still logged (audit view)
# ---------------------------------------------------------------------------

def test_no_match_at_all_is_still_logged(db_session):
    event = evaluate_action_intent(
        db_session, agent_id="HRMS-1102", entity_type="candidate", entity_id="C-LONE",
        action_type="scan_only",
    )
    db_session.commit()
    assert event.resolution_action is None
    assert db_session.query(OrchestrationEvent).filter(OrchestrationEvent.entity_id == "C-LONE").count() == 1
