"""
import logging
S-054/HRMS-0454 -- Offer Release Notification via Thunder.

Real architecture under test (see offer_release_notification_service
module docstring): reuses the pre-existing OfferLetter model (no new
`offers` table); salary is already a display string (BR-03 moot);
portal link reuses S-017's generate_portal_link_url(); no OFFER_SENT
state -- logged as a real OFFER_RELEASED ConversationEvent;
offer_faq_active flag set for real.

Throwaway SQLite -- never the real database. Throwaway JWT keys for
generate_portal_link_url()'s real create_access_token() call.
"""
import os
import tempfile
from datetime import date
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.security as security
from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.consent import ConsentRecord
from app.models.offer_letter import OfferLetter
from app.models.user import Users

import app.services.offer_release_notification_service as svc


@pytest.fixture(autouse=True)
def _throwaway_jwt_keys(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption()).decode()
    public_pem = key.public_key().public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    monkeypatch.setattr(security, "PRIVATE_KEY", private_pem)
    monkeypatch.setattr(security, "PUBLIC_KEY", public_pem)


@pytest.fixture(autouse=True)
def _fake_whatsapp_number(monkeypatch):
    import app.services.whatsapp_routing_service as wr_svc
    monkeypatch.setattr(wr_svc, "DEFAULT_WHATSAPP_NUMBER", "+15550009999")


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        OfferLetter.__table__, ConsentRecord.__table__,
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
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h", tenant_id=None)
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya", candidateMobile="+919876543210")
    db_session.add_all([owner, candidate])
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp")
    db_session.add(conv)
    db_session.add(ConsentRecord(subject_type="candidate", subject_id="C-1", consent_type="whatsapp_outreach", consent_given=True, captured_by="candidate_self_service"))
    db_session.commit()

    offer = OfferLetter(
        candidate_id="C-1", position="Sr. Guidewire Developer", salary="24 LPA",
        joining_date=date(2026, 9, 1), offer_expire_date=date(2026, 8, 20),
        offer_status="Released", approval_status="Approved", released_by="U-ORG",
        download_url="https://sharepoint.example.com/offer.pdf",
    )
    db_session.add(offer)
    db_session.commit()

    return candidate, conv, offer


def test_sends_both_whatsapp_and_email_with_offer_details(db_session, seeded):
    candidate, conv, offer = seeded

    with patch.object(svc.EmailService, "send_email", return_value={"status": "success"}) as mock_send:
        result = svc.send_offer_release_notification(db_session, offer)

    assert result["whatsapp_sent"] is True
    assert result["email_sent"] is True
    mock_send.assert_called_once()

    # Email body includes salary, position, and a portal link/button.
    _, kwargs = mock_send.call_args
    body = kwargs.get("body_content", "")
    assert "24 LPA" in body
    assert "Sr. Guidewire Developer" in body
    assert "/candidate/" in body
    assert "https://sharepoint.example.com/offer.pdf" in body


def test_whatsapp_message_includes_salary_and_portal_link(db_session, seeded):
    candidate, conv, offer = seeded

    with patch.object(svc.EmailService, "send_email", return_value={"status": "success"}):
        svc.send_offer_release_notification(db_session, offer)

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id).all()
    whatsapp_bodies = [e.event_data.get("body", "") for e in events if e.event_data and e.event_data.get("channel") != "email" and "body" in e.event_data]
    assert any("24 LPA" in b and "/candidate/" in b for b in whatsapp_bodies)


def test_logs_offer_released_event_and_sets_faq_flag(db_session, seeded):
    candidate, conv, offer = seeded

    with patch.object(svc.EmailService, "send_email", return_value={"status": "success"}):
        svc.send_offer_release_notification(db_session, offer)

    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "OFFER_RELEASED").first()
    assert event is not None
    assert event.event_data["offer_id"] == offer.id

    db_session.refresh(conv)
    assert conv.offer_faq_active is True


def test_both_channels_failing_logs_offer_email_failed(db_session, seeded):
    candidate, conv, offer = seeded
    conv.owner_type = "hr_user"  # blocks WhatsApp via R-08
    conv.owner_id = "U-RECRUITER"
    db_session.commit()

    with patch.object(svc.EmailService, "send_email", side_effect=RuntimeError("simulated outage")):
        result = svc.send_offer_release_notification(db_session, offer)

    assert result["whatsapp_sent"] is False
    assert result["email_sent"] is False

    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "OFFER_EMAIL_FAILED").first()
    assert event is not None


def test_email_only_failure_does_not_log_offer_email_failed(db_session, seeded):
    """BR-02's own integrations note: only a BOTH-channel failure is
    the real escalation case -- a WhatsApp success + email failure is
    not itself OFFER_EMAIL_FAILED."""
    candidate, conv, offer = seeded

    with patch.object(svc.EmailService, "send_email", side_effect=RuntimeError("simulated outage")):
        result = svc.send_offer_release_notification(db_session, offer)

    assert result["whatsapp_sent"] is True
    assert result["email_sent"] is False

    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "OFFER_EMAIL_FAILED").first()
    assert event is None


def test_no_candidate_found_never_raises(db_session, seeded):
    candidate, conv, offer = seeded
    offer.candidate_id = "NOPE"
    db_session.commit()

    result = svc.send_offer_release_notification(db_session, offer)  # should not raise
    assert result == {"whatsapp_sent": False, "email_sent": False}
