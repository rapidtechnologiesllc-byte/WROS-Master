"""
HRMS-0401 bug fix -- the AI recruiter must assign itself automatically
when a candidate is created, not only when an HR user clicks "Assign AI
import logging
Recruiter" (the only path that existed until now).

Covers app.services.ai_conversation_service.auto_assign_ai_agent_on_creation(),
the function wired as a BackgroundTask from both R-07-sanctioned candidate-
creation entry points (app.api.v1.endpoints.onboarding.create_candidate and
app.api.v1.endpoints.create_job's public application endpoint).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.user import Users
from app.services.ai_conversation_service import assign_ai_agent, auto_assign_ai_agent_on_creation

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, CandidateAIAssignment.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

@pytest.fixture()
def fixtures(db_session):
    org_owner = Users(UserID="U-ORG", UserRole="Admin", UserEmail="admin@blitzenx.com", UserPassword="h")
    db_session.add(org_owner)
    db_session.commit()

    candidate = Candidate(
        candidateID="C-AUTO-1", candidateEmail="autocand@example.com", candidatePassword="h",
        candidateFirstName="Auto", candidateLastName="Assign",
    )
    db_session.add(candidate)
    db_session.commit()

    return org_owner, candidate

def test_assign_ai_agent_accepts_none_assigned_by(db_session, fixtures):
    """assigned_by is nullable for exactly this system-triggered case."""
    org_owner, candidate = fixtures
    result = assign_ai_agent(
        candidate_id=candidate.candidateID, tenant_id=org_owner.UserID, assigned_by=None, db=db_session,
    )
    assert result["candidate_id"] == candidate.candidateID

    assignment = db_session.query(CandidateAIAssignment).filter(
        CandidateAIAssignment.candidate_id == candidate.candidateID
    ).first()
    assert assignment.assigned_by is None

def test_assign_ai_agent_logs_system_triggered_when_no_assigned_by(db_session, fixtures):
    org_owner, candidate = fixtures
    assign_ai_agent(candidate_id=candidate.candidateID, tenant_id=org_owner.UserID, assigned_by=None, db=db_session)

    conversation = db_session.query(CandidateConversation).filter(
        CandidateConversation.candidate_id == candidate.candidateID
    ).first()
    event = db_session.query(ConversationEvent).filter(
        ConversationEvent.conversation_id == conversation.id,
        ConversationEvent.event_type == "ai_assigned",
    ).first()
    assert event.triggered_by == "system"

def test_assign_ai_agent_still_logs_hr_user_when_assigned_by_given(db_session, fixtures):
    org_owner, candidate = fixtures
    assign_ai_agent(candidate_id=candidate.candidateID, tenant_id=org_owner.UserID, assigned_by="U-ORG", db=db_session)

    conversation = db_session.query(CandidateConversation).filter(
        CandidateConversation.candidate_id == candidate.candidateID
    ).first()
    event = db_session.query(ConversationEvent).filter(
        ConversationEvent.conversation_id == conversation.id,
        ConversationEvent.event_type == "ai_assigned",
    ).first()
    assert event.triggered_by == "hr_user"

def test_auto_assign_creates_conversation(db_session, fixtures):
    org_owner, candidate = fixtures
    auto_assign_ai_agent_on_creation(candidate.candidateID, org_owner.UserID, db_session)

    conversation = db_session.query(CandidateConversation).filter(
        CandidateConversation.candidate_id == candidate.candidateID
    ).first()
    assert conversation is not None
    assert conversation.owner_type == "ai_agent"

def test_auto_assign_skips_gracefully_without_tenant_id(db_session, fixtures):
    org_owner, candidate = fixtures
    # Must not raise even though no tenant_id is resolvable.
    auto_assign_ai_agent_on_creation(candidate.candidateID, None, db_session)

    conversation = db_session.query(CandidateConversation).filter(
        CandidateConversation.candidate_id == candidate.candidateID
    ).first()
    assert conversation is None  # nothing created

def test_auto_assign_never_raises_on_underlying_failure(db_session):
    # Candidate doesn't exist -- assign_ai_agent() would raise HTTPException(404)
    # internally; auto_assign_ai_agent_on_creation() must swallow it, not propagate,
    # since this always runs as a background task after the HTTP response is sent.
    auto_assign_ai_agent_on_creation("DOES-NOT-EXIST", "U-ORG", db_session)  # no raise
