"""
S-056/HRMS-0456 -- Offer Acceptance Tracking.

Real architecture under test (see offer_decision_service module
docstring): reuses the pre-existing candidate_pool_service.set_org_pool()
on decline (same mechanism the already-shipped POST /offer-letter/respond
endpoint uses); introduces a new real "Countered" offer_status value
(no migration needed, plain String(30) column); BR-01 acceptance
leaves conversation.status untouched (not "completed" -- still active,
just no longer offer-FAQ mode); BR-02 decline reason is a true
one-time ask; BR-03 counter notifies the recruiter with P1 urgency and
the real offer expiry date.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateStatus
from app.models.candidate_opportunity_watch import CandidateOpportunityWatch
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_history import CandidateHistory
from app.models.candidate_ownership import CandidateOwnership
from app.models.client import Client
from app.models.consent import ConsentRecord
from app.models.demand import Demand, DemandHistory
from app.models.notification import Notification
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.preboarding_touchpoint import PreboardingTouchpoint
from app.models.submission import Submission, SubmissionViolation
from app.models.tenant import Tenant
from app.models.recruiter_intervention_queue import RecruiterInterventionQueue
from app.models.user import Users

import app.services.offer_decision_service as svc


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
        Users.__table__, Candidate.__table__, CandidateStatus.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        OfferLetter.__table__, ConsentRecord.__table__, Notification.__table__, CandidateOwnership.__table__, CandidateHistory.__table__,
        PreboardingDocument.__table__, PreboardingTouchpoint.__table__,
        Tenant.__table__, Client.__table__, Demand.__table__, DemandHistory.__table__,
        Submission.__table__, SubmissionViolation.__table__, RecruiterInterventionQueue.__table__,
        CandidateOpportunityWatch.__table__,
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
    hr_user = Users(UserID="U-HR", UserRole="HR Manager", UserEmail="hr@blitzenx.com", UserPassword="h", tenant_id=None)
    db_session.add(hr_user)
    db_session.commit()

    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya", candidateMobile="+919876543210")
    db_session.add(candidate)
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp", offer_faq_active=True)
    db_session.add(conv)
    db_session.add(ConsentRecord(subject_type="candidate", subject_id="C-1", consent_type="whatsapp_outreach", consent_given=True, captured_by="candidate_self_service"))
    db_session.commit()

    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    client = Client(tenant_id=tenant.id, company_name="Acme")
    db_session.add(client)
    db_session.commit()
    demand = Demand(tenant_id=tenant.id, client_id=client.id, job_title="Sr. Dev", required_skills="[]", min_experience_years=5.0, work_location="REMOTE", status="OPEN")
    db_session.add(demand)
    db_session.commit()
    submission = Submission(tenant_id=tenant.id, demand_id=demand.id, client_id=client.id, candidate_id="C-1", submitted_by_user_id="U-HR", status="OFFER_EXTENDED")
    db_session.add(submission)
    db_session.commit()

    offer = OfferLetter(
        candidate_id="C-1", position="Sr. Guidewire Developer", salary="24 LPA",
        joining_date=date(2026, 9, 1), offer_expire_date=date(2026, 8, 20),
        offer_status="Released", approval_status="Approved", released_by="U-HR", created_by="U-HR",
    )
    db_session.add(offer)
    db_session.commit()

    return candidate, conv, offer, submission


# ── BR-03 gate ─────────────────────────────────────────────────────────

def test_not_active_when_offer_faq_flag_false(db_session, seeded):
    candidate, conv, offer, submission = seeded
    conv.offer_faq_active = False
    db_session.commit()

    result = svc.handle_offer_decision(db_session, candidate, conv, "U-ORG", "offer_accepted", "I accept")
    assert result["outcome"] == "not_active"


def test_no_offer_found(db_session, seeded):
    candidate, conv, offer, submission = seeded
    offer.offer_status = "Pending"
    db_session.commit()

    result = svc.handle_offer_decision(db_session, candidate, conv, "U-ORG", "offer_accepted", "I accept")
    assert result["outcome"] == "no_offer_found"


# ── TC-001/AC-1: acceptance ────────────────────────────────────────────

def test_acceptance_updates_offer_and_notifies(db_session, seeded):
    candidate, conv, offer, submission = seeded

    with patch.object(svc.EmailService, "send_email", return_value={"status": "success"}):
        result = svc.handle_offer_decision(db_session, candidate, conv, "U-ORG", "offer_accepted", "I am happy to accept the offer")

    assert result["outcome"] == "accepted"

    db_session.refresh(offer)
    assert offer.offer_status == "Accepted"
    assert offer.responded_at is not None

    db_session.refresh(conv)
    assert conv.offer_faq_active is False
    assert conv.status == "open"  # BR-01: NOT completed/closed -- preboarding still needs the conversation active

    pipeline = db_session.query(CandidateStatus).filter(CandidateStatus.candidateID == "C-1").first()
    assert pipeline.piplineStatus == "Hired"

    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "OFFER_ACCEPTED").first()
    assert event is not None

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1


# ── TC-002/AC-2: decline ────────────────────────────────────────────────

def test_decline_updates_offer_transitions_pool_and_asks_reason_once(db_session, seeded):
    candidate, conv, offer, submission = seeded

    with patch.object(svc.EmailService, "send_email", return_value={"status": "success"}):
        result = svc.handle_offer_decision(db_session, candidate, conv, "U-ORG", "offer_declined", "I have decided not to join")

    assert result["outcome"] == "declined"

    db_session.refresh(offer)
    assert offer.offer_status == "Rejected"

    db_session.refresh(conv)
    assert conv.status == "closed"
    assert conv.offer_faq_active is False

    pipeline = db_session.query(CandidateStatus).filter(CandidateStatus.candidateID == "C-1").first()
    assert pipeline.piplineStatus == "Rejected"

    ownership = db_session.query(CandidateOwnership).filter(CandidateOwnership.candidateID == "C-1").first()
    assert ownership is not None  # real Org Pool transition happened

    ask_event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "DECLINE_REASON_REQUESTED").first()
    assert ask_event is not None


def test_decline_reason_never_asked_twice(db_session, seeded):
    candidate, conv, offer, submission = seeded
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="DECLINE_REASON_REQUESTED", event_data={}, triggered_by="system"))
    db_session.commit()

    with patch.object(svc.EmailService, "send_email", return_value={"status": "success"}):
        svc.handle_offer_decision(db_session, candidate, conv, "U-ORG", "offer_declined", "I've decided to go elsewhere")

    ask_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "DECLINE_REASON_REQUESTED").all()
    assert len(ask_events) == 1  # not asked a second time


# ── TC-003/AC-3/BR-03: counter ──────────────────────────────────────────

def test_counter_escalates_and_notifies_recruiter_with_urgency(db_session, seeded):
    candidate, conv, offer, submission = seeded

    result = svc.handle_offer_decision(db_session, candidate, conv, "U-ORG", "offer_counter", "Could we discuss the salary?")
    assert result["outcome"] == "countered"

    db_session.refresh(offer)
    assert offer.offer_status == "Countered"
    assert offer.candidate_response == "Could we discuss the salary?"

    db_session.refresh(conv)
    assert conv.escalation_state == "escalated"
    assert conv.owner_type == "hr_user"
    assert conv.offer_faq_active is False

    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "OFFER_COUNTERED").first()
    assert event is not None

    notification = db_session.query(Notification).first()
    assert notification is not None
    assert notification.priority_tier == "P1"
    assert "2026-08-20" in notification.message


def test_never_raises_on_unexpected_error(db_session, seeded):
    candidate, conv, offer, submission = seeded

    with patch.object(svc, "_relevant_submission", side_effect=RuntimeError("boom")):
        result = svc.handle_offer_decision(db_session, candidate, conv, "U-ORG", "offer_accepted", "I accept")  # should not raise
    assert result["outcome"] == "decision_failed"
