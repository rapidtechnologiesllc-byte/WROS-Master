"""
S-002/HRMS-0402 -- WhatsApp Webhook (app.services.whatsapp_webhook_service).

Tests against Meta's real documented Cloud API payload shapes (message
IDs prefixed "wamid.", unix-epoch timestamps as strings, etc.) -- no
live Meta connection, same convention as every other Gemini/external-
API mock in this codebase. Covers the acceptance criteria from
S-002_HRMS-0402.docx that this codebase's real architecture can
satisfy (see the module's own docstring for the one honestly-flagged
gap: outbound wamid capture for delivery-status matching).

"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.follow_up_schedule import FollowUpSchedule
from app.models.outreach_campaign import CampaignTouchpoint, OutreachCampaign
from app.models.user import Users

import app.services.whatsapp_webhook_service as svc

@pytest.fixture(autouse=True)
def _webhook_secrets(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", "test-verify-token")
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "test-app-secret")

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
def candidate_with_conversation(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    db_session.add(owner)
    db_session.commit()

    candidate = Candidate(
        candidateID="C-100", candidateEmail="cand@example.com", candidatePassword="h",
        candidateMobile="+12025551234",
    )
    db_session.add(candidate)
    db_session.commit()

    conversation = CandidateConversation(
        tenant_id=owner.UserID, candidate_id=candidate.candidateID,
        status="open", owner_type="ai_agent", owner_id="thunder",
    )
    db_session.add(conversation)
    db_session.commit()
    return candidate, conversation

# ---------------------------------------------------------------------------
# GET verification (AC-1, AC-2)
# ---------------------------------------------------------------------------

def test_verify_webhook_challenge_correct_token_returns_challenge():
    result = svc.verify_webhook_challenge("subscribe", "test-verify-token", "abc123")
    assert result == "abc123"

def test_verify_webhook_challenge_wrong_token_returns_none():
    assert svc.verify_webhook_challenge("subscribe", "wrong-token", "abc123") is None

def test_verify_webhook_challenge_wrong_mode_returns_none():
    assert svc.verify_webhook_challenge("unsubscribe", "test-verify-token", "abc123") is None

def test_verify_webhook_challenge_unconfigured_secret_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", "")
    assert svc.verify_webhook_challenge("subscribe", "anything", "abc123") is None

# ---------------------------------------------------------------------------
# Signature validation
# ---------------------------------------------------------------------------

def test_validate_signature_correct_hmac_passes():
    import hashlib, hmac
    body = b'{"test":"payload"}'
    sig = "sha256=" + hmac.new(b"test-app-secret", body, hashlib.sha256).hexdigest()
    assert svc.validate_signature(body, sig) is True

def test_validate_signature_wrong_hmac_fails():
    body = b'{"test":"payload"}'
    assert svc.validate_signature(body, "sha256=deadbeef") is False

def test_validate_signature_missing_header_fails():
    assert svc.validate_signature(b'{}', None) is False

def test_validate_signature_unconfigured_secret_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "")
    assert svc.validate_signature(b'{}', "sha256=whatever") is False

# ---------------------------------------------------------------------------
# Phone normalization (BR-04)
# ---------------------------------------------------------------------------

def test_normalize_e164_adds_plus_prefix():
    assert svc.normalize_e164("12025551234") == "+12025551234"

def test_normalize_e164_keeps_existing_plus():
    assert svc.normalize_e164("+12025551234") == "+12025551234"

def test_normalize_e164_strips_non_digits():
    assert svc.normalize_e164("+1 (202) 555-1234") == "+12025551234"

# ---------------------------------------------------------------------------
# Inbound message storage (AC-4, AC-6, AC-11, AC-12, AC-13)
# ---------------------------------------------------------------------------

def test_store_inbound_text_message(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    message = {
        "id": "wamid.ABC123",
        "from": "12025551234",
        "timestamp": "1721740800",
        "type": "text",
        "text": {"body": "Hi, is this role still open?"},
    }
    result = svc.store_inbound_whatsapp_message(db_session, message)

    assert result["status"] == "stored"
    assert result["candidate_id"] == candidate.candidateID

    event = db_session.query(ConversationEvent).filter(ConversationEvent.id == result["event_id"]).first()
    assert event.event_type == "candidate_reply"
    assert event.event_data["channel"] == "whatsapp"
    assert event.event_data["body"] == "Hi, is this role still open?"
    assert event.event_data["whatsapp_message_id"] == "wamid.ABC123"

def test_store_inbound_message_deduplicates_same_wamid(db_session, candidate_with_conversation):
    message = {"id": "wamid.DUP1", "from": "12025551234", "timestamp": "1721740800", "type": "text", "text": {"body": "hello"}}
    first = svc.store_inbound_whatsapp_message(db_session, message)
    second = svc.store_inbound_whatsapp_message(db_session, message)

    assert first["status"] == "stored"
    assert second["status"] == "duplicate"

    count = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "candidate_reply").count()
    assert count == 1

def test_store_inbound_message_unknown_sender_no_crash_no_record(db_session, candidate_with_conversation):
    message = {"id": "wamid.XYZ", "from": "19995550000", "timestamp": "1721740800", "type": "text", "text": {"body": "hi"}}
    result = svc.store_inbound_whatsapp_message(db_session, message)

    assert result["status"] == "unknown_sender"
    assert db_session.query(ConversationEvent).count() == 0

def test_store_inbound_message_no_active_conversation(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    conversation.status = "closed"
    db_session.commit()

    message = {"id": "wamid.NOCONV", "from": "12025551234", "timestamp": "1721740800", "type": "text", "text": {"body": "hi"}}
    result = svc.store_inbound_whatsapp_message(db_session, message)

    assert result["status"] == "no_active_conversation"

def test_store_inbound_document_message_stores_media_id_without_url(db_session, candidate_with_conversation):
    """No S3 configured in this environment -- media_url stays None,
    message is still stored (never lost over a media failure, per the
    spec's own BR-01/Step 5 fallback)."""
    message = {
        "id": "wamid.DOC1", "from": "12025551234", "timestamp": "1721740800",
        "type": "document", "document": {"id": "media-id-123", "filename": "resume.pdf"},
    }
    result = svc.store_inbound_whatsapp_message(db_session, message)
    assert result["status"] == "stored"

    event = db_session.query(ConversationEvent).filter(ConversationEvent.id == result["event_id"]).first()
    assert event.event_data["message_type"] == "DOCUMENT"
    assert event.event_data["media_id"] == "media-id-123"
    assert event.event_data["media_url"] is None

def test_store_inbound_message_two_tenants_same_phone_only_matches_real_candidate(db_session, candidate_with_conversation):
    """AC-12 tenant isolation, adapted: candidateMobile is globally
    matched (this codebase has no per-tenant WhatsApp Business Account
    routing infra), but a second candidate with a DIFFERENT phone must
    never be matched by a first candidate's message."""
    candidate, conversation = candidate_with_conversation
    other = Candidate(candidateID="C-200", candidateEmail="other@example.com", candidatePassword="h", candidateMobile="+19995551111")
    db_session.add(other)
    db_session.commit()

    message = {"id": "wamid.T1", "from": "12025551234", "timestamp": "1721740800", "type": "text", "text": {"body": "hi"}}
    result = svc.store_inbound_whatsapp_message(db_session, message)
    assert result["candidate_id"] == "C-100"

# ---------------------------------------------------------------------------
# Delivery status updates (AC-7, AC-8)
# ---------------------------------------------------------------------------

def test_process_delivery_status_updates_matching_sent_event(db_session, candidate_with_conversation):
    candidate, conversation = candidate_with_conversation
    sent_event = ConversationEvent(
        conversation_id=conversation.id, event_type="ai_message_sent",
        event_data={"channel": "whatsapp", "body": "Thanks!", "whatsapp_message_id": "wamid.SENT1", "delivered": True},
        triggered_by="ai_agent",
    )
    db_session.add(sent_event)
    db_session.commit()

    result = svc.process_delivery_status(db_session, {"id": "wamid.SENT1", "status": "delivered"})
    assert result["status"] == "updated"

    db_session.refresh(sent_event)
    assert sent_event.event_data["delivery_status"] == "DELIVERED"

def test_process_delivery_status_unknown_message_logged_not_crashed(db_session, candidate_with_conversation):
    result = svc.process_delivery_status(db_session, {"id": "wamid.NEVER-SENT", "status": "delivered"})
    assert result["status"] == "unknown_message"

def test_process_delivery_status_unrecognized_status_ignored(db_session, candidate_with_conversation):
    result = svc.process_delivery_status(db_session, {"id": "wamid.X", "status": "some_unknown_status"})
    assert result["status"] == "ignored"
