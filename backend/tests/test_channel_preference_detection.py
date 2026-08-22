"""
S-069/HRMS-0469 -- Multi-Channel Preference Detection
(app.services.channel_preference_service.detect_channel_preference).

Reads ConversationEvent.event_data['channel'] on 'candidate_reply'
events -- the same field send_whatsapp_message()/ai_conversation_service
already write -- per the S-002/S-003 architecture decision to extend
ConversationEvent rather than fork a new conversation_messages table.

"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.user import Users
from app.services.ai_conversation_service import AI_AGENT_NAME
from app.services.channel_preference_service import detect_channel_preference

@pytest.fixture()
def db_session():
    engine = create_engine(f"sqlite:///{db_path}")
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
        candidateID="C-200", candidateEmail="cand200@example.com", candidatePassword="h",
        candidateMobile="+19995551234",
    )
    db_session.add(candidate)
    db_session.commit()

    conversation = CandidateConversation(
        tenant_id=org_owner.UserID, candidate_id=candidate.candidateID,
        status="open", ai_agent_name=AI_AGENT_NAME, channel_preference="email",
        owner_type="ai_agent", owner_id=AI_AGENT_NAME,
    )
    db_session.add(conversation)
    db_session.commit()

    return org_owner, candidate, conversation

def _add_inbound(db, conversation, channel):
    event = ConversationEvent(
        conversation_id=conversation.id, event_type="candidate_reply",
        event_data={"channel": channel, "body": "hi"}, triggered_by="candidate",
    )
    db.add(event)
    db.commit()

def test_fewer_than_3_inbound_leaves_preference_unchanged(db_session, fixtures):
    org_owner, candidate, conversation = fixtures
    _add_inbound(db_session, conversation, "whatsapp")
    _add_inbound(db_session, conversation, "whatsapp")

    result = detect_channel_preference(db_session, conversation)

    assert result["updated"] is False
    assert result["confidence"] is None
    assert result["channel"] == "email"  # unchanged
    assert conversation.channel_preference == "email"

def test_whatsapp_dominant_updates_preference_with_full_confidence(db_session, fixtures):
    org_owner, candidate, conversation = fixtures
    for _ in range(5):
        _add_inbound(db_session, conversation, "whatsapp")

    result = detect_channel_preference(db_session, conversation)

    assert result["channel"] == "whatsapp"
    assert result["confidence"] == 1.0
    assert result["updated"] is True
    assert conversation.channel_preference == "whatsapp"

def test_mixed_channels_picks_majority(db_session, fixtures):
    org_owner, candidate, conversation = fixtures
    for _ in range(4):
        _add_inbound(db_session, conversation, "whatsapp")
    for _ in range(1):
        _add_inbound(db_session, conversation, "email")

    result = detect_channel_preference(db_session, conversation)

    assert result["channel"] == "whatsapp"
    assert result["confidence"] == 0.8
    assert result["updated"] is True

def test_no_change_when_detected_channel_matches_current(db_session, fixtures):
    org_owner, candidate, conversation = fixtures
    conversation.channel_preference = "whatsapp"
    db_session.commit()
    for _ in range(3):
        _add_inbound(db_session, conversation, "whatsapp")

    result = detect_channel_preference(db_session, conversation)

    assert result["updated"] is False
    assert result["channel"] == "whatsapp"

def test_only_last_20_inbound_events_considered(db_session, fixtures):
    org_owner, candidate, conversation = fixtures
    # 25 old whatsapp replies, then 20 recent email replies -- only the
    # most recent 20 should be considered, so email should win.
    for _ in range(25):
        _add_inbound(db_session, conversation, "whatsapp")
    for _ in range(20):
        _add_inbound(db_session, conversation, "email")

    result = detect_channel_preference(db_session, conversation)

    assert result["channel"] == "email"
    assert result["confidence"] == 1.0
