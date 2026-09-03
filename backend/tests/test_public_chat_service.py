"""
Public Thunder Chat (app.services.public_chat_service) -- the real,
unauthenticated candidate-facing chat widget. Proves: a fresh visitor
becomes a real Candidate row through create_candidate_safe(), a
returning visitor (matched by email) resumes the same conversation
instead of duplicating it, consent is required and captured for real,
and every message after the opening greeting goes through the same
governed send_thunder_message() path WhatsApp candidates use -- just
import logging
on the "web_chat" channel.

No real Gemini call is made anywhere in this file -- ChatGoogleGenerativeAI
is mocked, same convention as test_thunder_test_chat.py.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.candidate_field_skip import CandidateFieldSkip
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.candidate_memory import CandidateMemory, CandidateMemoryFact
from app.models.candidate_sentiment_log import CandidateSentimentLog
from app.models.consent import ConsentRecord
from app.models.follow_up_schedule import FollowUpSchedule
from app.models.outreach_campaign import CampaignTouchpoint, OutreachCampaign
from app.models.internal_note import InternalNote
from app.models.notification import Notification
from app.models.prompt_execution_log import PromptExecutionLog
from app.models.sla_breach import CandidateSLABreach
from app.models.user import Jobs, Users

import app.services.prompt_framework_service as prompt_framework_svc
import app.services.thunder_service as thunder_svc
import app.services.whatsapp_routing_service as routing
import app.services.public_chat_service as svc

@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setattr(thunder_svc, "GEMINI_API_KEY", "fake-key-for-test")

@pytest.fixture(autouse=True)
def _mock_gemini(monkeypatch):
    mock_response = MagicMock()
    mock_response.content = "Real Thunder reply text, long enough to pass validation."
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    monkeypatch.setattr(thunder_svc, "ChatGoogleGenerativeAI", MagicMock(return_value=mock_llm))

@pytest.fixture(autouse=True)
def _mock_intent_detection_llm(monkeypatch):
    """S-072/HRMS-0472: send_public_chat_message() now calls
    detect_intent_service.detect_intent() on every turn (its first
    live wiring -- see public_chat_service's own inline comment), which
    goes through prompt_framework_service.call_llm()'s REAL default
    Gemini REST call path -- a different, separately-mocked path from
    thunder_service's LangChain-based ChatGoogleGenerativeAI above.
    Without this, every test in this file would attempt a real network
    call (and a real 3s retry sleep on failure) the moment this story
    landed. Default resolves to 'unclear' so every pre-existing test's
    behavior is unchanged (falls through to the normal reply path);
    individual objection-handling tests override this per-test."""
    monkeypatch.setattr(prompt_framework_svc, "_default_llm_call", lambda *a, **k: '{"intent": "unclear", "confidence": 0.0}')

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, Jobs.__table__, CandidateInfoForm.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, CandidateAIAssignment.__table__,
        Notification.__table__, ConsentRecord.__table__, InternalNote.__table__, FollowUpSchedule.__table__,
        CandidateGhostingStatus.__table__, OutreachCampaign.__table__, CampaignTouchpoint.__table__,
        CandidateFieldSkip.__table__, CandidateMemory.__table__, CandidateMemoryFact.__table__,
        PromptExecutionLog.__table__, CandidateSLABreach.__table__, CandidateSentimentLog.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

@pytest.fixture()
def super_user(db_session):
    user = Users(UserID="U-CEO", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    db_session.add(user)
    db_session.commit()
    return user

def test_start_public_chat_creates_real_candidate_and_conversation(db_session, super_user):
    result = svc.start_public_chat(
        db_session, full_name="Jane Doe", email="jane@example.com",
        phone="+15550001111", job_id=None, consent=True,
    )

    assert result["status"] == "started"
    candidate = db_session.query(Candidate).filter(Candidate.candidateID == result["candidate_id"]).first()
    assert candidate is not None
    assert candidate.candidateEmail == "jane@example.com"
    assert candidate.candidateSource == "public_web_chat"

    conversation = (
        db_session.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate.candidateID)
        .first()
    )
    assert conversation is not None
    assert conversation.channel_preference == "web_chat"
    assert conversation.owner_type == "ai_agent"

    consent = (
        db_session.query(ConsentRecord)
        .filter(ConsentRecord.subject_id == candidate.candidateID, ConsentRecord.consent_type == "web_chat_outreach")
        .first()
    )
    assert consent is not None
    assert consent.consent_given is True

    assert "Jane" in result["message"]

def test_start_public_chat_requires_consent(db_session, super_user):
    with pytest.raises(svc.PublicChatConsentRequired):
        svc.start_public_chat(
            db_session, full_name="Jane Doe", email="jane@example.com",
            phone=None, job_id=None, consent=False,
        )

def test_start_public_chat_with_no_super_user_raises(db_session):
    with pytest.raises(svc.PublicChatNoTenantAvailable):
        svc.start_public_chat(
            db_session, full_name="Jane Doe", email="jane@example.com",
            phone=None, job_id=None, consent=True,
        )

def test_start_public_chat_resumes_existing_candidate_by_email(db_session, super_user):
    first = svc.start_public_chat(
        db_session, full_name="Jane Doe", email="jane@example.com",
        phone=None, job_id=None, consent=True,
    )
    second = svc.start_public_chat(
        db_session, full_name="Jane Doe", email="jane@example.com",
        phone=None, job_id=None, consent=True,
    )

    assert second["status"] == "resumed"
    assert second["candidate_id"] == first["candidate_id"]

    # Exactly one candidate, one open conversation -- no duplicate created.
    assert db_session.query(Candidate).filter(Candidate.candidateEmail == "jane@example.com").count() == 1
    assert db_session.query(CandidateConversation).filter(
        CandidateConversation.candidate_id == first["candidate_id"],
    ).count() == 1

def test_send_public_chat_message_unknown_candidate_raises(db_session, super_user):
    with pytest.raises(svc.PublicChatSessionNotFound):
        svc.send_public_chat_message(db_session, candidate_id="CAN-does-not-exist", message="hello")

def test_send_public_chat_message_logs_real_events_and_replies(db_session, super_user):
    started = svc.start_public_chat(
        db_session, full_name="Jane Doe", email="jane@example.com",
        phone=None, job_id=None, consent=True,
    )

    result = svc.send_public_chat_message(
        db_session, candidate_id=started["candidate_id"], message="What roles do you have open?",
    )
    assert result["reply"] == "Real Thunder reply text, long enough to pass validation."

    conversation = (
        db_session.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == started["candidate_id"])
        .first()
    )
    events = (
        db_session.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation.id)
        .order_by(ConversationEvent.id.asc())
        .all()
    )
    # assign_ai_agent() also fires a real "missing profile fields" email
    # (a legitimate ai_message_sent event on channel="email") -- only
    # assert on the web_chat-channel events this test actually cares about.
    web_chat_events = [e for e in events if e.event_data.get("channel") == "web_chat"]
    web_chat_event_types = [e.event_type for e in web_chat_events]
    assert "candidate_reply" in web_chat_event_types
    assert "ai_message_sent" in web_chat_event_types

def test_send_public_chat_message_objecting_intent_routes_to_objection_handler(db_session, super_user, monkeypatch):
    """S-072/HRMS-0472: the first live, end-to-end proof that
    detect_intent()'s 'objecting' branch actually reaches
    handle_objection() -- production code calls check_escalation()
    (S-035), detect_intent() (S-033), and classify_objection() (S-072)
    IN THAT ORDER, all through the same unmocked
    prompt_framework_service._default_llm_call() path (none of them
    are given their own llm_call override), so this queues three
    canned JSON responses -- the first satisfies check_escalation's own
    ESCALATION_CHECK call (needs_escalation=false, so it falls through
    normally), the second is the intent classification, the third is
    the objection classification."""
    started = svc.start_public_chat(db_session, full_name="Jane Doe", email="jane@example.com", phone=None, job_id=None, consent=True)

    responses = iter([
        '{"needs_escalation": false}',
        '{"intent": "objecting", "confidence": 0.9}',
        '{"objection_type": "LOCATION", "key_concern": "not willing to relocate", "confidence": 0.88}',
    ])
    monkeypatch.setattr(prompt_framework_svc, "_default_llm_call", lambda *a, **k: next(responses))

    result = svc.send_public_chat_message(db_session, candidate_id=started["candidate_id"], message="I'm not willing to relocate for this role")

    assert result.get("escalated") is not True
    conversation = db_session.query(CandidateConversation).filter(CandidateConversation.candidate_id == started["candidate_id"]).first()
    objection_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conversation.id, ConversationEvent.event_type == "OBJECTION_RAISED").all()
    assert len(objection_events) == 1
    assert objection_events[0].event_data["objection_type"] == "LOCATION"

def test_send_public_chat_message_third_objection_escalates(db_session, super_user, monkeypatch):
    """BR-01, proven end-to-end through the real public chat entry
    point: the 3rd SALARY objection in the same conversation escalates
    instead of Thunder responding again."""
    started = svc.start_public_chat(db_session, full_name="Jane Doe", email="jane@example.com", phone=None, job_id=None, consent=True)
    candidate_id = started["candidate_id"]

    no_escalation = '{"needs_escalation": false}'
    salary_intent = '{"intent": "objecting", "confidence": 0.9}'
    salary_objection = '{"objection_type": "SALARY", "key_concern": "wants more money", "confidence": 0.9}'

    def _queue_one_turn():
        it = iter([no_escalation, salary_intent, salary_objection])
        monkeypatch.setattr(prompt_framework_svc, "_default_llm_call", lambda *a, **k: next(it))

    _queue_one_turn()
    r1 = svc.send_public_chat_message(db_session, candidate_id=candidate_id, message="salary too low")
    assert r1.get("escalated") is not True

    _queue_one_turn()
    r2 = svc.send_public_chat_message(db_session, candidate_id=candidate_id, message="still think salary is low")
    assert r2.get("escalated") is not True

    _queue_one_turn()
    r3 = svc.send_public_chat_message(db_session, candidate_id=candidate_id, message="salary still an issue")
    assert r3.get("escalated") is True

    conversation = db_session.query(CandidateConversation).filter(CandidateConversation.candidate_id == candidate_id).first()
    assert conversation.escalation_state == "escalated"

def test_get_public_chat_history_returns_full_transcript(db_session, super_user):
    started = svc.start_public_chat(
        db_session, full_name="Jane Doe", email="jane@example.com",
        phone=None, job_id=None, consent=True,
    )
    svc.send_public_chat_message(db_session, candidate_id=started["candidate_id"], message="Hi there")

    history = svc.get_public_chat_history(db_session, candidate_id=started["candidate_id"])
    senders = [m["sender"] for m in history]
    assert senders == ["thunder", "candidate", "thunder"]
