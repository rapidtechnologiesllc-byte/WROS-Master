"""
import logging
S-024/HRMS-0424 -- Candidate Qualification Questionnaire Engine.

Real architecture adaptations under test (see qualification_engine_service
module docstring): get_next_missing_field() wraps the real
get_missing_fields() minus explicitly-skipped fields (new
CandidateFieldSkip table, not a status column on a nonexistent
candidate_missing_fields table); BR-01's QUALIFYING maps onto real
status != "closed" AND escalation_state not pending/escalated; LLM is
injectable Gemini.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_field_skip import CandidateFieldSkip
from app.models.user import Users

import app.services.qualification_engine_service as svc

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, CandidateFieldSkip.__table__,
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
    # Only candidateMobile missing among CANDIDATE_CORE_FIELDS; INFO_FORM_FIELDS all present.
    candidate = Candidate(
        candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h",
        candidateFirstName="Priya", candidateLastName="Sharma",
        candidateGender="F", candidateDateOfBirth=__import__("datetime").datetime(1990, 1, 1),
        candidateCurrentLocation="Bangalore", candidateJoiningDate=__import__("datetime").datetime(2026, 1, 1),
        candidateExperience="5 years", candidateJobTitle="Engineer",
    )
    db_session.add_all([owner, candidate])
    db_session.commit()
    db_session.add(CandidateInfoForm(candidateID="C-1", marital_status="Single", nationality="Indian", permanent_address="Bangalore, Karnataka, India"))
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="thunder", escalation_state="none")
    db_session.add(conv)
    db_session.commit()
    return candidate, conv

def test_get_next_missing_field_returns_highest_priority(db_session, seeded):
    candidate, conv = seeded
    field = svc.get_next_missing_field(db_session, candidate, "U-ORG")
    assert field["field"] == "candidateMobile"

def test_get_next_missing_field_none_when_all_present(db_session, seeded):
    candidate, conv = seeded
    candidate.candidateMobile = "+919876543210"
    db_session.commit()
    field = svc.get_next_missing_field(db_session, candidate, "U-ORG")
    assert field is None

def test_get_next_missing_field_excludes_skipped(db_session, seeded):
    candidate, conv = seeded
    svc.skip_field(db_session, "C-1", "U-ORG", "candidateMobile")
    db_session.commit()
    field = svc.get_next_missing_field(db_session, candidate, "U-ORG")
    assert field is None  # only missing field was skipped

def test_first_ask_returns_base_question(db_session, seeded):
    candidate, conv = seeded
    question = svc.generate_qualification_question(db_session, conv, "candidateMobile")
    db_session.commit()
    assert question == svc.QUALIFICATION_QUESTIONS["candidateMobile"]

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "QUESTION_ASKED").all()
    assert len(events) == 1
    assert events[0].event_data["ask_count"] == 1

def test_second_ask_returns_llm_variation(db_session, seeded):
    candidate, conv = seeded
    svc.generate_qualification_question(db_session, conv, "candidateMobile")
    db_session.commit()

    variation = "Hey again, mind sharing your phone number when you get a chance?"
    question = svc.generate_qualification_question(db_session, conv, "candidateMobile", llm_call=lambda p: variation)
    db_session.commit()

    assert question == variation
    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "QUESTION_ASKED").all()
    assert len(events) == 2
    assert events[1].event_data["ask_count"] == 2

def test_llm_failure_on_variation_falls_back_to_base_question(db_session, seeded):
    candidate, conv = seeded
    svc.generate_qualification_question(db_session, conv, "candidateMobile")
    db_session.commit()

    def broken_llm(prompt):
        raise RuntimeError("Gemini down")

    question = svc.generate_qualification_question(db_session, conv, "candidateMobile", llm_call=broken_llm)
    db_session.commit()

    assert question == svc.QUALIFICATION_QUESTIONS["candidateMobile"]
    failures = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "QUESTION_VARIATION_FAILED").all()
    assert len(failures) == 1

def test_qualification_plan_returns_next_field_and_question(db_session, seeded):
    candidate, conv = seeded
    plan = svc.get_qualification_plan(db_session, conv, candidate, "U-ORG", llm_call=lambda p: "variation")
    db_session.commit()

    assert plan["is_complete"] is False
    assert plan["next_field"] == "candidateMobile"
    assert plan["question"] == svc.QUALIFICATION_QUESTIONS["candidateMobile"]
    assert plan["remaining_fields_count"] == 1

def test_qualification_plan_complete_when_no_fields_missing(db_session, seeded):
    candidate, conv = seeded
    candidate.candidateMobile = "+919876543210"
    db_session.commit()

    plan = svc.get_qualification_plan(db_session, conv, candidate, "U-ORG")
    assert plan == {"is_complete": True, "next_field": None, "question": None, "remaining_fields_count": 0}

def test_qualification_plan_raises_when_not_qualifying_state(db_session, seeded):
    candidate, conv = seeded
    conv.status = "closed"
    db_session.commit()

    with pytest.raises(svc.QualificationNotApplicable):
        svc.get_qualification_plan(db_session, conv, candidate, "U-ORG")

def test_qualification_plan_raises_when_escalated(db_session, seeded):
    candidate, conv = seeded
    conv.escalation_state = "escalated"
    db_session.commit()

    with pytest.raises(svc.QualificationNotApplicable):
        svc.get_qualification_plan(db_session, conv, candidate, "U-ORG")

def test_auto_skip_after_max_asks_moves_to_next_field(db_session, seeded):
    candidate, conv = seeded
    # Ask candidateMobile twice already (reaches MAX_ASKS_BEFORE_AUTO_SKIP).
    svc.generate_qualification_question(db_session, conv, "candidateMobile")
    svc.generate_qualification_question(db_session, conv, "candidateMobile", llm_call=lambda p: "v2")
    db_session.commit()

    plan = svc.get_qualification_plan(db_session, conv, candidate, "U-ORG", llm_call=lambda p: "v")
    db_session.commit()

    # candidateMobile should now be auto-skipped -- since it was the only
    # missing field, the plan should be complete.
    assert plan["is_complete"] is True
    skipped = svc.skipped_field_names(db_session, "C-1", "U-ORG")
    assert "candidateMobile" in skipped

def test_skip_field_is_idempotent(db_session, seeded):
    candidate, conv = seeded
    svc.skip_field(db_session, "C-1", "U-ORG", "candidateMobile")
    svc.skip_field(db_session, "C-1", "U-ORG", "candidateMobile")
    db_session.commit()

    rows = db_session.query(CandidateFieldSkip).filter(CandidateFieldSkip.candidate_id == "C-1").all()
    assert len(rows) == 1
