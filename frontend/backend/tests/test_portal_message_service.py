"""
S-004/HRMS-0404 -- Web Portal Chat Messages (app.services.portal_message_service).
S-346/HRMS-P116 -- Portal Real-Time Chat Widget's reply-generation addition.

Adapted to real architecture: stores into ConversationEvent (channel=
"portal"), not a new conversation_messages table -- same pattern as
S-002/S-003. Throwaway SQLite -- never the real database.

No real Gemini call is made anywhere in this file -- ChatGoogleGenerativeAI
and the prompt-framework REST call are both mocked, same convention as
test_public_chat_service.py -- send_portal_message() now synchronously
generates a Thunder reply (S-346), which would otherwise hit the network
on every single test in this file.
"""
import os
import tempfile
from datetime import datetime, timedelta
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
from app.models.internal_note import InternalNote
from app.models.notification import Notification
from app.models.outreach_campaign import CampaignTouchpoint, OutreachCampaign
from app.models.prompt_execution_log import PromptExecutionLog
from app.models.sla_breach import CandidateSLABreach
from app.models.user import Jobs, Users

import app.services.prompt_framework_service as prompt_framework_svc
import app.services.thunder_service as thunder_svc
import app.services.portal_message_service as svc


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
def _mock_intent_and_escalation_llm(monkeypatch):
    """check_escalation()/detect_intent() both go through
    prompt_framework_service.call_llm()'s real default Gemini REST call
    path -- a different, separately-mocked path from thunder_service's
    LangChain-based ChatGoogleGenerativeAI above. Default resolves to
    'unclear'/no-escalation so every pre-existing test's storage-only
    assertions are unaffected by the new reply-generation step."""
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
def candidate_with_conversation(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    db_session.add(owner)
    db_session.commit()

    candidate = Candidate(candidateID="C-100", candidateEmail="cand@example.com", candidatePassword="h")
    db_session.add(candidate)
    db_session.commit()

    conversation = CandidateConversation(
        tenant_id=owner.UserID, candidate_id=candidate.candidateID,
        status="open", owner_type="ai_agent", owner_id="thunder",
    )
    db_session.add(conversation)
    db_session.commit()
    return candidate, conversation


def test_send_portal_message_stores_real_event(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    result = svc.send_portal_message(db_session, candidate, conversation.id, "Hi, when's my interview?")

    assert result["message_id"] is not None
    event = db_session.query(ConversationEvent).filter(ConversationEvent.id == result["message_id"]).first()
    assert event.event_type == "candidate_reply"
    assert event.event_data["channel"] == "portal"
    assert event.event_data["body"] == "Hi, when's my interview?"


def test_send_portal_message_trims_whitespace(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    svc.send_portal_message(db_session, candidate, conversation.id, "   hello   ")
    event = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "candidate_reply").first()
    assert event.event_data["body"] == "hello"


def test_send_portal_message_empty_raises(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    with pytest.raises(svc.PortalMessageEmpty):
        svc.send_portal_message(db_session, candidate, conversation.id, "   ")


def test_send_portal_message_too_long_raises(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    with pytest.raises(svc.PortalMessageTooLong):
        svc.send_portal_message(db_session, candidate, conversation.id, "x" * 4001)


def test_send_portal_message_wrong_candidate_raises_not_found(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    other = Candidate(candidateID="C-200", candidateEmail="other@example.com", candidatePassword="h")
    db_session.add(other)
    db_session.commit()

    with pytest.raises(svc.PortalConversationNotFound):
        svc.send_portal_message(db_session, other, conversation.id, "sneaky cross-candidate message")


def test_send_portal_message_nonexistent_conversation_raises_not_found(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    with pytest.raises(svc.PortalConversationNotFound):
        svc.send_portal_message(db_session, candidate, 999999, "hi")


def test_send_portal_message_rate_limit_21st_message_raises(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    for i in range(20):
        svc.send_portal_message(db_session, candidate, conversation.id, f"message {i}")

    with pytest.raises(svc.PortalRateLimitExceeded):
        svc.send_portal_message(db_session, candidate, conversation.id, "one too many")


def test_rate_limit_only_counts_last_hour(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    old_time = datetime.utcnow() - timedelta(hours=2)
    for i in range(20):
        event = ConversationEvent(
            conversation_id=conversation.id, event_type="candidate_reply",
            event_data={"channel": "portal", "body": f"old {i}"}, triggered_by="candidate",
        )
        db_session.add(event)
        db_session.flush()
        event.created_at = old_time
    db_session.commit()

    # All 20 are outside the rolling window -- a new message should succeed.
    result = svc.send_portal_message(db_session, candidate, conversation.id, "fresh message")
    assert result["message_id"] is not None


def test_paused_conversation_still_accepts_messages(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    conversation.status = "paused"
    db_session.commit()

    result = svc.send_portal_message(db_session, candidate, conversation.id, "still here")
    assert result["message_id"] is not None


def test_get_history_returns_ascending_order(db_session, candidate_with_conversation):
    """S-346: each send_portal_message() call now also generates a real
    (mocked) synchronous Thunder reply, so 'first'/'second' each get an
    auto-reply interleaved before the manually-stored 'reply'."""
    candidate, conversation = candidate_with_conversation
    AUTO_REPLY = "Real Thunder reply text, long enough to pass validation."
    svc.send_portal_message(db_session, candidate, conversation.id, "first")
    svc.send_portal_message(db_session, candidate, conversation.id, "second")
    svc.store_outbound_portal_message(db_session, conversation, sender_type="ai_agent", message_body="reply")
    db_session.commit()

    history = svc.get_portal_message_history(db_session, candidate, conversation.id)
    bodies = [m["message_body"] for m in history["messages"]]
    assert bodies == ["first", AUTO_REPLY, "second", AUTO_REPLY, "reply"]
    assert history["total_count"] == 5


def test_get_history_wrong_candidate_raises_not_found(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    other = Candidate(candidateID="C-200", candidateEmail="other@example.com", candidatePassword="h")
    db_session.add(other)
    db_session.commit()

    with pytest.raises(svc.PortalConversationNotFound):
        svc.get_portal_message_history(db_session, other, conversation.id)


def test_get_history_excludes_non_portal_channel_events(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    svc.send_portal_message(db_session, candidate, conversation.id, "portal message")
    db_session.add(ConversationEvent(
        conversation_id=conversation.id, event_type="ai_message_sent",
        event_data={"channel": "whatsapp", "body": "unrelated whatsapp reply"}, triggered_by="ai_agent",
    ))
    db_session.commit()

    history = svc.get_portal_message_history(db_session, candidate, conversation.id)
    # S-346: the candidate's own message plus its real (mocked) auto-reply
    # -- both channel=portal. The whatsapp event stays excluded, which is
    # this test's actual point.
    assert len(history["messages"]) == 2
    assert history["messages"][0]["message_body"] == "portal message"
    assert history["messages"][1]["message_body"] == "Real Thunder reply text, long enough to pass validation."


def test_store_outbound_portal_message_marks_delivered(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    event = svc.store_outbound_portal_message(db_session, conversation, sender_type="ai_agent", message_body="Thanks for reaching out!")
    db_session.commit()

    assert event.event_data["delivery_status"] == "DELIVERED"
    assert event.event_data["channel"] == "portal"


# ---------------------------------------------------------------------------
# S-346/HRMS-P116 -- synchronous reply generation
# ---------------------------------------------------------------------------

def test_send_portal_message_generates_a_real_reply(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    result = svc.send_portal_message(db_session, candidate, conversation.id, "What roles do you have open?")

    assert result["reply"] == "Real Thunder reply text, long enough to pass validation."
    assert result["reply_sent_at"] is not None
    assert result["escalated"] is False
    assert result["suppressed"] is False

    reply_event = (
        db_session.query(ConversationEvent)
        .filter(ConversationEvent.event_type == "ai_message_sent")
        .first()
    )
    assert reply_event is not None
    assert reply_event.event_data["channel"] == "portal"
    assert reply_event.event_data["delivery_status"] == "DELIVERED"


def test_human_owned_conversation_gets_no_auto_reply(db_session, candidate_with_conversation):
    """R-08: a human recruiter has taken over -- Thunder must not
    auto-reply on the portal either, same ownership posture as every
    other channel."""
    candidate, conversation = candidate_with_conversation
    conversation.owner_type = "hr_user"
    db_session.commit()

    result = svc.send_portal_message(db_session, candidate, conversation.id, "Any update?")

    assert result["reply"] is None
    assert db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "ai_message_sent").count() == 0


def test_thunder_paused_conversation_gets_no_auto_reply(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    conversation.is_thunder_paused = True
    db_session.commit()

    result = svc.send_portal_message(db_session, candidate, conversation.id, "Any update?")

    assert result["reply"] is None
    assert db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "ai_message_sent").count() == 0


def test_reply_generation_failure_is_fail_soft_not_fail_closed(db_session, candidate_with_conversation, monkeypatch):
    """The candidate's own message must still be stored (and the call
    must not raise) even if reply generation blows up."""
    candidate, conversation = candidate_with_conversation

    def _broken_reply(*args, **kwargs):
        raise RuntimeError("simulated reply generation failure")

    monkeypatch.setattr(
        "app.services.thunder_service.generate_thunder_reply_with_fallback", _broken_reply,
    )

    result = svc.send_portal_message(db_session, candidate, conversation.id, "hello")

    assert result["message_id"] is not None  # candidate's message still stored
    assert result["reply"] is None
    assert result["suppressed"] is True

    inbound = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "candidate_reply").first()
    assert inbound is not None
    assert inbound.event_data["body"] == "hello"
