"""
S-075/HRMS-0475 -- AI Recruiter Pause & Resume Controls.

Real architecture under test (see thunder_pause_service module
docstring): no HRMS-0466 Supervisor Agent dispatch loop exists in this
codebase (separate, deferred story) -- pause enforcement is wired
directly into thunder_service.send_thunder_message() /
send_outbound_campaign_message(), the real choke points every
autonomous Thunder send already goes through. This test module covers
the pause primitives themselves (pause/resume/expiry/global-precedence)
plus the choke-point wiring in send_thunder_message().

"""
import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.consent import ConsentRecord
from app.models.user import Users

import app.services.thunder_pause_service as svc

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
def seeded(db_session):
    db_session.add(Users(UserID="U-ORG", UserRole="Super User", UserEmail="org@blitzenx.com", UserPassword="h", tenant_id=None, thunder_enabled=True))
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    db_session.add(candidate)
    db_session.commit()
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="web_chat")
    db_session.add(conv)
    db_session.commit()
    return candidate, conv

def test_not_paused_by_default(db_session, seeded):
    _, conv = seeded
    assert svc.is_thunder_paused_for_conversation(db_session, conv) is False
    svc.raise_if_thunder_paused(db_session, conv)  # must not raise

def test_pause_thunder_sets_flags_without_touching_ownership(db_session, seeded):
    _, conv = seeded
    resume_at = datetime.utcnow() + timedelta(hours=24)
    svc.pause_thunder(db_session, conv, paused_by="U-HR", resume_at=resume_at)
    db_session.commit()

    assert conv.is_thunder_paused is True
    assert conv.thunder_resume_at == resume_at
    assert conv.thunder_paused_by == "U-HR"
    # BR-01: pause is independent of ownership.
    assert conv.owner_type == "ai_agent"
    assert conv.owner_id == "Thunder"

def test_paused_conversation_raises(db_session, seeded):
    _, conv = seeded
    svc.pause_thunder(db_session, conv, paused_by="U-HR")
    db_session.commit()
    assert svc.is_thunder_paused_for_conversation(db_session, conv) is True
    with pytest.raises(svc.ThunderPausedError):
        svc.raise_if_thunder_paused(db_session, conv)

def test_resume_thunder_clears_pause_and_resume_at(db_session, seeded):
    _, conv = seeded
    svc.pause_thunder(db_session, conv, paused_by="U-HR", resume_at=datetime.utcnow() + timedelta(hours=1))
    db_session.commit()
    svc.resume_thunder(db_session, conv)
    db_session.commit()
    assert conv.is_thunder_paused is False
    assert conv.thunder_resume_at is None

def test_global_tenant_pause_takes_precedence_br03(db_session, seeded):
    """BR-03: global pause blocks sends even when the conversation's own
    is_thunder_paused is False."""
    _, conv = seeded
    tenant = db_session.query(Users).filter(Users.UserID == "U-ORG").first()
    tenant.thunder_enabled = False
    db_session.commit()

    assert conv.is_thunder_paused is False  # per-candidate flag untouched
    assert svc.is_thunder_paused_for_conversation(db_session, conv) is True

def test_run_pause_expiry_job_auto_resumes_and_logs_event(db_session, seeded):
    _, conv = seeded
    svc.pause_thunder(db_session, conv, paused_by="U-HR", resume_at=datetime.utcnow() - timedelta(minutes=1))
    db_session.commit()

    result = svc.run_pause_expiry_job(db_session)
    db_session.refresh(conv)

    assert result["resumed"] == 1
    assert conv.is_thunder_paused is False
    assert conv.thunder_resume_at is None

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id).all()
    assert any(e.event_type == "THUNDER_AUTO_RESUMED" for e in events)

def test_run_pause_expiry_job_ignores_not_yet_due_or_manual_pauses(db_session, seeded):
    _, conv = seeded
    # Future resume_at -- not due yet.
    svc.pause_thunder(db_session, conv, paused_by="U-HR", resume_at=datetime.utcnow() + timedelta(hours=1))
    db_session.commit()
    result = svc.run_pause_expiry_job(db_session)
    db_session.refresh(conv)
    assert result["resumed"] == 0
    assert conv.is_thunder_paused is True

    # "Until manually resumed" (resume_at=None) -- never auto-resumed.
    svc.pause_thunder(db_session, conv, paused_by="U-HR", resume_at=None)
    db_session.commit()
    result = svc.run_pause_expiry_job(db_session)
    db_session.refresh(conv)
    assert result["resumed"] == 0
    assert conv.is_thunder_paused is True

def test_send_thunder_message_blocked_when_paused(db_session, seeded):
    """The real choke point (thunder_service.send_thunder_message)
    raises ThunderPausedError before it ever reaches consent/debounce/
    ownership checks."""
    from app.services.thunder_service import send_thunder_message, ThunderPausedError as ReExportedError

    candidate, conv = seeded
    svc.pause_thunder(db_session, conv, paused_by="U-HR")
    db_session.commit()

    assert ReExportedError is svc.ThunderPausedError
    with pytest.raises(svc.ThunderPausedError):
        send_thunder_message(db_session, conv, candidate, "Hi there", sender_type="ai_agent", channel="web_chat")

def test_send_thunder_message_blocked_when_globally_disabled(db_session, seeded):
    from app.services.thunder_service import send_thunder_message

    candidate, conv = seeded
    tenant = db_session.query(Users).filter(Users.UserID == "U-ORG").first()
    tenant.thunder_enabled = False
    db_session.commit()

    with pytest.raises(svc.ThunderPausedError):
        send_thunder_message(db_session, conv, candidate, "Hi there", sender_type="ai_agent", channel="web_chat")
