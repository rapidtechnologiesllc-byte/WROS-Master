"""
S-016/HRMS-0416 -- Conversation Filters (additive on top of S-015
search). Adapted to real status vocabulary: CandidateConversation.status
("open"/"awaiting_candidate"/"closed") and .escalation_state ("none"/
"pending"/"escalated"/"resolved") are two real, separate fields -- not
the spec's single fictional QUALIFYING/QUALIFIED/ESCALATED/PAUSED/
COMPLETED enum. has_missing_fields is computed live via the real
import logging
get_missing_fields(), no candidate_missing_fields table exists.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.conversation_search_service as svc
from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.user import Users


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__,
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
    db_session.add(owner)
    db_session.commit()

    # C-1: escalated, complete profile (every CANDIDATE_CORE_FIELDS +
    # INFO_FORM_FIELDS field filled, so get_missing_fields() returns []).
    c1 = Candidate(
        candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya",
        candidateLastName="Sharma", candidateMobile="+911234567890", candidateGender="F",
        candidateDateOfBirth=datetime(1990, 1, 1), candidateCurrentLocation="Bangalore",
        candidateJoiningDate=datetime(2026, 1, 1), candidateExperience="5 years", candidateJobTitle="Engineer",
    )
    # C-2: open, missing fields (only first name set).
    c2 = Candidate(candidateID="C-2", candidateEmail="c2@example.com", candidatePassword="h", candidateFirstName="Raj")
    db_session.add_all([c1, c2])
    db_session.commit()

    db_session.add(CandidateInfoForm(candidateID="C-1", marital_status="Single", nationality="Indian", permanent_address="Bangalore, Karnataka, India"))
    db_session.commit()

    conv1 = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", escalation_state="escalated", owner_type="ai_agent", owner_id="thunder")
    conv2 = CandidateConversation(tenant_id="U-ORG", candidate_id="C-2", status="awaiting_candidate", escalation_state="none", owner_type="ai_agent", owner_id="thunder")
    db_session.add_all([conv1, conv2])
    db_session.commit()

    db_session.add(ConversationEvent(conversation_id=conv1.id, event_type="candidate_reply", event_data={"channel": "whatsapp", "body": "Guidewire experience here"}, triggered_by="candidate"))
    db_session.add(ConversationEvent(conversation_id=conv2.id, event_type="candidate_reply", event_data={"channel": "whatsapp", "body": "Guidewire too"}, triggered_by="candidate"))
    db_session.commit()

    return conv1, conv2


def test_status_filter_or_within_type(db_session, seeded):
    result = svc.search_conversations(db_session, "U-ORG", "Guidewire", status=["awaiting_candidate"])
    assert result["total_count"] == 1
    assert result["results"][0]["candidate_id"] == "C-2"


def test_escalated_true_filter(db_session, seeded):
    result = svc.search_conversations(db_session, "U-ORG", "Guidewire", escalated=True)
    assert result["total_count"] == 1
    assert result["results"][0]["candidate_id"] == "C-1"


def test_escalated_false_filter(db_session, seeded):
    result = svc.search_conversations(db_session, "U-ORG", "Guidewire", escalated=False)
    assert result["total_count"] == 1
    assert result["results"][0]["candidate_id"] == "C-2"


def test_has_missing_fields_true_filter(db_session, seeded):
    result = svc.search_conversations(db_session, "U-ORG", "Guidewire", has_missing_fields=True)
    candidate_ids = [r["candidate_id"] for r in result["results"]]
    assert "C-2" in candidate_ids  # only has first name, everything else missing
    assert "C-1" not in candidate_ids  # complete profile in fixture


def test_updated_after_filter_excludes_stale_conversations(db_session, seeded):
    conv1, conv2 = seeded
    conv1.updated_at = datetime.utcnow() - timedelta(days=10)
    db_session.commit()

    result = svc.search_conversations(db_session, "U-ORG", "Guidewire", updated_after=datetime.utcnow() - timedelta(days=1))
    candidate_ids = [r["candidate_id"] for r in result["results"]]
    assert "C-1" not in candidate_ids


def test_combined_filters_and_logic(db_session, seeded):
    """BR-01: Status filter AND channel filter AND profile status all
    apply together (AND between types)."""
    result = svc.search_conversations(db_session, "U-ORG", "Guidewire", status=["open"], escalated=True, channel="WHATSAPP")
    assert result["total_count"] == 1
    assert result["results"][0]["candidate_id"] == "C-1"

    # Same status filter but wrong channel -> zero results.
    result2 = svc.search_conversations(db_session, "U-ORG", "Guidewire", status=["open"], escalated=True, channel="EMAIL")
    assert result2["total_count"] == 0
