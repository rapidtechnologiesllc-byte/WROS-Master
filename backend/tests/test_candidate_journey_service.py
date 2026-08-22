"""
S-059/HRMS-0459 -- Candidate Journey Dashboard.

Real architecture under test (see candidate_journey_service module
docstring): no conversation_state_history table or fictional 10-value
state enum -- each of the 7 stages is derived from the existence of
real artifacts (conversation, first candidate reply, CandidateJobScore,
SubmissionInterview, OfferLetter, CandidateJoiningScore, Employee).
BR-02 (JOINED only green after real employee conversion) is verified
directly. BR-01's literal multi-visit history has no real equivalent
in this codebase and is not attempted -- flagged in the module
docstring, not silently faked.

"""
import os
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_joining_score import CandidateJoiningScore
from app.models.employee import Employee
from app.models.interview_pipeline import SubmissionInterview
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.submission import Submission
from app.models.user import Users, Jobs

import app.services.candidate_journey_service as svc

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
def candidate(db_session):
    hr_user = Users(UserID="U-HR", UserRole="HR Manager", UserEmail="hr@blitzenx.com", UserPassword="h", tenant_id=None)
    db_session.add(hr_user)
    c = Candidate(
        candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya",
        candidateMobile="+919876543210", candidateGender="Female", candidateDateOfBirth=date(1995, 1, 1),
        candidateCurrentLocation="Bangalore", candidateJoiningDate=date(2026, 9, 1), candidateExperience="5",
        candidateJobTitle="Guidewire Developer",
    )
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

def _reply(db, conv, created_at):
    db.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={}, triggered_by="candidate", created_at=created_at))
    db.commit()

def _ai_message(db, conv, created_at):
    db.add(ConversationEvent(conversation_id=conv.id, event_type="ai_message_sent", event_data={"body": "hi"}, triggered_by="ai_agent", created_at=created_at))
    db.commit()

def _job_score(db, calculated_at, overall=87, technical=92, compensation=100, availability=75):
    job = Jobs(jobID="J-1", jobTitle="Sr. Dev", jobDescription="d", jobSkills="[]", jobExperience="5", jobLocation="Remote")
    db.merge(job)
    db.commit()
    score = CandidateJobScore(tenant_id="U-HR", candidate_id="C-1", job_id="J-1", technical_score=technical, compensation_score=compensation, availability_score=availability, overall_score=overall)
    score.calculated_at = calculated_at
    db.add(score)
    db.commit()
    return score

def _submission(db, submitted_at=None):
    sub = Submission(tenant_id=None, demand_id="D-1", client_id="CL-1", candidate_id="C-1", submitted_by_user_id="U-HR", status="OFFER_EXTENDED")
    if submitted_at:
        sub.submitted_at = submitted_at
    db.add(sub)
    db.commit()
    return sub

def _interview(db, submission, level, outcome="PENDING", scheduled_at=None, created_at=None):
    interview = SubmissionInterview(tenant_id=None, submission_id=submission.id, candidate_id="C-1", level=level, outcome=outcome, scheduled_at=scheduled_at)
    if created_at:
        interview.created_at = created_at
    db.add(interview)
    db.commit()
    return interview

def _offer(db, offer_status="Pending", created_at=None, responded_at=None, joining_date=None, released_at=None):
    offer = OfferLetter(candidate_id="C-1", position="Sr. Dev", salary="24 LPA", joining_date=joining_date or date(2026, 9, 1), offer_expire_date=date(2026, 8, 20), offer_status=offer_status, created_by="U-HR", responded_at=responded_at, released_at=released_at)
    if created_at:
        offer.created_at = created_at
    db.add(offer)
    db.commit()
    return offer

def _employee(db, joining_date=date(2026, 9, 1), employee_number="EMP-001"):
    emp = Employee(candidate_id="C-1", first_name="Priya", last_name="S", email="priya@blitzenx.com", joining_date=joining_date, employee_number=employee_number)
    db.add(emp)
    db.commit()
    return emp

# ── TC-001: rendering, candidate in SCREENED state ──────────────────────

def test_screened_candidate_shows_correct_stage_colors(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=10))
    _reply(db_session, conv, datetime.utcnow() - timedelta(days=9))
    _job_score(db_session, datetime.utcnow() - timedelta(days=2))

    result = svc.get_candidate_journey(db_session, "C-1", "U-ORG")
    by_name = {s["stage_name"]: s for s in result["stages"]}

    assert by_name["ENGAGED"]["status"] == "completed"
    assert by_name["QUALIFYING"]["status"] == "completed"
    assert by_name["SCREENED"]["status"] == "active"
    assert by_name["INTERVIEW"]["status"] == "pending"
    assert by_name["OFFER"]["status"] == "pending"
    assert by_name["PREBOARDING"]["status"] == "pending"
    assert by_name["JOINED"]["status"] == "pending"
    assert result["current_stage"] == "SCREENED"

# ── TC-002: active metrics card, QUALIFYING state ───────────────────────

def test_qualifying_active_metrics(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=4))
    _reply(db_session, conv, datetime.utcnow() - timedelta(days=4))
    for _ in range(8):
        _ai_message(db_session, conv, datetime.utcnow() - timedelta(hours=1))

    result = svc.get_candidate_journey(db_session, "C-1", "U-ORG")
    by_name = {s["stage_name"]: s for s in result["stages"]}

    assert by_name["QUALIFYING"]["status"] == "active"
    metrics = by_name["QUALIFYING"]["metrics"]
    assert metrics["thunder_message_count"] == 8
    assert metrics["missing_fields_count"] >= 0
    assert metrics["profile_completeness_pct"] is not None
    assert metrics["days_in_stage"] == 4

# ── Only ENGAGED reached (brand new candidate) ──────────────────────────

def test_only_engaged_reached_for_brand_new_candidate(db_session, candidate):
    _make_conversation(db_session)

    result = svc.get_candidate_journey(db_session, "C-1", "U-ORG")
    by_name = {s["stage_name"]: s for s in result["stages"]}
    assert by_name["ENGAGED"]["status"] == "active"
    assert result["current_stage"] == "ENGAGED"
    for name in ("QUALIFYING", "SCREENED", "INTERVIEW", "OFFER", "PREBOARDING", "JOINED"):
        assert by_name[name]["status"] == "pending"

# ── INTERVIEW stage L1/L2 metrics ───────────────────────────────────────

def test_interview_stage_shows_l1_l2_outcomes(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=20))
    _reply(db_session, conv, datetime.utcnow() - timedelta(days=19))
    _job_score(db_session, datetime.utcnow() - timedelta(days=15))
    sub = _submission(db_session)
    _interview(db_session, sub, "L1", outcome="PASS", scheduled_at=datetime(2026, 1, 18, 10, 0))
    _interview(db_session, sub, "L2", outcome="PENDING", scheduled_at=datetime(2026, 1, 22, 14, 0))

    result = svc.get_candidate_journey(db_session, "C-1", "U-ORG")
    by_name = {s["stage_name"]: s for s in result["stages"]}

    assert by_name["INTERVIEW"]["status"] == "active"
    metrics = by_name["INTERVIEW"]["metrics"]
    assert metrics["l1_outcome"] == "PASS"
    assert metrics["l2_outcome"] == "PENDING"

def test_superseded_interviews_excluded(db_session, candidate):
    conv = _make_conversation(db_session)
    _reply(db_session, conv, datetime.utcnow())
    _job_score(db_session, datetime.utcnow())
    sub = _submission(db_session)
    old = _interview(db_session, sub, "L1", outcome="PENDING")
    old.superseded_at = datetime.utcnow()
    db_session.commit()
    _interview(db_session, sub, "L1", outcome="PASS")

    result = svc.get_candidate_journey(db_session, "C-1", "U-ORG")
    by_name = {s["stage_name"]: s for s in result["stages"]}
    assert by_name["INTERVIEW"]["metrics"]["l1_outcome"] == "PASS"

# ── OFFER stage ──────────────────────────────────────────────────────────

def test_offer_stage_metrics(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=30))
    _reply(db_session, conv, datetime.utcnow() - timedelta(days=29))
    _job_score(db_session, datetime.utcnow() - timedelta(days=25))
    sub = _submission(db_session)
    _interview(db_session, sub, "L1", outcome="PASS")
    _offer(db_session, offer_status="Released", released_at=datetime.utcnow() - timedelta(days=2))

    result = svc.get_candidate_journey(db_session, "C-1", "U-ORG")
    by_name = {s["stage_name"]: s for s in result["stages"]}
    assert by_name["OFFER"]["status"] == "active"
    assert by_name["OFFER"]["metrics"]["offer_status"] == "Released"

# ── PREBOARDING stage (S-058 wiring) ────────────────────────────────────

def test_preboarding_stage_uses_accepted_offer_and_joining_score(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=40))
    _reply(db_session, conv, datetime.utcnow() - timedelta(days=39))
    _job_score(db_session, datetime.utcnow() - timedelta(days=35))
    sub = _submission(db_session)
    _interview(db_session, sub, "L1", outcome="PASS")
    offer = _offer(db_session, offer_status="Accepted", responded_at=datetime.utcnow() - timedelta(days=5), joining_date=date.today() + timedelta(days=10))
    db_session.add(PreboardingDocument(tenant_id="U-ORG", candidate_id="C-1", offer_id=offer.id, document_type="ID_PROOF", document_label="ID", status="RECEIVED"))
    db_session.add(PreboardingDocument(tenant_id="U-ORG", candidate_id="C-1", offer_id=offer.id, document_type="ADDRESS_PROOF", document_label="Address", status="PENDING"))
    db_session.add(CandidateJoiningScore(tenant_id="U-ORG", candidate_id="C-1", offer_id=offer.id, readiness_score=73, score_breakdown={}))
    db_session.commit()

    result = svc.get_candidate_journey(db_session, "C-1", "U-ORG")
    by_name = {s["stage_name"]: s for s in result["stages"]}
    assert by_name["PREBOARDING"]["status"] == "active"
    metrics = by_name["PREBOARDING"]["metrics"]
    assert metrics["joining_readiness_score"] == 73
    assert metrics["documents_received"] == 1
    assert metrics["documents_total"] == 2
    assert metrics["days_until_start"] == 10

def test_offer_not_yet_accepted_does_not_reach_preboarding(db_session, candidate):
    conv = _make_conversation(db_session)
    _reply(db_session, conv, datetime.utcnow())
    _job_score(db_session, datetime.utcnow())
    sub = _submission(db_session)
    _interview(db_session, sub, "L1", outcome="PASS")
    _offer(db_session, offer_status="Released")

    result = svc.get_candidate_journey(db_session, "C-1", "U-ORG")
    by_name = {s["stage_name"]: s for s in result["stages"]}
    assert by_name["OFFER"]["status"] == "active"
    assert by_name["PREBOARDING"]["status"] == "pending"

# ── BR-02: JOINED only green after real Employee conversion ────────────

def test_br02_joined_stays_pending_until_employee_conversion(db_session, candidate):
    conv = _make_conversation(db_session)
    _reply(db_session, conv, datetime.utcnow())
    _job_score(db_session, datetime.utcnow())
    sub = _submission(db_session)
    _interview(db_session, sub, "L1", outcome="PASS")
    _offer(db_session, offer_status="Accepted", responded_at=datetime.utcnow())

    result = svc.get_candidate_journey(db_session, "C-1", "U-ORG")
    by_name = {s["stage_name"]: s for s in result["stages"]}
    assert by_name["PREBOARDING"]["status"] == "active"
    assert by_name["JOINED"]["status"] == "pending"

def test_br02_joined_turns_active_only_with_real_employee_row(db_session, candidate):
    conv = _make_conversation(db_session)
    _reply(db_session, conv, datetime.utcnow())
    _job_score(db_session, datetime.utcnow())
    sub = _submission(db_session)
    _interview(db_session, sub, "L1", outcome="PASS")
    _offer(db_session, offer_status="Accepted", responded_at=datetime.utcnow())
    _employee(db_session, employee_number="EMP-042")

    result = svc.get_candidate_journey(db_session, "C-1", "U-ORG")
    by_name = {s["stage_name"]: s for s in result["stages"]}
    assert by_name["JOINED"]["status"] == "active"
    assert by_name["PREBOARDING"]["status"] == "completed"
    assert by_name["JOINED"]["metrics"]["employee_number"] == "EMP-042"
    assert result["current_stage"] == "JOINED"

def test_candidate_not_found_raises(db_session):
    with pytest.raises(svc.CandidateNotFound):
        svc.get_candidate_journey(db_session, "NOPE", "U-ORG")
