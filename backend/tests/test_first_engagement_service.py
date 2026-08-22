"""
S-012/HRMS-0412 -- WhatsApp First Engagement, 60-Second Rule.

Adapted to real architecture: no message_templates table (hardcoded
fallback IS the real template, per the spec's own sanctioned fallback
path), no per-candidate tenants row (real "tenant" is the org-owner
Users row). Uses the real R-08/consent gates via
_send_first_whatsapp_attempt(), bypassing only the 60s duplicate-body
debounce (which would otherwise block the mandated BR-04 retry).

No real WhatsApp call -- whatsapp_client is injected, same convention
as every other WhatsApp test in this codebase. _sleep is injected too,
so the BR-04 retry test doesn't actually wait 5 real seconds.

"""
import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.first_engagement_service as svc
import app.services.whatsapp_routing_service as routing
from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.consent import ConsentRecord
from app.models.message_template import MessageTemplate
from app.models.user import Users

@pytest.fixture(autouse=True)
def _default_whatsapp_number(monkeypatch):
    monkeypatch.setattr(routing, "DEFAULT_WHATSAPP_NUMBER", "+10005550000")

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

def _make_candidate_and_conversation(db, *, mobile="+19995551234", created_at=None, consent=True):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    db.add(owner)
    db.commit()

    candidate = Candidate(
        candidateID="C-100", candidateEmail="cand@example.com", candidatePassword="h",
        candidateMobile=mobile, candidateFirstName="Jordan",
        candidateCreatedAt=created_at or datetime.utcnow(),
    )
    db.add(candidate)
    db.commit()

    conversation = CandidateConversation(
        tenant_id="U-ORG", candidate_id="C-100", status="open",
        owner_type="ai_agent", owner_id="onboarding-ai",
    )
    db.add(conversation)
    db.commit()

    if consent and mobile:
        db.add(ConsentRecord(subject_type="candidate", subject_id="C-100", consent_type="whatsapp_outreach", consent_given=True, captured_by="test"))
        db.commit()

    return candidate, conversation

def _no_sleep(seconds):
    pass

def test_no_phone_skips_gracefully(db_session):
    candidate, conversation = _make_candidate_and_conversation(db_session, mobile=None, consent=False)
    result = svc.send_first_whatsapp_engagement(db_session, "C-100", "U-ORG", _sleep=_no_sleep)
    assert result["status"] == "skipped"
    assert result["reason"] == "NO_PHONE"

def test_successful_send_within_sla(db_session):
    _make_candidate_and_conversation(db_session)
    result = svc.send_first_whatsapp_engagement(
        db_session, "C-100", "U-ORG", whatsapp_client=lambda *a: True, _sleep=_no_sleep,
    )
    assert result["status"] == "sent"
    assert result["sla_met"] is True

    sent_event = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "FIRST_WHATSAPP_SENT").first()
    assert sent_event is not None
    sla_event = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "SLA_MET").first()
    assert sla_event is not None

    msg_event = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "ai_message_sent").first()
    assert "Jordan" in msg_event.event_data["body"]
    assert "Thunder" in msg_event.event_data["body"]
    assert "BlitzenX" in msg_event.event_data["body"]
    assert "{" not in msg_event.event_data["body"]

def test_sla_breach_logged_when_over_60_seconds(db_session):
    old_created_at = datetime.utcnow() - timedelta(seconds=120)
    _make_candidate_and_conversation(db_session, created_at=old_created_at)

    result = svc.send_first_whatsapp_engagement(
        db_session, "C-100", "U-ORG", whatsapp_client=lambda *a: True, _sleep=_no_sleep,
    )
    assert result["sla_met"] is False
    breach_event = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "SLA_BREACH").first()
    assert breach_event is not None
    assert breach_event.event_data["elapsed_seconds"] > 60

def test_idempotent_second_trigger_is_prevented(db_session):
    _make_candidate_and_conversation(db_session)
    svc.send_first_whatsapp_engagement(db_session, "C-100", "U-ORG", whatsapp_client=lambda *a: True, _sleep=_no_sleep)

    result = svc.send_first_whatsapp_engagement(db_session, "C-100", "U-ORG", whatsapp_client=lambda *a: True, _sleep=_no_sleep)
    assert result["status"] == "duplicate_prevented"

    sent_events = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "FIRST_WHATSAPP_SENT").all()
    assert len(sent_events) == 1

def test_retry_once_then_succeed(db_session):
    _make_candidate_and_conversation(db_session)
    attempts = {"count": 0}

    def flaky_client(*args):
        attempts["count"] += 1
        return attempts["count"] >= 2  # fails first attempt, succeeds on retry

    result = svc.send_first_whatsapp_engagement(db_session, "C-100", "U-ORG", whatsapp_client=flaky_client, _sleep=_no_sleep)
    assert result["status"] == "sent"
    assert attempts["count"] == 2

def test_both_attempts_fail_emits_failure_event_no_crash(db_session):
    _make_candidate_and_conversation(db_session)
    result = svc.send_first_whatsapp_engagement(db_session, "C-100", "U-ORG", whatsapp_client=lambda *a: False, _sleep=_no_sleep)

    assert result["status"] == "failed"
    assert result["reason"] == "API_FAILURE"
    failure_event = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "FIRST_WHATSAPP_FAILED").first()
    assert failure_event is not None

    # Never more than 2 real send attempts.
    sent_attempts = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "ai_message_sent").count()
    assert sent_attempts == 2

def test_no_consent_raises_and_logs_send_blocked(db_session):
    _make_candidate_and_conversation(db_session, consent=False)
    with pytest.raises(svc.FirstEngagementFailed):
        svc.send_first_whatsapp_engagement(db_session, "C-100", "U-ORG", whatsapp_client=lambda *a: True, _sleep=_no_sleep)

    failure_event = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "FIRST_ENGAGEMENT_FAILED").first()
    assert failure_event is not None

def test_render_greeting_never_leaves_unreplaced_placeholder(db_session):
    candidate, _ = _make_candidate_and_conversation(db_session)
    rendered = svc._render_greeting(db_session, candidate, "Thunder", "U-ORG")
    assert "{" not in rendered and "}" not in rendered
    assert len(rendered) < svc.MAX_MESSAGE_LENGTH
