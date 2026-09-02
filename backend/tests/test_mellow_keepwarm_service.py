"""
Mellow keep-warm outreach -- the ENGAGED/QUALIFYING/SCREENED cadence
tier of the real stage-aware cadence reconciliation
import logging
([[wros_outreach_cadence_by_stage_backlog]]).

Proves: only pre-interview-stage candidates are nudged, both channels
fire (WhatsApp AND email, not either/or -- the multichannel merge),
not-yet-due candidates are skipped, and a failed WhatsApp leg (e.g.
recruiter owns the conversation) doesn't block the independent email
leg.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.consent import ConsentRecord
from app.models.user import Users

import app.services.mellow_keepwarm_service as svc


@pytest.fixture(autouse=True)
def _fake_whatsapp_number(monkeypatch):
    import app.services.whatsapp_routing_service as wr_svc
    monkeypatch.setattr(wr_svc, "DEFAULT_WHATSAPP_NUMBER", "+15550009999")


@pytest.fixture(autouse=True)
def _no_real_email(monkeypatch):
    monkeypatch.setattr("app.services.email_service.EmailService.send_email", lambda *a, **kw: {"status": "sent"})


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        ConsentRecord.__table__, CandidateGhostingStatus.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _seed(db, *, stage="ENGAGED"):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h", ai_agent_name="Thunder")
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya", candidateMobile="+919876543210")
    db.add_all([owner, candidate])
    db.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp")
    db.add(conv)
    db.add(ConsentRecord(subject_type="candidate", subject_id="C-1", consent_type="whatsapp_outreach", consent_given=True, captured_by="candidate_self_service"))
    db.commit()
    return candidate, conv


@pytest.fixture()
def mocked_stage():
    def _mock(stage):
        return patch("app.services.candidate_journey_service.get_candidate_journey", lambda *a, **kw: {"current_stage": stage})
    return _mock


def test_nudges_pre_interview_candidate_never_nudged_before(db_session, mocked_stage):
    candidate, conv = _seed(db_session)
    with mocked_stage("ENGAGED"), patch("app.services.thunder_service.send_thunder_message") as mock_send:
        result = svc.run_mellow_keepwarm_job(db_session)

    assert result["nudged"] == 1
    assert mock_send.called
    events = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "MELLOW_KEEPWARM_SENT").all()
    assert len(events) == 1


def test_skips_interview_stage_candidate(db_session, mocked_stage):
    candidate, conv = _seed(db_session)
    with mocked_stage("INTERVIEW"), patch("app.services.thunder_service.send_thunder_message") as mock_send:
        result = svc.run_mellow_keepwarm_job(db_session)

    assert result["nudged"] == 0
    assert not mock_send.called


def test_skips_when_nudged_recently(db_session, mocked_stage):
    candidate, conv = _seed(db_session)
    db_session.add(ConversationEvent(
        conversation_id=conv.id, event_type="ai_message_sent",
        event_data={}, triggered_by="ai_agent", created_at=datetime.utcnow() - timedelta(days=1),
    ))
    db_session.commit()

    with mocked_stage("ENGAGED"), patch("app.services.thunder_service.send_thunder_message") as mock_send:
        result = svc.run_mellow_keepwarm_job(db_session)

    assert result["nudged"] == 0
    assert not mock_send.called


def test_due_again_after_interval_elapsed(db_session, mocked_stage):
    candidate, conv = _seed(db_session)
    db_session.add(ConversationEvent(
        conversation_id=conv.id, event_type="ai_message_sent",
        event_data={}, triggered_by="ai_agent", created_at=datetime.utcnow() - timedelta(days=10),
    ))
    db_session.commit()

    with mocked_stage("ENGAGED"), patch("app.services.thunder_service.send_thunder_message") as mock_send:
        result = svc.run_mellow_keepwarm_job(db_session)

    assert result["nudged"] == 1
    assert mock_send.called


def test_email_leg_independent_of_failed_whatsapp_leg(db_session, mocked_stage):
    from app.services.thunder_service import ConversationOwnedByHuman

    candidate, conv = _seed(db_session)
    with mocked_stage("ENGAGED"), \
         patch("app.services.thunder_service.send_thunder_message", side_effect=ConversationOwnedByHuman("owned")), \
         patch("app.services.email_service.EmailService.send_email") as mock_email:
        result = svc.run_mellow_keepwarm_job(db_session)

    assert result["nudged"] == 1  # email leg still counts as a real nudge
    assert mock_email.called
