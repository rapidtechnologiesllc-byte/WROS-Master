"""
import logging
S-062/HRMS-0462 -- Recruiter Intervention Queue.

Real architecture under test (see intervention_queue_service module
docstring): the 7 real trigger points named in Step 2's integrations
table are exercised via the actual functions that call add_to_queue()
internally (escalate(), calculate_drop_risk(), calculate_abandonment_score(),
sla breach detection, no-show confirmation, offer counter, document
overdue escalation) -- not re-implemented against the queue service in
isolation, so a real regression in the wiring would actually be caught
here. BR-01 (CRITICAL sorts first), BR-02 (dedup), BR-03 (auto-resolve)
all verified directly.

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
from app.models.candidate_abandonment_score import CandidateAbandonmentScore
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.candidate_drop_risk import CandidateDropRisk
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_joining_score import CandidateJoiningScore
from app.models.candidate_sentiment_log import CandidateSentimentLog
from app.models.consent import ConsentRecord
from app.models.sla_breach import CandidateSLABreach
from app.models.employee import Employee
from app.models.follow_up_schedule import FollowUpSchedule
from app.models.interview_pipeline import SubmissionInterview
from app.models.notification import Notification
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.recruiter_intervention_queue import RecruiterInterventionQueue
from app.models.submission import Submission
from app.models.user import Users, Jobs

import app.services.abandonment_scoring_service as abandonment_svc
import app.services.conversation_state_service as state_svc
import app.services.document_collection_service as doc_svc
import app.services.drop_risk_service as drop_risk_svc
import app.services.intervention_queue_service as svc
import app.services.offer_decision_service as offer_decision_svc
import app.services.sla_monitoring_service as sla_svc

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Jobs.__table__, Candidate.__table__, CandidateInfoForm.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, CandidateJobScore.__table__,
        SubmissionInterview.__table__, OfferLetter.__table__, CandidateJoiningScore.__table__,
        PreboardingDocument.__table__, Employee.__table__, Submission.__table__,
        CandidateAbandonmentScore.__table__, CandidateSentimentLog.__table__, CandidateGhostingStatus.__table__,
        FollowUpSchedule.__table__, CandidateDropRisk.__table__, Notification.__table__,
        CandidateSLABreach.__table__, RecruiterInterventionQueue.__table__,
        CandidateAIAssignment.__table__, ConsentRecord.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

@pytest.fixture()
def candidate(db_session):
    hr_user = Users(UserID="U-HR", UserRole="HR Manager", UserEmail="hr@blitzenx.com", UserPassword="h", tenant_id=None)
    db_session.add(hr_user)
    c = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya", candidateMobile="+919876543210")
    db_session.add(c)
    db_session.commit()
    return c

def _make_conversation(db, created_at=None):
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp")
    if created_at:
        conv.created_at = created_at
    db.add(conv)
    db.commit()
    return conv

# ── Core add/dedup/resolve ───────────────────────────────────────────────

def test_add_to_queue_creates_open_item(db_session, candidate):
    result = svc.add_to_queue(db_session, "C-1", "U-ORG", "ESCALATION", "test reason", 1)
    assert result["outcome"] == "created"
    row = db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.id == result["id"]).first()
    assert row.status == "OPEN"

def test_add_to_queue_dedups_open_item(db_session, candidate):
    svc.add_to_queue(db_session, "C-1", "U-ORG", "ESCALATION", "first reason", 2)
    result = svc.add_to_queue(db_session, "C-1", "U-ORG", "ESCALATION", "updated reason", 1)
    assert result["outcome"] == "updated"
    assert db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.candidate_id == "C-1", RecruiterInterventionQueue.queue_reason == "ESCALATION").count() == 1
    row = db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.id == result["id"]).first()
    assert row.reason_detail == "updated reason"
    assert row.priority == 1

def test_resolve_queue_items(db_session, candidate):
    svc.add_to_queue(db_session, "C-1", "U-ORG", "HIGH_DROP_RISK", "risk 72", 2)
    count = svc.resolve_queue_items(db_session, "C-1", "U-ORG", ["HIGH_DROP_RISK"])
    assert count == 1
    row = db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.candidate_id == "C-1").first()
    assert row.status == "RESOLVED"
    assert row.resolved_at is not None

# ── BR-01: CRITICAL sorts first regardless of age ───────────────────────

def test_critical_sorts_first_regardless_of_age(db_session, candidate):
    svc.add_to_queue(db_session, "C-1", "U-ORG", "SLA_BREACH", "29h", 2)  # HIGH, added first (older)
    svc.add_to_queue(db_session, "C-1", "U-ORG", "CRITICAL_DROP_RISK", "84", 1)  # CRITICAL, added second (newer)

    queue = svc.get_queue(db_session, "U-ORG")
    assert queue[0]["queue_reason"] == "CRITICAL_DROP_RISK"
    assert queue[1]["queue_reason"] == "SLA_BREACH"

def test_queue_summary_counts_by_priority(db_session, candidate):
    svc.add_to_queue(db_session, "C-1", "U-ORG", "CRITICAL_DROP_RISK", "84", 1)
    svc.add_to_queue(db_session, "C-1", "U-ORG", "SLA_BREACH", "29h", 2)

    summary = svc.get_queue_summary(db_session, "U-ORG")
    assert summary == {"critical": 1, "high": 1, "medium": 0, "total": 2}

# ── Take over / resolve ──────────────────────────────────────────────────

def test_take_over_transfers_ownership_and_marks_in_progress(db_session, candidate):
    conv = _make_conversation(db_session)
    result = svc.add_to_queue(db_session, "C-1", "U-ORG", "ESCALATION", "human requested", 2)

    outcome = svc.take_over_queue_item(db_session, result["id"], "U-ORG", "U-HR")
    assert outcome["status"] == "IN_PROGRESS"
    assert outcome["assigned_to_user_id"] == "U-HR"

    db_session.refresh(conv)
    assert conv.owner_type == "hr_user"
    assert conv.owner_id == "U-HR"

def test_take_over_unknown_item_raises(db_session):
    with pytest.raises(svc.QueueItemNotFound):
        svc.take_over_queue_item(db_session, 999999, "U-ORG", "U-HR")

def test_mark_resolved_with_note(db_session, candidate):
    result = svc.add_to_queue(db_session, "C-1", "U-ORG", "OFFER_COUNTER", "countered", 3)
    outcome = svc.mark_resolved(db_session, result["id"], "U-ORG", "U-HR", "Handled, offer revised.")
    assert outcome["status"] == "RESOLVED"
    row = db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.id == result["id"]).first()
    assert row.resolved_by == "U-HR"
    assert row.resolution_note == "Handled, offer revised."

def test_resolved_items_hidden_after_retention_window(db_session, candidate):
    result = svc.add_to_queue(db_session, "C-1", "U-ORG", "OFFER_COUNTER", "countered", 3)
    row = db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.id == result["id"]).first()
    row.status = "RESOLVED"
    row.resolved_at = datetime.utcnow() - timedelta(days=10)
    db_session.commit()

    queue = svc.get_queue(db_session, "U-ORG")
    assert queue == []

# ── Real wiring: TC-001, escalation via S-035's real escalate() ─────────

def test_escalation_adds_queue_item_via_real_escalate(db_session, candidate):
    conv = _make_conversation(db_session)
    state_svc.escalate(db_session, conv, reason="Candidate requested a human", triggered_by="ai_agent")
    db_session.commit()

    row = db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.candidate_id == "C-1", RecruiterInterventionQueue.queue_reason == "ESCALATION").first()
    assert row is not None
    assert row.status == "OPEN"
    assert row.priority == 2  # HIGH -- no legal keyword

def test_escalation_with_legal_keyword_is_critical(db_session, candidate):
    conv = _make_conversation(db_session)
    state_svc.escalate(db_session, conv, reason="Candidate mentioned their lawyer", triggered_by="ai_agent")
    db_session.commit()

    row = db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.candidate_id == "C-1").first()
    assert row.priority == 1  # CRITICAL

def test_escalation_resolved_auto_resolves_queue_item(db_session, candidate):
    conv = _make_conversation(db_session)
    state_svc.escalate(db_session, conv, reason="Candidate requested a human", triggered_by="ai_agent")
    db_session.commit()
    state_svc.resolve_escalation(db_session, conv, reason="Recruiter handled it", triggered_by="hr_user")
    db_session.commit()

    row = db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.candidate_id == "C-1").first()
    assert row.status == "RESOLVED"

# ── Real wiring: drop risk (TC-005) ──────────────────────────────────────

def test_critical_drop_risk_adds_queue_item(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=8))
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={}, triggered_by="candidate", created_at=datetime.utcnow() - timedelta(days=8)))
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="ai_message_sent", event_data={}, triggered_by="ai_agent", created_at=datetime.utcnow() - timedelta(days=3)))
    for _ in range(5):
        db_session.add(CandidateSentimentLog(tenant_id="U-ORG", candidate_id="C-1", message_event_id=None, sentiment="NEGATIVE", confidence=0.9))
    db_session.add(CandidateGhostingStatus(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, ghosted_at=datetime.utcnow() - timedelta(days=10), is_reactivated=False))
    db_session.commit()

    result = drop_risk_svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    assert result["risk_level"] == "CRITICAL"

    row = db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.candidate_id == "C-1", RecruiterInterventionQueue.queue_reason == "CRITICAL_DROP_RISK").first()
    assert row is not None
    assert row.priority == 1

def test_drop_risk_falling_below_50_resolves_queue_item(db_session, candidate):
    row = RecruiterInterventionQueue(tenant_id="U-ORG", candidate_id="C-1", queue_reason="HIGH_DROP_RISK", reason_detail="72", priority=2, status="OPEN")
    db_session.add(row)
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(hours=5))
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={}, triggered_by="candidate", created_at=datetime.utcnow() - timedelta(hours=4)))
    db_session.commit()

    drop_risk_svc.calculate_drop_risk(db_session, "C-1", "U-ORG")

    refreshed = db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.candidate_id == "C-1").first()
    assert refreshed.status == "RESOLVED"

# ── Real wiring: abandonment ──────────────────────────────────────────────

def test_high_abandonment_adds_queue_item(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=10))
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="ai_message_sent", event_data={}, triggered_by="ai_agent", created_at=datetime.utcnow() - timedelta(days=3)))
    for _ in range(3):
        db_session.add(CandidateSentimentLog(tenant_id="U-ORG", candidate_id="C-1", message_event_id=None, sentiment="NEGATIVE", confidence=0.9))
    db_session.commit()

    abandonment_svc.calculate_abandonment_score(db_session, "C-1", "U-ORG", conv)

    row = db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.candidate_id == "C-1", RecruiterInterventionQueue.queue_reason == "HIGH_ABANDONMENT").first()
    assert row is not None

# ── Real wiring: SLA breach ────────────────────────────────────────────────

def test_sla_breach_adds_queue_item(db_session, candidate):
    _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(hours=30))
    conv = db_session.query(CandidateConversation).first()
    conv.updated_at = datetime.utcnow() - timedelta(hours=30)
    db_session.commit()

    sla_svc.detect_and_resolve_no_contact_breaches(db_session, "U-ORG")

    row = db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.candidate_id == "C-1", RecruiterInterventionQueue.queue_reason == "SLA_BREACH").first()
    assert row is not None
    assert row.priority == 2

# ── Real wiring: offer counter ────────────────────────────────────────────

def test_offer_counter_adds_queue_item_alongside_escalation(db_session, candidate):
    conv = _make_conversation(db_session)
    offer = OfferLetter(candidate_id="C-1", position="Sr. Dev", salary="24 LPA", joining_date=date(2026, 9, 1), offer_expire_date=date(2026, 8, 20), offer_status="Released", created_by="U-HR")
    db_session.add(offer)
    db_session.commit()

    offer_decision_svc._handle_counter(db_session, candidate, conv, offer, "Can we discuss the salary?")

    reasons = {r.queue_reason for r in db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.candidate_id == "C-1").all()}
    assert "OFFER_COUNTER" in reasons
    assert "ESCALATION" in reasons  # documented real overlap -- see module docstring

# ── Real wiring: document overdue ────────────────────────────────────────

def test_document_overdue_adds_and_resolves_queue_item(db_session, candidate):
    conv = _make_conversation(db_session)
    offer = OfferLetter(candidate_id="C-1", position="Sr. Dev", salary="24 LPA", joining_date=date(2026, 9, 1), offer_expire_date=date(2026, 8, 20), offer_status="Accepted", created_by="U-HR")
    db_session.add(offer)
    db_session.commit()

    doc = PreboardingDocument(tenant_id="U-ORG", candidate_id="C-1", offer_id=offer.id, document_type="ID_PROOF", document_label="Government ID", status="PENDING", reminder_count=3)
    doc.created_at = datetime.utcnow() - timedelta(hours=200)
    doc.last_reminded_at = datetime.utcnow() - timedelta(hours=50)
    db_session.add(doc)
    db_session.commit()

    doc_svc.run_document_reminder_job(db_session)

    row = db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.candidate_id == "C-1", RecruiterInterventionQueue.queue_reason == "DOCUMENT_OVERDUE").first()
    assert row is not None
    assert row.status == "OPEN"

    doc_svc.mark_document_received(db_session, candidate, conv, "U-ORG", "ID_PROOF", "https://example.com/id.pdf")

    db_session.refresh(row)
    assert row.status == "RESOLVED"

# ── Real wiring: no-show ──────────────────────────────────────────────────

def test_no_show_adds_queue_item(db_session, candidate):
    conv = _make_conversation(db_session)
    submission = Submission(tenant_id=None, demand_id="D-1", client_id="CL-1", candidate_id="C-1", submitted_by_user_id="U-HR", status="OFFER_EXTENDED")
    db_session.add(submission)
    db_session.commit()

    interview = SubmissionInterview(
        tenant_id=None, submission_id=submission.id, candidate_id="C-1", level="L1", outcome="PENDING",
        scheduled_at=datetime.utcnow() - timedelta(minutes=35),
        no_show_check_in_at=datetime.utcnow() - timedelta(minutes=20),
    )
    db_session.add(interview)
    db_session.commit()

    from app.services.interview_no_show_service import run_no_show_detection_job
    run_no_show_detection_job(db_session)

    row = db_session.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.candidate_id == "C-1", RecruiterInterventionQueue.queue_reason == "NO_SHOW").first()
    assert row is not None
