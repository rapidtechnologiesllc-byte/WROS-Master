"""
import logging
S-057/HRMS-0457 -- Document Collection Agent.

Real architecture under test (see document_collection_service module
docstring): no offers table -- offer_id FKs the real OfferLetter.id;
no system_configuration table -- REQUIRED_DOCUMENTS is a real module
constant; BR-02's country_code has no dedicated field -- derived from
the real +91 mobile prefix / Asia/Kolkata timezone fallback; no live
document-upload trigger exists (same gap S-027 already flagged) --
mark_document_received()/classify_document_type() are real, tested,
standalone functions; BR-03's "no 4th reminder" is enforced by a real
event-presence check so HR is notified exactly once per document.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_joining_score import CandidateJoiningScore
from app.models.client import Client
from app.models.consent import ConsentRecord
from app.models.demand import Demand, DemandHistory
from app.models.notification import Notification
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.submission import Submission, SubmissionViolation
from app.models.tenant import Tenant
from app.models.recruiter_intervention_queue import RecruiterInterventionQueue
from app.models.user import Users

import app.services.document_collection_service as svc


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
        OfferLetter.__table__, PreboardingDocument.__table__, ConsentRecord.__table__, Notification.__table__,
        Tenant.__table__, Client.__table__, Demand.__table__, DemandHistory.__table__,
        Submission.__table__, SubmissionViolation.__table__, CandidateJoiningScore.__table__, RecruiterInterventionQueue.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _make_candidate(db, candidate_id="C-1", mobile="+919876543210"):
    candidate = Candidate(candidateID=candidate_id, candidateEmail=f"{candidate_id.lower()}@example.com", candidatePassword="h", candidateFirstName="Priya", candidateMobile=mobile)
    db.add(candidate)
    db.commit()
    return candidate


@pytest.fixture()
def seeded(db_session):
    hr_user = Users(UserID="U-HR", UserRole="HR Manager", UserEmail="hr@blitzenx.com", UserPassword="h", tenant_id=None)
    db_session.add(hr_user)
    db_session.commit()

    candidate = _make_candidate(db_session)

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp")
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

    offer = OfferLetter(candidate_id="C-1", position="Sr. Guidewire Developer", salary="24 LPA", joining_date=date(2026, 9, 1), offer_expire_date=date(2026, 8, 20), offer_status="Accepted", approval_status="Approved", created_by="U-HR")
    db_session.add(offer)
    db_session.commit()

    return candidate, conv, offer, submission


# ── BR-02: country-specific documents ──────────────────────────────────

def test_india_candidate_gets_pan_card_requirement(db_session, seeded):
    candidate, conv, offer, submission = seeded
    result = svc.start_document_collection(db_session, candidate, conv, offer, "U-ORG")
    assert result["outcome"] == "started"
    assert result["documents_created"] == 7  # all 7, including PAN_CARD

    doc_types = {d.document_type for d in db_session.query(PreboardingDocument).all()}
    assert "PAN_CARD" in doc_types


def test_non_india_candidate_excludes_pan_card(db_session, seeded):
    candidate, conv, offer, submission = seeded
    candidate.candidateMobile = "+14155552671"
    candidate.timezone = "America/Chicago"
    db_session.commit()

    result = svc.start_document_collection(db_session, candidate, conv, offer, "U-ORG")
    assert result["documents_created"] == 6  # PAN_CARD excluded

    doc_types = {d.document_type for d in db_session.query(PreboardingDocument).all()}
    assert "PAN_CARD" not in doc_types


# ── TC-001/AC-1,2: initial request ────────────────────────────────────

def test_start_collection_sends_initial_message_listing_all_documents(db_session, seeded):
    candidate, conv, offer, submission = seeded
    svc.start_document_collection(db_session, candidate, conv, offer, "U-ORG")

    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "ai_message_sent").first()
    assert event is not None
    assert "Government issued ID" in event.event_data["body"]
    assert "PAN Card" in event.event_data["body"]


def test_start_collection_is_idempotent(db_session, seeded):
    candidate, conv, offer, submission = seeded
    svc.start_document_collection(db_session, candidate, conv, offer, "U-ORG")
    result2 = svc.start_document_collection(db_session, candidate, conv, offer, "U-ORG")
    assert result2["outcome"] == "already_started"
    assert db_session.query(PreboardingDocument).count() == 7


# ── TC-002/AC-3,4: document received ───────────────────────────────────

def test_mark_document_received_acknowledges_and_asks_for_next(db_session, seeded):
    candidate, conv, offer, submission = seeded
    svc.start_document_collection(db_session, candidate, conv, offer, "U-ORG")

    result = svc.mark_document_received(db_session, candidate, conv, "U-ORG", "ID_PROOF", "https://sharepoint.example.com/id_proof.pdf")
    assert result["outcome"] == "received"
    assert result["all_complete"] is False

    doc = db_session.query(PreboardingDocument).filter(PreboardingDocument.document_type == "ID_PROOF").first()
    assert doc.status == "RECEIVED"
    assert doc.document_url == "https://sharepoint.example.com/id_proof.pdf"

    ack_event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "ai_message_sent").order_by(ConversationEvent.id.desc()).first()
    assert "received your" in ack_event.event_data["body"]
    assert "Next, could you share" in ack_event.event_data["body"]

    # S-058 wiring: mark_document_received() must genuinely recalculate
    # joining readiness, not silently fail (calculate_joining_readiness()
    # swallows its own exceptions, so this proves the write really landed).
    readiness = db_session.query(CandidateJoiningScore).filter(CandidateJoiningScore.candidate_id == candidate.candidateID, CandidateJoiningScore.offer_id == offer.id).first()
    assert readiness is not None
    assert readiness.score_breakdown["documents"] > 0


def test_all_documents_received_notifies_hr(db_session, seeded):
    candidate, conv, offer, submission = seeded
    svc.start_document_collection(db_session, candidate, conv, offer, "U-ORG")

    all_docs = db_session.query(PreboardingDocument).all()
    for doc in all_docs[:-1]:
        svc.mark_document_received(db_session, candidate, conv, "U-ORG", doc.document_type, "https://example.com/doc.pdf")

    last = all_docs[-1]
    result = svc.mark_document_received(db_session, candidate, conv, "U-ORG", last.document_type, "https://example.com/last.pdf")
    assert result["all_complete"] is True

    # S-058 wiring recalculates readiness on every document received, so
    # early in this sequence (most documents still missing) the score
    # legitimately crosses below BR-01's 50 threshold and fires its own
    # alert -- a real, distinct notification from the "all complete" one
    # below, not a duplicate of it.
    notifications = db_session.query(Notification).all()
    assert len(notifications) == 2
    assert any("has submitted all required preboarding documents" in n.message for n in notifications)
    assert any("joining readiness score has dropped" in n.message for n in notifications)


def test_no_matching_pending_document(db_session, seeded):
    candidate, conv, offer, submission = seeded
    svc.start_document_collection(db_session, candidate, conv, offer, "U-ORG")
    svc.mark_document_received(db_session, candidate, conv, "U-ORG", "ID_PROOF", "https://example.com/x.pdf")

    result = svc.mark_document_received(db_session, candidate, conv, "U-ORG", "ID_PROOF", "https://example.com/y.pdf")  # already RECEIVED
    assert result["outcome"] == "no_matching_document"


# ── classify_document_type ──────────────────────────────────────────────

def test_classify_document_type_returns_valid_classification(db_session, seeded):
    result = svc.classify_document_type("this is my aadhar card scan", llm_call=lambda p: "ID_PROOF")
    assert result == "ID_PROOF"


def test_classify_document_type_falls_back_to_other_on_invalid_response(db_session, seeded):
    result = svc.classify_document_type("random text", llm_call=lambda p: "NONSENSE_VALUE")
    assert result == "OTHER"


def test_classify_document_type_never_raises_on_llm_failure(db_session, seeded):
    def _boom(p):
        raise RuntimeError("simulated failure")
    result = svc.classify_document_type("some text", llm_call=_boom)  # should not raise
    assert result == "OTHER"


# ── TC-003/AC-7/BR-03: reminder escalation ─────────────────────────────

def test_reminder_sent_after_48h_with_no_upload(db_session, seeded):
    candidate, conv, offer, submission = seeded
    svc.start_document_collection(db_session, candidate, conv, offer, "U-ORG")
    doc = db_session.query(PreboardingDocument).first()
    doc.created_at = datetime.utcnow() - timedelta(hours=50)
    db_session.commit()

    result = svc.run_document_reminder_job(db_session)
    assert result["reminded"] >= 1

    db_session.refresh(doc)
    assert doc.reminder_count == 1
    assert doc.last_reminded_at is not None


def test_three_reminders_then_hr_takeover_no_fourth_message(db_session, seeded):
    candidate, conv, offer, submission = seeded
    svc.start_document_collection(db_session, candidate, conv, offer, "U-ORG")
    doc = db_session.query(PreboardingDocument).filter(PreboardingDocument.document_type == "ID_PROOF").first()
    doc.reminder_count = 3
    doc.last_reminded_at = datetime.utcnow() - timedelta(hours=50)
    db_session.commit()

    result = svc.run_document_reminder_job(db_session)
    assert result["escalated"] == 1

    db_session.refresh(doc)
    assert doc.reminder_count == 3  # unchanged -- no 4th reminder sent

    escalation_event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "DOCUMENT_OVERDUE_ESCALATED").first()
    assert escalation_event is not None

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1

    # Run again -- must NOT notify HR a second time for the same document.
    result2 = svc.run_document_reminder_job(db_session)
    assert result2["escalated"] == 0
    assert db_session.query(Notification).count() == 1


def test_reminder_job_ignores_not_yet_due_documents(db_session, seeded):
    candidate, conv, offer, submission = seeded
    svc.start_document_collection(db_session, candidate, conv, offer, "U-ORG")

    result = svc.run_document_reminder_job(db_session)
    assert result["reminded"] == 0
    assert result["escalated"] == 0


# ── BR-01: cancel pending documents ─────────────────────────────────────

def test_cancel_pending_documents_for_candidate(db_session, seeded):
    candidate, conv, offer, submission = seeded
    svc.start_document_collection(db_session, candidate, conv, offer, "U-ORG")

    cancelled_count = svc.cancel_pending_documents_for_candidate(db_session, "C-1")
    assert cancelled_count == 7

    statuses = {d.status for d in db_session.query(PreboardingDocument).all()}
    assert statuses == {"CANCELLED"}
