"""
import logging
S-018/HRMS-0418 -- Conversation State Manager.

Real state model under test (see conversation_state_service module
docstring for why this is 3 orthogonal axes, not the spec's fictional
single 10-value enum): status (open/awaiting_candidate/closed),
escalation_state, owner_type/owner_id. BR-03's audit trail is the
existing ConversationEvent log (STATE_TRANSITION-typed rows), not a
new conversation_state_history table.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.recruiter_intervention_queue import RecruiterInterventionQueue
from app.models.user import Users

import app.services.conversation_state_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        RecruiterInterventionQueue.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def seeded(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h")
    db_session.add_all([owner, candidate])
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="thunder", escalation_state="none")
    db_session.add(conv)
    db_session.commit()
    return conv


def test_valid_transition_updates_status_and_logs_event(db_session, seeded):
    conv = seeded
    svc.transition_status(db_session, conv, "awaiting_candidate", reason="First outreach sent", triggered_by="system")
    db_session.commit()

    db_session.refresh(conv)
    assert conv.status == "awaiting_candidate"

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "STATE_TRANSITION").all()
    assert len(events) == 1
    assert events[0].event_data == {"from_state": "open", "to_state": "awaiting_candidate", "reason": "First outreach sent", "triggered_by": "system"}


def test_invalid_transition_rejected_status_unchanged(db_session, seeded):
    conv = seeded
    svc.transition_status(db_session, conv, "closed", reason="closing", triggered_by="system")
    db_session.commit()
    db_session.refresh(conv)
    assert conv.status == "closed"

    with pytest.raises(svc.InvalidStateTransitionError):
        svc.transition_status(db_session, conv, "awaiting_candidate", reason="illegal", triggered_by="system")

    db_session.refresh(conv)
    assert conv.status == "closed"  # unchanged -- BR-01, no silent overwrite


def test_three_transitions_produce_three_history_events(db_session, seeded):
    conv = seeded
    svc.transition_status(db_session, conv, "awaiting_candidate", reason="r1", triggered_by="system")
    svc.transition_status(db_session, conv, "open", reason="r2", triggered_by="candidate")
    svc.transition_status(db_session, conv, "closed", reason="r3", triggered_by="ai_agent")
    db_session.commit()

    events = (
        db_session.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "STATE_TRANSITION")
        .order_by(ConversationEvent.id.asc())
        .all()
    )
    assert len(events) == 3
    assert [e.event_data["to_state"] for e in events] == ["awaiting_candidate", "open", "closed"]
    assert [e.event_data["triggered_by"] for e in events] == ["system", "candidate", "ai_agent"]


def test_same_state_call_is_idempotent_not_an_error(db_session, seeded):
    conv = seeded
    svc.transition_status(db_session, conv, "open", reason="no-op", triggered_by="system")
    db_session.commit()
    db_session.refresh(conv)
    assert conv.status == "open"


def test_get_conversation_state_returns_all_three_axes(db_session, seeded):
    conv = seeded
    state = svc.get_conversation_state(db_session, conv.id, "U-ORG")
    assert state["status"] == "open"
    assert state["escalation_state"] == "none"
    assert state["owner_type"] == "ai_agent"
    assert state["entered_at"] is not None


def test_escalate_does_not_change_status(db_session, seeded):
    conv = seeded
    svc.transition_status(db_session, conv, "awaiting_candidate", reason="waiting", triggered_by="system")
    svc.escalate(db_session, conv, reason="Thunder cannot handle this", triggered_by="ai_agent")
    db_session.commit()
    db_session.refresh(conv)

    assert conv.escalation_state == "escalated"
    assert conv.status == "awaiting_candidate"  # BR-02: escalation is reversible because it never touched status


def test_resolve_escalation_restores_none_status_untouched(db_session, seeded):
    conv = seeded
    svc.escalate(db_session, conv, reason="needs human", triggered_by="ai_agent")
    svc.resolve_escalation(db_session, conv, reason="resolved by recruiter", triggered_by="U-HR-1")
    db_session.commit()
    db_session.refresh(conv)

    assert conv.escalation_state == "resolved"
    assert conv.status == "open"  # never moved


def test_pause_and_resume_round_trip_preserves_status(db_session, seeded):
    conv = seeded
    svc.transition_status(db_session, conv, "awaiting_candidate", reason="in progress", triggered_by="system")
    svc.pause_for_recruiter(db_session, conv, recruiter_user_id="U-HR-1", reason="recruiter taking over")
    db_session.commit()
    db_session.refresh(conv)
    assert conv.owner_type == "hr_user"
    assert conv.owner_id == "U-HR-1"
    assert conv.status == "awaiting_candidate"  # BR-02: PAUSED never overwrote status

    svc.resume_to_thunder(db_session, conv, ai_agent_name="thunder", reason="handing back")
    db_session.commit()
    db_session.refresh(conv)
    assert conv.owner_type == "ai_agent"
    assert conv.status == "awaiting_candidate"  # restored to the exact state that was active before PAUSED


def test_transition_status_by_id_wraps_lookup(db_session, seeded):
    conv = seeded
    svc.transition_status_by_id(db_session, conv.id, "U-ORG", "closed", reason="done", triggered_by="system")
    db_session.commit()
    db_session.refresh(conv)
    assert conv.status == "closed"


def test_transition_status_by_id_wrong_tenant_raises(db_session, seeded):
    conv = seeded
    with pytest.raises(ValueError):
        svc.transition_status_by_id(db_session, conv.id, "WRONG-TENANT", "closed", reason="x", triggered_by="system")
