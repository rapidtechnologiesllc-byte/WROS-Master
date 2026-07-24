"""
S-025/HRMS-0425 -- AI Qualification Conversation Engine.

Real architecture adaptations under test (see
qualification_conversation_service module docstring): reuses the real
is_ai_owner() (R-08), the real get_qualification_plan() (S-024), the
real transition_status() (S-018) collapsing QUALIFIED/COMPLETED into
the one real terminal "closed" state; not_interested detection is a
deterministic phrase heuristic (no HRMS-0433 Intent Detection exists);
channel dispatch falls back to a direct ConversationEvent log for
email/unset channels.

sleep_fn is injected as a no-op so tests don't actually sleep 2s.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_field_skip import CandidateFieldSkip
from app.models.consent import ConsentRecord
from app.models.user import Users

import app.services.qualification_conversation_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, CandidateFieldSkip.__table__,
        ConsentRecord.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _no_sleep(seconds):
    pass


@pytest.fixture()
def seeded(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    # Only candidateMobile missing -- one qualification question away from complete.
    candidate = Candidate(
        candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h",
        candidateFirstName="Priya", candidateLastName="Sharma",
        candidateGender="F", candidateDateOfBirth=datetime(1990, 1, 1),
        candidateCurrentLocation="Bangalore", candidateJoiningDate=datetime(2026, 1, 1),
        candidateExperience="5 years", candidateJobTitle="Engineer",
    )
    db_session.add_all([owner, candidate])
    db_session.commit()
    db_session.add(CandidateInfoForm(candidateID="C-1", marital_status="Single", nationality="Indian", permanent_address="Bangalore, Karnataka, India"))
    db_session.commit()

    conv = CandidateConversation(
        tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="thunder",
        escalation_state="none", channel_preference="email",
    )
    db_session.add(conv)
    db_session.commit()
    return candidate, conv


def test_recruiter_owned_conversation_thunder_stays_silent(db_session, seeded):
    candidate, conv = seeded
    conv.owner_type = "hr_user"
    conv.owner_id = "U-REC"
    db_session.commit()

    result = svc.run_qualification_turn(db_session, conv, candidate, "U-ORG", "Hi there", sleep_fn=_no_sleep)
    assert result["action"] == "skipped_recruiter_owns"

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id).all()
    assert events == []  # BR-03: no message sent at all


def test_not_qualifying_state_no_op(db_session, seeded):
    candidate, conv = seeded
    conv.status = "closed"
    db_session.commit()

    result = svc.run_qualification_turn(db_session, conv, candidate, "U-ORG", "Hi", sleep_fn=_no_sleep)
    assert result["action"] == "not_qualifying"


def test_not_interested_transitions_to_closed_and_sends_graceful_message(db_session, seeded):
    candidate, conv = seeded
    result = svc.run_qualification_turn(db_session, conv, candidate, "U-ORG", "Thanks but I'm not interested at this time", sleep_fn=_no_sleep)

    assert result["action"] == "not_interested"
    db_session.refresh(conv)
    assert conv.status == "closed"

    not_interested_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "CANDIDATE_NOT_INTERESTED").all()
    assert len(not_interested_events) == 1

    sent_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "ai_message_sent").all()
    assert len(sent_events) == 1
    assert "no worries" in sent_events[0].event_data["body"].lower()


def test_qualification_question_sent_for_missing_field(db_session, seeded):
    candidate, conv = seeded
    result = svc.run_qualification_turn(db_session, conv, candidate, "U-ORG", "Sure, here's some info", llm_call=lambda p: "variation", sleep_fn=_no_sleep)

    assert result["action"] == "qualification_question_sent"
    assert result["next_field"] == "candidateMobile"
    assert "Great, thanks for sharing that!" in result["message"]

    sent_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "ai_message_sent").all()
    assert len(sent_events) == 1


def test_candidate_question_answered_before_next_field(db_session, seeded):
    candidate, conv = seeded

    def fake_answer(db, cand, message):
        return "BlitzenX places engineers in P&C insurance technology roles."

    result = svc.run_qualification_turn(
        db_session, conv, candidate, "U-ORG", "What kind of roles does BlitzenX place?",
        answer_question_fn=fake_answer, sleep_fn=_no_sleep,
    )

    assert result["action"] == "qualification_question_sent"
    assert "BlitzenX places engineers" in result["message"]
    assert "To continue getting to know your background" in result["message"]


def test_qualification_complete_transitions_and_sends_completion_message(db_session, seeded):
    candidate, conv = seeded
    candidate.candidateMobile = "+919876543210"  # last missing field now filled
    db_session.commit()

    result = svc.run_qualification_turn(db_session, conv, candidate, "U-ORG", "Here's my number", sleep_fn=_no_sleep)

    assert result["action"] == "qualification_complete"
    db_session.refresh(conv)
    assert conv.status == "closed"
    assert conv.next_action == "ready_for_matching"

    sent_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "ai_message_sent").all()
    assert len(sent_events) == 1
    assert "Priya" in sent_events[0].event_data["body"]


def test_whatsapp_channel_dispatches_through_send_thunder_message(db_session, seeded, monkeypatch):
    import app.services.whatsapp_routing_service as wr_svc
    monkeypatch.setattr(wr_svc, "DEFAULT_WHATSAPP_NUMBER", "+15550009999")

    candidate, conv = seeded
    candidate.candidateMobile = "+919876543210"
    conv.channel_preference = "whatsapp"
    db_session.commit()
    db_session.add(ConsentRecord(subject_type="candidate", subject_id="C-1", consent_type="whatsapp_outreach", consent_given=True, captured_by="system"))
    db_session.commit()

    result = svc.run_qualification_turn(
        db_session, conv, candidate, "U-ORG", "Here's my number",
        whatsapp_client=lambda *a, **kw: True, sleep_fn=_no_sleep,
    )
    assert result["action"] == "qualification_complete"

    sent_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "ai_message_sent").all()
    assert len(sent_events) == 1
    assert sent_events[0].event_data["channel"] == "whatsapp"


def test_portal_channel_dispatches_through_portal_message_service(db_session, seeded):
    candidate, conv = seeded
    conv.channel_preference = "portal"
    db_session.commit()

    result = svc.run_qualification_turn(db_session, conv, candidate, "U-ORG", "Sure", llm_call=lambda p: "v", sleep_fn=_no_sleep)
    assert result["action"] == "qualification_question_sent"

    sent_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id).all()
    assert any(e.event_data and e.event_data.get("channel") == "portal" for e in sent_events)
