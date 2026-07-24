"""
S-020/HRMS-0420 -- Engagement SLA Monitoring.

Real architecture adaptations under test (see sla_monitoring_service
module docstring): BR-01's QUALIFYING/QUALIFIED map onto the real
"open"/"awaiting_candidate" statuses; BR-02 auto-resolve happens via
re-evaluation on every job tick rather than hooking into every
outbound-send code path.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.notification import Notification
from app.models.sla_breach import CandidateSLABreach
from app.models.user import Users

import app.services.sla_monitoring_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        CandidateSLABreach.__table__, CandidateAIAssignment.__table__, Notification.__table__,
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
    db_session.add(owner)
    db_session.commit()

    c1 = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    c2 = Candidate(candidateID="C-2", candidateEmail="c2@example.com", candidatePassword="h", candidateFirstName="Raj")
    c3 = Candidate(candidateID="C-3", candidateEmail="c3@example.com", candidatePassword="h", candidateFirstName="Anita")
    db_session.add_all([c1, c2, c3])
    db_session.commit()

    stale_conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="awaiting_candidate", owner_type="ai_agent", owner_id="thunder")
    fresh_conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-2", status="open", owner_type="ai_agent", owner_id="thunder")
    closed_conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-3", status="closed", owner_type="ai_agent", owner_id="thunder")
    db_session.add_all([stale_conv, fresh_conv, closed_conv])
    db_session.commit()

    stale_conv.updated_at = datetime.utcnow() - timedelta(hours=25)
    closed_conv.updated_at = datetime.utcnow() - timedelta(hours=25)
    db_session.commit()

    return stale_conv, fresh_conv, closed_conv


def test_creates_breach_for_stale_monitored_conversation(db_session, seeded):
    stale_conv, fresh_conv, closed_conv = seeded
    result = svc.detect_and_resolve_no_contact_breaches(db_session, tenant_id="U-ORG")

    assert result["created"] == 1
    breaches = db_session.query(CandidateSLABreach).filter(CandidateSLABreach.conversation_id == stale_conv.id).all()
    assert len(breaches) == 1
    assert breaches[0].sla_type == "NO_CONTACT"
    assert breaches[0].is_resolved is False


def test_no_breach_for_fresh_conversation(db_session, seeded):
    stale_conv, fresh_conv, closed_conv = seeded
    svc.detect_and_resolve_no_contact_breaches(db_session, tenant_id="U-ORG")

    breaches = db_session.query(CandidateSLABreach).filter(CandidateSLABreach.conversation_id == fresh_conv.id).all()
    assert breaches == []


def test_br01_excludes_closed_conversations_even_if_stale(db_session, seeded):
    stale_conv, fresh_conv, closed_conv = seeded
    svc.detect_and_resolve_no_contact_breaches(db_session, tenant_id="U-ORG")

    breaches = db_session.query(CandidateSLABreach).filter(CandidateSLABreach.conversation_id == closed_conv.id).all()
    assert breaches == []  # BR-01: closed is not a monitored status


def test_second_run_does_not_duplicate_active_breach(db_session, seeded):
    stale_conv, fresh_conv, closed_conv = seeded
    svc.detect_and_resolve_no_contact_breaches(db_session, tenant_id="U-ORG")
    result2 = svc.detect_and_resolve_no_contact_breaches(db_session, tenant_id="U-ORG")

    assert result2["created"] == 0
    breaches = db_session.query(CandidateSLABreach).filter(CandidateSLABreach.conversation_id == stale_conv.id).all()
    assert len(breaches) == 1


def test_br02_breach_auto_resolves_when_conversation_gets_fresh_again(db_session, seeded):
    stale_conv, fresh_conv, closed_conv = seeded
    svc.detect_and_resolve_no_contact_breaches(db_session, tenant_id="U-ORG")

    # Simulate a new outbound message being sent -- updated_at moves forward.
    stale_conv.updated_at = datetime.utcnow()
    db_session.commit()

    result2 = svc.detect_and_resolve_no_contact_breaches(db_session, tenant_id="U-ORG")
    assert result2["resolved"] == 1

    breach = db_session.query(CandidateSLABreach).filter(CandidateSLABreach.conversation_id == stale_conv.id).first()
    assert breach.is_resolved is True
    assert breach.resolved_at is not None


def test_get_active_breaches_returns_oldest_first_with_hours_since(db_session, seeded):
    stale_conv, fresh_conv, closed_conv = seeded
    svc.detect_and_resolve_no_contact_breaches(db_session, tenant_id="U-ORG")

    active = svc.get_active_breaches(db_session, "U-ORG")
    assert len(active) == 1
    assert active[0]["candidate_id"] == "C-1"
    assert active[0]["candidate_name"] == "Priya"
    assert active[0]["hours_since_breach"] >= 0


def test_get_active_breaches_excludes_resolved(db_session, seeded):
    stale_conv, fresh_conv, closed_conv = seeded
    svc.detect_and_resolve_no_contact_breaches(db_session, tenant_id="U-ORG")
    stale_conv.updated_at = datetime.utcnow()
    db_session.commit()
    svc.detect_and_resolve_no_contact_breaches(db_session, tenant_id="U-ORG")

    active = svc.get_active_breaches(db_session, "U-ORG")
    assert active == []


def test_get_active_no_contact_breach_for_conversation(db_session, seeded):
    stale_conv, fresh_conv, closed_conv = seeded
    svc.detect_and_resolve_no_contact_breaches(db_session, tenant_id="U-ORG")

    breach = svc.get_active_no_contact_breach_for_conversation(db_session, stale_conv.id)
    assert breach is not None
    assert breach.sla_type == "NO_CONTACT"

    no_breach = svc.get_active_no_contact_breach_for_conversation(db_session, fresh_conv.id)
    assert no_breach is None


def test_breach_creates_conversation_event(db_session, seeded):
    stale_conv, fresh_conv, closed_conv = seeded
    svc.detect_and_resolve_no_contact_breaches(db_session, tenant_id="U-ORG")

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == stale_conv.id, ConversationEvent.event_type == "sla_breach_detected").all()
    assert len(events) == 1
