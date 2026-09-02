"""
Proves the per-staff WhatsApp number routing layer built on top of
import logging
HRMS-0410's ownership model:

  - is_ai_owner() / send_whatsapp_message()'s AI-side gate: the actual
    enforcement of HRMS-0410 BR-01 / R-08 ("Thunder must never send
    while a recruiter owns the conversation"), which existed only as
    unenforced schema fields before this module.
  - resolve_outbound_whatsapp_number(): routes to the owning staff
    member's own number, falling back to the shared/default number.
  - HRMS-0409 BR-01: any human send transfers ownership unconditionally,
    even away from another human or from AI.
  - Unification: messages sent from different numbers by different
    owners all land as ConversationEvent rows under the same
    conversation_id/candidate_id.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.user import Users
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent, CandidateAIAssignment

import app.services.whatsapp_routing_service as routing
from app.services.whatsapp_routing_service import (
    is_ai_owner,
    resolve_outbound_whatsapp_number,
    take_over_conversation,
    hand_back_conversation,
    send_whatsapp_message,
    ConversationOwnedByHuman,
    NoWhatsAppNumberAvailable,
)
from app.services.ai_conversation_service import AI_AGENT_NAME
from app.services.notification_service import ChannelNotConfigured


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__,
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
    recruiter_a = Users(
        UserID="U-REC-A", UserRole="Recruiter", UserEmail="reca@blitzenx.com", UserPassword="h",
        whatsapp_number="+15550001111",
    )
    recruiter_b = Users(
        UserID="U-REC-B", UserRole="Recruiter", UserEmail="recb@blitzenx.com", UserPassword="h",
        whatsapp_number=None,  # no personal number registered
    )
    db_session.add_all([org_owner, recruiter_a, recruiter_b])
    db_session.commit()

    candidate = Candidate(
        candidateID="C-001", candidateEmail="cand@example.com", candidatePassword="h",
        candidateMobile="+19995551234",
    )
    db_session.add(candidate)
    db_session.commit()

    conversation = CandidateConversation(
        tenant_id=org_owner.UserID, candidate_id=candidate.candidateID,
        status="open", ai_agent_name=AI_AGENT_NAME, channel_preference="whatsapp",
        owner_type="ai_agent", owner_id=AI_AGENT_NAME,
    )
    db_session.add(conversation)
    db_session.commit()

    return org_owner, recruiter_a, recruiter_b, candidate, conversation


@pytest.fixture(autouse=True)
def _default_number(monkeypatch):
    monkeypatch.setattr(routing, "DEFAULT_WHATSAPP_NUMBER", "+10005550000")


# ---------------------------------------------------------------------------
# is_ai_owner / ownership transitions
# ---------------------------------------------------------------------------

def test_is_ai_owner_true_by_default(db_session, fixtures):
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures
    assert is_ai_owner(conversation) is True


def test_take_over_sets_human_owner_no_permission_check(db_session, fixtures):
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures

    take_over_conversation(db_session, conversation, recruiter_a.UserID)
    db_session.commit()

    assert conversation.owner_type == "hr_user"
    assert conversation.owner_id == recruiter_a.UserID
    assert is_ai_owner(conversation) is False


def test_any_recruiter_can_take_over_from_another(db_session, fixtures):
    """HRMS-0410 BR-03: no permission check, no lock."""
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures
    take_over_conversation(db_session, conversation, recruiter_a.UserID)
    db_session.commit()

    take_over_conversation(db_session, conversation, recruiter_b.UserID)
    db_session.commit()

    assert conversation.owner_id == recruiter_b.UserID


def test_hand_back_resets_to_ai(db_session, fixtures):
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures
    take_over_conversation(db_session, conversation, recruiter_a.UserID)
    db_session.commit()

    hand_back_conversation(db_session, conversation)
    db_session.commit()

    assert conversation.owner_type == "ai_agent"
    assert conversation.owner_id == AI_AGENT_NAME
    assert is_ai_owner(conversation) is True


# ---------------------------------------------------------------------------
# resolve_outbound_whatsapp_number
# ---------------------------------------------------------------------------

def test_resolve_number_uses_owner_personal_number(db_session, fixtures):
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures
    take_over_conversation(db_session, conversation, recruiter_a.UserID)
    db_session.commit()

    assert resolve_outbound_whatsapp_number(db_session, conversation) == "+15550001111"


def test_resolve_number_falls_back_when_owner_has_none(db_session, fixtures):
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures
    take_over_conversation(db_session, conversation, recruiter_b.UserID)
    db_session.commit()

    assert resolve_outbound_whatsapp_number(db_session, conversation) == "+10005550000"


def test_resolve_number_uses_default_when_ai_owns(db_session, fixtures):
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures
    assert resolve_outbound_whatsapp_number(db_session, conversation) == "+10005550000"


# ---------------------------------------------------------------------------
# send_whatsapp_message -- R-08 gate (the actually-missing enforcement)
# ---------------------------------------------------------------------------

def test_ai_send_allowed_when_ai_owns(db_session, fixtures):
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures

    event = send_whatsapp_message(
        db_session, conversation, candidate, "Hi, following up on your application.",
        sender_type="ai_agent", whatsapp_client=lambda to, frm, body: True,
    )
    db_session.commit()
    assert event.event_type == "ai_message_sent"
    assert event.event_data["delivered"] is True


def test_ai_send_blocked_when_human_owns(db_session, fixtures):
    """The actual R-08 fix: this gate did not exist anywhere in the
    codebase before this module -- Thunder had no way to be blocked."""
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures
    take_over_conversation(db_session, conversation, recruiter_a.UserID)
    db_session.commit()

    with pytest.raises(ConversationOwnedByHuman):
        send_whatsapp_message(
            db_session, conversation, candidate, "Automated follow-up",
            sender_type="ai_agent", whatsapp_client=lambda to, frm, body: True,
        )


def test_human_send_transfers_ownership_from_ai(db_session, fixtures):
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures
    assert conversation.owner_type == "ai_agent"

    send_whatsapp_message(
        db_session, conversation, candidate, "Hey, this is Priya from BlitzenX.",
        sender_type="hr_user", sender_id=recruiter_a.UserID,
        whatsapp_client=lambda to, frm, body: True,
    )
    db_session.commit()

    assert conversation.owner_type == "hr_user"
    assert conversation.owner_id == recruiter_a.UserID


def test_human_send_transfers_ownership_from_another_human(db_session, fixtures):
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures
    take_over_conversation(db_session, conversation, recruiter_a.UserID)
    db_session.commit()

    send_whatsapp_message(
        db_session, conversation, candidate, "Taking over from here.",
        sender_type="hr_user", sender_id=recruiter_b.UserID,
        whatsapp_client=lambda to, frm, body: True,
    )
    db_session.commit()

    assert conversation.owner_id == recruiter_b.UserID


def test_human_send_requires_sender_id(db_session, fixtures):
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures
    with pytest.raises(ValueError):
        send_whatsapp_message(
            db_session, conversation, candidate, "x", sender_type="hr_user",
            whatsapp_client=lambda to, frm, body: True,
        )


def test_invalid_sender_type_rejected(db_session, fixtures):
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures
    with pytest.raises(ValueError):
        send_whatsapp_message(db_session, conversation, candidate, "x", sender_type="bot")


# ---------------------------------------------------------------------------
# send_whatsapp_message -- number resolution + event recording
# ---------------------------------------------------------------------------

def test_send_records_owner_personal_number_as_from_number(db_session, fixtures):
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures

    event = send_whatsapp_message(
        db_session, conversation, candidate, "Hi from Aisha",
        sender_type="hr_user", sender_id=recruiter_a.UserID,
        whatsapp_client=lambda to, frm, body: True,
    )
    db_session.commit()

    assert event.event_data["from_number"] == "+15550001111"
    assert event.event_data["to_number"] == candidate.candidateMobile


def test_send_falls_back_to_default_number_for_ownerless_number(db_session, fixtures):
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures

    event = send_whatsapp_message(
        db_session, conversation, candidate, "Hi from Rahul",
        sender_type="hr_user", sender_id=recruiter_b.UserID,
        whatsapp_client=lambda to, frm, body: True,
    )
    db_session.commit()

    assert event.event_data["from_number"] == "+10005550000"


def test_send_raises_when_no_number_available_at_all(db_session, fixtures, monkeypatch):
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures
    monkeypatch.setattr(routing, "DEFAULT_WHATSAPP_NUMBER", None)
    take_over_conversation(db_session, conversation, recruiter_b.UserID)
    db_session.commit()

    with pytest.raises(NoWhatsAppNumberAvailable):
        send_whatsapp_message(
            db_session, conversation, candidate, "x",
            sender_type="hr_user", sender_id=recruiter_b.UserID,
            whatsapp_client=lambda to, frm, body: True,
        )


def test_default_client_raises_channel_not_configured_and_is_recorded_as_not_delivered(db_session, fixtures):
    """No whatsapp_client injected -- exercises the real default stub,
    which is honest about WhatsApp not being provisioned rather than
    silently pretending to succeed."""
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures

    event = send_whatsapp_message(
        db_session, conversation, candidate, "Hi",
        sender_type="hr_user", sender_id=recruiter_a.UserID,
    )
    db_session.commit()

    assert event.event_data["delivered"] is False


# ---------------------------------------------------------------------------
# Unification: different numbers/owners, same conversation/candidate
# ---------------------------------------------------------------------------

def test_messages_from_different_owners_unify_under_same_conversation(db_session, fixtures):
    org_owner, recruiter_a, recruiter_b, candidate, conversation = fixtures

    send_whatsapp_message(
        db_session, conversation, candidate, "AI: checking on your documents",
        sender_type="ai_agent", whatsapp_client=lambda to, frm, body: True,
    )
    db_session.commit()

    send_whatsapp_message(
        db_session, conversation, candidate, "Recruiter A taking over",
        sender_type="hr_user", sender_id=recruiter_a.UserID,
        whatsapp_client=lambda to, frm, body: True,
    )
    db_session.commit()

    send_whatsapp_message(
        db_session, conversation, candidate, "Recruiter B handling now",
        sender_type="hr_user", sender_id=recruiter_b.UserID,
        whatsapp_client=lambda to, frm, body: True,
    )
    db_session.commit()

    events = db_session.query(ConversationEvent).filter(
        ConversationEvent.conversation_id == conversation.id
    ).order_by(ConversationEvent.id).all()

    assert len(events) == 3
    from_numbers = [e.event_data["from_number"] for e in events]
    # Three different senders, three different numbers, same conversation/candidate throughout.
    assert from_numbers == ["+10005550000", "+15550001111", "+10005550000"]  # AI default, A's own, B's fallback
    assert all(e.conversation_id == conversation.id for e in events)
    assert conversation.candidate_id == candidate.candidateID
