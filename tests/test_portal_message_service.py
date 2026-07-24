"""
S-004/HRMS-0404 -- Web Portal Chat Messages (app.services.portal_message_service).

Adapted to real architecture: stores into ConversationEvent (channel=
"portal"), not a new conversation_messages table -- same pattern as
S-002/S-003. Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.user import Users

import app.services.portal_message_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
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
    candidate, conversation = candidate_with_conversation
    svc.send_portal_message(db_session, candidate, conversation.id, "first")
    svc.send_portal_message(db_session, candidate, conversation.id, "second")
    svc.store_outbound_portal_message(db_session, conversation, sender_type="ai_agent", message_body="reply")
    db_session.commit()

    history = svc.get_portal_message_history(db_session, candidate, conversation.id)
    bodies = [m["message_body"] for m in history["messages"]]
    assert bodies == ["first", "second", "reply"]
    assert history["total_count"] == 3


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
    assert len(history["messages"]) == 1
    assert history["messages"][0]["message_body"] == "portal message"


def test_store_outbound_portal_message_marks_delivered(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    event = svc.store_outbound_portal_message(db_session, conversation, sender_type="ai_agent", message_body="Thanks for reaching out!")
    db_session.commit()

    assert event.event_data["delivery_status"] == "DELIVERED"
    assert event.event_data["channel"] == "portal"
