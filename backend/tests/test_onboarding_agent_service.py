"""
import logging
S-067/HRMS-0467 -- Onboarding Agent.

Real architecture under test (see onboarding_agent_service module
docstring): built standalone, its own scheduled job -- not dispatched
by a fictional Supervisor sub-agent loop, per Avinash's explicit
direction. "PREBOARDING" = OfferLetter.offer_status == "Accepted",
same real substitute S-057/S-058/S-059 already established. D+1 is
scheduled only at completion-detection time (see preboarding_
touchpoint.py's own module docstring) -- its presence is the real
idempotency guard against double HR-notify / double onboarding.complete.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_joining_score import CandidateJoiningScore
from app.models.consent import ConsentRecord
from app.models.employee import Employee
from app.models.event_log import EventLog
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.preboarding_touchpoint import PreboardingTouchpoint
from app.models.submission import Submission
from app.models.user import Users, Jobs

import app.services.onboarding_agent_service as svc

@pytest.fixture(autouse=True)
def _fake_whatsapp_number(monkeypatch):
    """whatsapp_routing_service.DEFAULT_WHATSAPP_NUMBER is captured once
    at import time from THUNDER_WHATSAPP_NUMBER -- real value depends on
    env state, which is unreliable across a combined test run (same
    precedent as test_follow_up_scheduler_service.py's own fix for
    this). Every test here that reaches the real whatsapp send path
    needs a number to send from."""
    import app.services.whatsapp_routing_service as wr_svc
    monkeypatch.setattr(wr_svc, "DEFAULT_WHATSAPP_NUMBER", "+15550009999")

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Jobs.__table__, Candidate.__table__, CandidateInfoForm.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, OfferLetter.__table__,
        PreboardingDocument.__table__, PreboardingTouchpoint.__table__, Employee.__table__,
        CandidateJobScore.__table__, CandidateJoiningScore.__table__, Submission.__table__, EventLog.__table__,
        ConsentRecord.__table__,
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
    db_session.add(Users(UserID="U-ORG", UserRole="Super User", UserEmail="org@blitzenx.com", UserPassword="h", thunder_enabled=True))
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    db_session.add(candidate)
    db_session.commit()
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp")
    db_session.add(conv)
    offer = OfferLetter(candidate_id="C-1", position="SDET", salary="100000", joining_date=date.today() + timedelta(days=10), offer_expire_date=date.today() + timedelta(days=30), offer_status="Accepted")
    db_session.add(offer)
    db_session.add(ConsentRecord(subject_type="candidate", subject_id="C-1", consent_type="whatsapp_outreach", consent_given=True, captured_by="candidate_self_service"))
    db_session.commit()
    return candidate, conv, offer

def test_schedule_onboarding_touchpoints_creates_d7_d3_d1(db_session, seeded):
    candidate, _, offer = seeded
    rows = svc.schedule_onboarding_touchpoints(db_session, candidate, offer, "U-ORG")
    assert len(rows) == 3
    types = {r.touchpoint_type for r in rows}
    assert types == {"D7", "D3", "D1"}

    d7 = next(r for r in rows if r.touchpoint_type == "D7")
    assert d7.scheduled_at.date() == offer.joining_date - timedelta(days=7)
    assert d7.status == "PENDING"

def test_schedule_is_idempotent(db_session, seeded):
    candidate, _, offer = seeded
    svc.schedule_onboarding_touchpoints(db_session, candidate, offer, "U-ORG")
    second = svc.schedule_onboarding_touchpoints(db_session, candidate, offer, "U-ORG")
    assert second == []
    assert db_session.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.offer_id == offer.id).count() == 3

def test_schedule_skips_offer_with_no_joining_date(db_session, seeded):
    """joining_date is NOT NULL at the DB level (never actually
    reachable via a persisted row) -- this exercises the function's
    own defensive guard directly against an in-memory, uncommitted
    OfferLetter, the same way a caller could hand it a stale/partial
    object."""
    candidate, _, offer = seeded
    unsaved_offer = OfferLetter(id=999, candidate_id="C-1", position="SDET", salary="100000", joining_date=None, offer_expire_date=date.today() + timedelta(days=30), offer_status="Accepted")
    rows = svc.schedule_onboarding_touchpoints(db_session, candidate, unsaved_offer, "U-ORG")
    assert rows == []

def test_cancel_pending_touchpoints_br01(db_session, seeded):
    candidate, _, offer = seeded
    svc.schedule_onboarding_touchpoints(db_session, candidate, offer, "U-ORG")
    cancelled = svc.cancel_pending_touchpoints_for_candidate(db_session, "C-1")
    assert cancelled == 3
    rows = db_session.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.candidate_id == "C-1").all()
    assert all(r.status == "CANCELLED" for r in rows)

def test_d7_message_mentions_documents_when_pending_br02(db_session, seeded):
    candidate, _, offer = seeded
    db_session.add(PreboardingDocument(tenant_id="U-ORG", candidate_id="C-1", offer_id=offer.id, document_type="RESUME", document_label="Resume", status="PENDING"))
    db_session.commit()
    message = svc._build_message("D7", candidate, offer, db_session)
    assert "still waiting on a few documents" in message

def test_d7_message_omits_documents_line_when_all_received_br02(db_session, seeded):
    candidate, _, offer = seeded
    db_session.add(PreboardingDocument(tenant_id="U-ORG", candidate_id="C-1", offer_id=offer.id, document_type="RESUME", document_label="Resume", status="RECEIVED"))
    db_session.commit()
    message = svc._build_message("D7", candidate, offer, db_session)
    assert "still waiting on a few documents" not in message

def test_run_job_sends_due_touchpoint_and_marks_sent(db_session, seeded):
    candidate, _, offer = seeded
    svc.schedule_onboarding_touchpoints(db_session, candidate, offer, "U-ORG")
    d7 = db_session.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.touchpoint_type == "D7").first()
    d7.scheduled_at = datetime.utcnow() - timedelta(minutes=5)  # make it due
    db_session.commit()

    result = svc.run_onboarding_touchpoint_job(db_session)
    db_session.refresh(d7)
    assert result["sent"] >= 1
    assert d7.status == "SENT"
    assert d7.sent_at is not None

def test_run_job_skips_not_yet_due_touchpoints(db_session, seeded):
    candidate, _, offer = seeded
    svc.schedule_onboarding_touchpoints(db_session, candidate, offer, "U-ORG")  # all in the future
    result = svc.run_onboarding_touchpoint_job(db_session)
    assert result["processed"] == 0

def test_run_job_cancels_touchpoints_for_no_longer_accepted_offer(db_session, seeded):
    candidate, _, offer = seeded
    svc.schedule_onboarding_touchpoints(db_session, candidate, offer, "U-ORG")
    offer.offer_status = "Rejected"
    d7 = db_session.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.touchpoint_type == "D7").first()
    d7.scheduled_at = datetime.utcnow() - timedelta(minutes=5)
    db_session.commit()

    result = svc.run_onboarding_touchpoint_job(db_session)
    db_session.refresh(d7)
    assert d7.status == "CANCELLED"
    assert result["cancelled"] >= 1

def test_check_onboarding_completion_false_when_documents_pending(db_session, seeded):
    candidate, _, offer = seeded
    svc.schedule_onboarding_touchpoints(db_session, candidate, offer, "U-ORG")
    for t in db_session.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.offer_id == offer.id).all():
        t.status = "SENT"
    db_session.add(PreboardingDocument(tenant_id="U-ORG", candidate_id="C-1", offer_id=offer.id, document_type="RESUME", document_label="Resume", status="PENDING"))
    db_session.commit()

    assert svc.check_onboarding_completion(db_session, "C-1", offer.id, "U-ORG") is False

def test_check_onboarding_completion_true_schedules_d_plus_1_notifies_and_emits(db_session, seeded):
    candidate, _, offer = seeded
    svc.schedule_onboarding_touchpoints(db_session, candidate, offer, "U-ORG")
    for t in db_session.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.offer_id == offer.id).all():
        t.status = "SENT"
    db_session.commit()

    result = svc.check_onboarding_completion(db_session, "C-1", offer.id, "U-ORG")
    assert result is True

    d_plus_1 = db_session.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.offer_id == offer.id, PreboardingTouchpoint.touchpoint_type == "D_PLUS_1").first()
    assert d_plus_1 is not None
    assert d_plus_1.status == "PENDING"

    events = db_session.query(EventLog).filter(EventLog.event_type == "onboarding.complete").all()
    assert len(events) == 1
    assert events[0].candidate_id == "C-1"

def test_check_onboarding_completion_idempotent_br03(db_session, seeded):
    """BR-03: never emits/notifies twice -- D_PLUS_1's presence is the guard."""
    candidate, _, offer = seeded
    svc.schedule_onboarding_touchpoints(db_session, candidate, offer, "U-ORG")
    for t in db_session.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.offer_id == offer.id).all():
        t.status = "SENT"
    db_session.commit()

    assert svc.check_onboarding_completion(db_session, "C-1", offer.id, "U-ORG") is True
    assert svc.check_onboarding_completion(db_session, "C-1", offer.id, "U-ORG") is False  # already completed

    events = db_session.query(EventLog).filter(EventLog.event_type == "onboarding.complete").all()
    assert len(events) == 1  # not doubled

def test_d_plus_1_only_sent_after_employee_record_exists(db_session, seeded):
    candidate, _, offer = seeded
    svc.schedule_onboarding_touchpoints(db_session, candidate, offer, "U-ORG")
    for t in db_session.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.offer_id == offer.id).all():
        t.status = "SENT"
    db_session.commit()
    svc.check_onboarding_completion(db_session, "C-1", offer.id, "U-ORG")

    d_plus_1 = db_session.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.offer_id == offer.id, PreboardingTouchpoint.touchpoint_type == "D_PLUS_1").first()
    d_plus_1.scheduled_at = datetime.utcnow() - timedelta(minutes=5)
    db_session.commit()

    result = svc.run_onboarding_touchpoint_job(db_session)
    db_session.refresh(d_plus_1)
    assert d_plus_1.status == "PENDING"  # no Employee record yet -- skipped, not sent
    assert result["skipped"] >= 1

    db_session.add(Employee(candidate_id="C-1", first_name="Priya", last_name="K", email="priya.emp@example.com", joining_date=offer.joining_date))
    db_session.commit()

    svc.run_onboarding_touchpoint_job(db_session)
    db_session.refresh(d_plus_1)
    assert d_plus_1.status == "SENT"
