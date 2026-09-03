"""
HRMS-0401/0409 bug fix -- a candidate's reply to the AI recruiter's
missing-fields email was never actually processed by anything (the
webhook endpoint's own docstring said "by a scheduler polling the Graph
inbox periodically", but no such scheduler job existed, and no UI called
import logging
the manual poll endpoint either).

Covers app.services.ai_conversation_service.poll_all_awaiting_candidates(),
the function now wired into app.core.scheduler's 15-minute job.

process_candidate_reply is monkeypatched here so these tests are about
poll_all_awaiting_candidates()'s own batching/isolation logic, not the
Graph/Gemini pipeline (covered elsewhere).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.ai_conversation_service as ai_conversation_service
from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.user import Users
from app.services.ai_conversation_service import AI_AGENT_NAME, poll_all_awaiting_candidates

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

def _make_conversation(db, candidate_id, status):
    org_owner = db.query(Users).filter(Users.UserID == "U-ORG").first()
    if not org_owner:
        org_owner = Users(UserID="U-ORG", UserRole="Admin", UserEmail="admin@blitzenx.com", UserPassword="h")
        db.add(org_owner)
        db.commit()

    candidate = Candidate(candidateID=candidate_id, candidateEmail=f"{candidate_id}@example.com", candidatePassword="h")
    db.add(candidate)
    db.commit()

    conversation = CandidateConversation(
        tenant_id="U-ORG", candidate_id=candidate_id, status=status,
        ai_agent_name=AI_AGENT_NAME, owner_type="ai_agent", owner_id=AI_AGENT_NAME,
    )
    db.add(conversation)
    db.commit()
    return conversation

def test_only_awaiting_candidates_are_polled(db_session, monkeypatch):
    _make_conversation(db_session, "C-AWAIT-1", "awaiting_candidate")
    _make_conversation(db_session, "C-OPEN-1", "open")
    _make_conversation(db_session, "C-CLOSED-1", "closed")

    polled_ids = []

    def fake_process(candidate_id, db):
        polled_ids.append(candidate_id)
        return {"status": "no_reply_found"}

    monkeypatch.setattr(ai_conversation_service, "process_candidate_reply", fake_process)

    result = poll_all_awaiting_candidates(db_session)

    assert polled_ids == ["C-AWAIT-1"]
    assert result["checked"] == 1
    assert result["processed"] == 1

def test_counts_updated_fields_correctly(db_session, monkeypatch):
    _make_conversation(db_session, "C-AWAIT-1", "awaiting_candidate")
    _make_conversation(db_session, "C-AWAIT-2", "awaiting_candidate")

    def fake_process(candidate_id, db):
        if candidate_id == "C-AWAIT-1":
            return {"status": "partial", "updated_fields": ["candidateGender"]}
        return {"status": "no_reply_found"}

    monkeypatch.setattr(ai_conversation_service, "process_candidate_reply", fake_process)

    result = poll_all_awaiting_candidates(db_session)

    assert result["checked"] == 2
    assert result["processed"] == 2
    assert result["updated"] == 1

def test_one_candidate_error_does_not_block_others(db_session, monkeypatch):
    _make_conversation(db_session, "C-FAIL", "awaiting_candidate")
    _make_conversation(db_session, "C-OK", "awaiting_candidate")

    def fake_process(candidate_id, db):
        if candidate_id == "C-FAIL":
            raise RuntimeError("Graph API exploded")
        return {"status": "no_reply_found"}

    monkeypatch.setattr(ai_conversation_service, "process_candidate_reply", fake_process)

    result = poll_all_awaiting_candidates(db_session)  # must not raise

    assert result["checked"] == 2
    assert result["processed"] == 1  # only C-OK succeeded
    assert len(result["errors"]) == 1
    assert "C-FAIL" in result["errors"][0]

def test_no_awaiting_candidates_returns_zero_counts(db_session):
    result = poll_all_awaiting_candidates(db_session)
    assert result == {"checked": 0, "processed": 0, "updated": 0, "errors": []}
