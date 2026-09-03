"""
import logging
S-013/HRMS-0413 -- Email First Engagement, parallel channel to S-012.

No message_templates table (hardcoded fallback IS the real template).
EmailService.send_email is mocked -- no real MS Graph call.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.email_first_engagement_service as svc
from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.message_template import MessageTemplate
from app.models.user import Users

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__,
        ConversationEvent.__table__, CandidateAIAssignment.__table__, MessageTemplate.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

def _make_candidate_and_conversation(db, *, created_at=None):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    db.add(owner)
    db.commit()

    candidate = Candidate(
        candidateID="C-100", candidateEmail="cand@example.com", candidatePassword="h",
        candidateFirstName="Jordan", candidateCreatedAt=created_at or datetime.utcnow(),
    )
    db.add(candidate)
    db.commit()

    conversation = CandidateConversation(tenant_id="U-ORG", candidate_id="C-100", status="open", owner_type="ai_agent", owner_id="onboarding-ai")
    db.add(conversation)
    db.commit()
    return candidate, conversation

def _no_sleep(seconds):
    pass

def test_successful_send_stores_and_signs(db_session):
    _make_candidate_and_conversation(db_session)
    with patch.object(svc.EmailService, "send_email", return_value={"status": "success"}) as mock_send:
        result = svc.send_first_email_engagement(db_session, "C-100", "U-ORG", _sleep=_no_sleep)

    assert result["status"] == "sent"
    assert mock_send.called
    _, kwargs = mock_send.call_args
    assert "Jordan" in kwargs["subject"]
    assert svc.THUNDER_SIGNATURE in kwargs["body_content"]
    assert "{" not in kwargs["subject"] and "{" not in kwargs["body_content"]

    sent_event = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "FIRST_EMAIL_SENT").first()
    assert sent_event is not None

def test_sla_breach_logged_independently(db_session):
    old_created_at = datetime.utcnow() - timedelta(seconds=90)
    _make_candidate_and_conversation(db_session, created_at=old_created_at)
    with patch.object(svc.EmailService, "send_email", return_value={"status": "success"}):
        result = svc.send_first_email_engagement(db_session, "C-100", "U-ORG", _sleep=_no_sleep)

    assert result["sla_met"] is False
    breach = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "SLA_BREACH", ConversationEvent.event_data.isnot(None)).first()
    assert breach.event_data["channel"] == "email"

def test_idempotent_second_trigger_prevented(db_session):
    _make_candidate_and_conversation(db_session)
    with patch.object(svc.EmailService, "send_email", return_value={"status": "success"}):
        svc.send_first_email_engagement(db_session, "C-100", "U-ORG", _sleep=_no_sleep)
        result = svc.send_first_email_engagement(db_session, "C-100", "U-ORG", _sleep=_no_sleep)

    assert result["status"] == "duplicate_prevented"
    sent_events = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "FIRST_EMAIL_SENT").all()
    assert len(sent_events) == 1

def test_retry_once_then_succeed(db_session):
    _make_candidate_and_conversation(db_session)
    attempts = {"count": 0}

    def flaky_send(**kwargs):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise HTTPException(status_code=500, detail="graph down")
        return {"status": "success"}

    with patch.object(svc.EmailService, "send_email", side_effect=flaky_send):
        result = svc.send_first_email_engagement(db_session, "C-100", "U-ORG", _sleep=_no_sleep)

    assert result["status"] == "sent"
    assert attempts["count"] == 2

def test_both_attempts_fail_emits_failure_no_crash(db_session):
    _make_candidate_and_conversation(db_session)
    with patch.object(svc.EmailService, "send_email", side_effect=HTTPException(status_code=500, detail="down")):
        result = svc.send_first_email_engagement(db_session, "C-100", "U-ORG", _sleep=_no_sleep)

    assert result["status"] == "failed"
    failure = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "FIRST_EMAIL_FAILED").first()
    assert failure is not None

def test_render_greeting_email_contains_signature_and_no_placeholders(db_session):
    candidate, _ = _make_candidate_and_conversation(db_session)
    rendered = svc._render_greeting_email(db_session, candidate, "Thunder", "U-ORG")
    assert svc.THUNDER_SIGNATURE in rendered["body"]
    assert "Jordan" in rendered["subject"]
    assert "{" not in rendered["subject"] and "{" not in rendered["body"]
