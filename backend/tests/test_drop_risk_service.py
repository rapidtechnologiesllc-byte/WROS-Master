"""
S-060/HRMS-0460 -- Drop Risk Prediction.

Real architecture under test (see drop_risk_service module docstring):
no fictional pipeline enum -- stage-gating reuses S-059's real
get_candidate_journey() current_stage detection directly. Abandonment
score reused from S-046, sentiment trend reused from S-036. Ghosting
multiplier (BR-03) is permanent per candidate. Hysteresis: flagged at
>=70, only resolved below 60 (spec's own named threshold difference).

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
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_drop_risk import CandidateDropRisk
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_joining_score import CandidateJoiningScore
from app.models.candidate_sentiment_log import CandidateSentimentLog
from app.models.employee import Employee
from app.models.follow_up_schedule import FollowUpSchedule
from app.models.interview_pipeline import SubmissionInterview
from app.models.notification import Notification
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.submission import Submission
from app.models.recruiter_intervention_queue import RecruiterInterventionQueue
from app.models.user import Users, Jobs

import app.services.drop_risk_service as svc


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
        FollowUpSchedule.__table__, CandidateDropRisk.__table__, Notification.__table__, RecruiterInterventionQueue.__table__,
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


def _reply(db, conv, created_at):
    db.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={}, triggered_by="candidate", created_at=created_at))
    db.commit()


def _ai_message(db, conv, created_at):
    db.add(ConversationEvent(conversation_id=conv.id, event_type="ai_message_sent", event_data={"body": "hi"}, triggered_by="ai_agent", created_at=created_at))
    db.commit()


def _sentiment(db, sentiment, analyzed_at=None):
    row = CandidateSentimentLog(tenant_id="U-ORG", candidate_id="C-1", message_event_id=None, sentiment=sentiment, confidence=0.9)
    if analyzed_at:
        row.analyzed_at = analyzed_at
    db.add(row)
    db.commit()
    return row


def _job_score(db, calculated_at=None):
    job = Jobs(jobID="J-1", jobTitle="Sr. Dev", jobDescription="d", jobSkills="[]", jobExperience="5", jobLocation="Remote")
    db.merge(job)
    db.commit()
    score = CandidateJobScore(tenant_id="U-HR", candidate_id="C-1", job_id="J-1", technical_score=90, compensation_score=90, availability_score=90, overall_score=90)
    if calculated_at:
        score.calculated_at = calculated_at
    db.add(score)
    db.commit()
    return score


def _submission(db):
    sub = Submission(tenant_id=None, demand_id="D-1", client_id="CL-1", candidate_id="C-1", submitted_by_user_id="U-HR", status="OFFER_EXTENDED")
    db.add(sub)
    db.commit()
    return sub


def _interview(db, submission, level, outcome="PENDING", scheduled_at=None, created_at=None, reschedule_count=0):
    interview = SubmissionInterview(tenant_id=None, submission_id=submission.id, candidate_id="C-1", level=level, outcome=outcome, scheduled_at=scheduled_at, reschedule_count=reschedule_count)
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


# ── QUALIFYING stage (TC-001) ────────────────────────────────────────────

def test_qualifying_high_risk_no_response_negative_sentiment_stuck(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=8))
    _reply(db_session, conv, datetime.utcnow() - timedelta(days=8))
    # Follow-up outreach since, with zero replies -- 0% response rate.
    _ai_message(db_session, conv, datetime.utcnow() - timedelta(days=3))
    _ai_message(db_session, conv, datetime.utcnow() - timedelta(days=1))
    for _ in range(5):
        _sentiment(db_session, "NEGATIVE")

    result = svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    assert result["drop_risk_score"] >= 70
    assert result["is_flagged"] is True


def test_qualifying_low_risk_engaged_positive(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(hours=5))
    _reply(db_session, conv, datetime.utcnow() - timedelta(hours=4))
    _sentiment(db_session, "POSITIVE")

    result = svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    assert result["drop_risk_score"] < 40
    assert result["is_flagged"] is False


def test_not_applicable_for_engaged_only_stage_still_scores_via_engaged_bucket(db_session, candidate):
    _make_conversation(db_session)
    result = svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    # ENGAGED is in SCORABLE_STAGES (uses the same qualifying-bucket formula)
    assert "drop_risk_score" in result


# ── INTERVIEW stage ──────────────────────────────────────────────────────

def test_interview_stage_reschedules_increase_risk(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=20))
    _reply(db_session, conv, datetime.utcnow() - timedelta(days=19))
    _job_score(db_session, datetime.utcnow() - timedelta(days=15))
    sub = _submission(db_session)
    _interview(db_session, sub, "L1", outcome="PENDING", scheduled_at=datetime.utcnow() + timedelta(days=2), reschedule_count=2)

    result = svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    assert result["risk_signals"]["reschedule_points"] == 20


def test_interview_stage_good_response_rate_low_risk(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=20))
    _reply(db_session, conv, datetime.utcnow() - timedelta(days=19))
    _job_score(db_session, datetime.utcnow() - timedelta(days=15))
    sub = _submission(db_session)
    booked_at = datetime.utcnow() - timedelta(days=3)
    _interview(db_session, sub, "L1", outcome="PENDING", scheduled_at=datetime.utcnow() + timedelta(days=1), created_at=booked_at)
    for _ in range(3):
        _ai_message(db_session, conv, booked_at + timedelta(hours=1))
        _reply(db_session, conv, booked_at + timedelta(hours=2))

    result = svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    assert result["risk_signals"]["response_rate_points"] == 0


# ── OFFER stage ──────────────────────────────────────────────────────────

def test_offer_stage_days_since_release_increases_risk(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=30))
    _reply(db_session, conv, datetime.utcnow() - timedelta(days=29))
    _job_score(db_session, datetime.utcnow() - timedelta(days=25))
    sub = _submission(db_session)
    _interview(db_session, sub, "L1", outcome="PASS")
    _offer(db_session, offer_status="Released", released_at=datetime.utcnow() - timedelta(days=5))

    result = svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    assert result["risk_signals"]["days_since_release_points"] == 40  # 5 days * 8


# ── PREBOARDING stage (TC-002) ────────────────────────────────────────────

def test_preboarding_low_readiness_high_risk(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=40))
    _reply(db_session, conv, datetime.utcnow() - timedelta(days=39))
    _job_score(db_session, datetime.utcnow() - timedelta(days=35))
    sub = _submission(db_session)
    _interview(db_session, sub, "L1", outcome="PASS")
    offer = _offer(db_session, offer_status="Accepted", responded_at=datetime.utcnow() - timedelta(days=5), joining_date=date.today() + timedelta(days=10))
    db_session.add(CandidateJoiningScore(tenant_id="U-ORG", candidate_id="C-1", offer_id=offer.id, readiness_score=25, score_breakdown={}))
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={}, triggered_by="candidate", created_at=datetime.utcnow() - timedelta(days=6)))
    db_session.commit()

    result = svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    assert result["risk_signals"]["readiness_points"] == round((100 - 25) * 0.70)
    assert result["drop_risk_score"] >= 65


def test_preboarding_no_joining_score_skips_that_component(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=40))
    _reply(db_session, conv, datetime.utcnow() - timedelta(days=39))
    _job_score(db_session, datetime.utcnow() - timedelta(days=35))
    sub = _submission(db_session)
    _interview(db_session, sub, "L1", outcome="PASS")
    _offer(db_session, offer_status="Accepted", responded_at=datetime.utcnow())

    result = svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    assert result["risk_signals"]["readiness_points"] == 0


# ── BR-03: ghosting multiplier, permanent ───────────────────────────────

def test_ghosting_multiplier_applied_and_capped(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=8))
    _reply(db_session, conv, datetime.utcnow() - timedelta(days=8))
    for _ in range(5):
        _sentiment(db_session, "NEGATIVE")
    db_session.add(CandidateGhostingStatus(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, ghosted_at=datetime.utcnow() - timedelta(days=10), is_reactivated=False))
    db_session.commit()

    result = svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    assert result["risk_signals"]["ghosting_multiplier_applied"] is True
    assert result["drop_risk_score"] <= 100


def test_reactivated_ghost_does_not_get_multiplier(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(hours=5))
    _reply(db_session, conv, datetime.utcnow() - timedelta(hours=4))
    db_session.add(CandidateGhostingStatus(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, ghosted_at=datetime.utcnow() - timedelta(days=10), is_reactivated=True))
    db_session.commit()

    result = svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    assert result["risk_signals"]["ghosting_multiplier_applied"] is False


# ── BR-01: CRITICAL notification ────────────────────────────────────────

def test_critical_score_notifies_recruiter_immediately(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=8))
    _reply(db_session, conv, datetime.utcnow() - timedelta(days=8))
    for _ in range(5):
        _sentiment(db_session, "NEGATIVE")
    db_session.add(CandidateGhostingStatus(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, ghosted_at=datetime.utcnow() - timedelta(days=10), is_reactivated=False))
    db_session.add(Submission(tenant_id=None, demand_id="D-1", client_id="CL-1", candidate_id="C-1", submitted_by_user_id="U-HR", status="OFFER_EXTENDED"))
    db_session.commit()

    result = svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    assert result["risk_level"] == "CRITICAL"
    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1
    assert "CRITICAL" in notifications[0].message


def test_repeated_critical_does_not_renotify(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=8))
    _reply(db_session, conv, datetime.utcnow() - timedelta(days=8))
    for _ in range(5):
        _sentiment(db_session, "NEGATIVE")
    db_session.add(CandidateGhostingStatus(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, ghosted_at=datetime.utcnow() - timedelta(days=10), is_reactivated=False))
    db_session.add(Submission(tenant_id=None, demand_id="D-1", client_id="CL-1", candidate_id="C-1", submitted_by_user_id="U-HR", status="OFFER_EXTENDED"))
    db_session.commit()

    svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    assert db_session.query(Notification).count() == 1


# ── Hysteresis: flagged at 70, resolved only below 60 ───────────────────

def test_flag_hysteresis_stays_flagged_between_60_and_69(db_session, candidate):
    row = CandidateDropRisk(tenant_id="U-ORG", candidate_id="C-1", drop_risk_score=72, risk_level="HIGH", risk_signals={}, is_flagged=True)
    db_session.add(row)
    db_session.commit()

    # Deliberately lands at 67 (< 70 but >= 60): single NEGATIVE sentiment
    # (25pts, my bucket's "all negative" trivially true for 1 item), 8
    # days since first reply (>7 -> 15pts), abandonment_score=45 (0
    # response-rate + 25 sentiment + 20 days-silent) -> 27pts. 27+25+15=67.
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(days=8))
    _reply(db_session, conv, datetime.utcnow() - timedelta(days=8))
    _sentiment(db_session, "NEGATIVE")

    result = svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    assert 60 <= result["drop_risk_score"] < 70
    assert result["is_flagged"] is True  # still flagged, hasn't dropped below 60


def test_resolved_and_logged_below_60(db_session, candidate):
    conv = _make_conversation(db_session, created_at=datetime.utcnow() - timedelta(hours=5))
    row = CandidateDropRisk(tenant_id="U-ORG", candidate_id="C-1", drop_risk_score=72, risk_level="HIGH", risk_signals={}, is_flagged=True)
    db_session.add(row)
    _reply(db_session, conv, datetime.utcnow() - timedelta(hours=4))
    _sentiment(db_session, "POSITIVE")
    db_session.commit()

    result = svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    assert result["drop_risk_score"] < 60
    assert result["is_flagged"] is False

    resolved_events = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "DROP_RISK_RESOLVED").all()
    assert len(resolved_events) == 1


def test_candidate_not_found(db_session):
    result = svc.calculate_drop_risk(db_session, "NOPE", "U-ORG")
    assert result["outcome"] == "not_found"


def test_joined_candidate_not_applicable(db_session, candidate):
    conv = _make_conversation(db_session)
    _reply(db_session, conv, datetime.utcnow())
    _job_score(db_session, datetime.utcnow())
    sub = _submission(db_session)
    _interview(db_session, sub, "L1", outcome="PASS")
    _offer(db_session, offer_status="Accepted", responded_at=datetime.utcnow())
    db_session.add(Employee(candidate_id="C-1", first_name="Priya", last_name="S", email="priya@blitzenx.com", joining_date=date(2026, 9, 1), employee_number="EMP-001"))
    db_session.commit()

    result = svc.calculate_drop_risk(db_session, "C-1", "U-ORG")
    assert result["outcome"] == "not_applicable"
    assert result["stage"] == "JOINED"


# ── Job batch processing ─────────────────────────────────────────────────

def test_job_scores_all_candidates_with_conversations(db_session, candidate):
    _make_conversation(db_session)
    result = svc.run_drop_risk_scoring_job(db_session)
    assert result["scored"] == 1
