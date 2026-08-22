"""
S-070/HRMS-0470 -- Candidate Engagement Health Metrics.

Real architecture under test (see engagement_metrics_service module
docstring): no conversation_messages table -- reuses real
ConversationEvent (ai_message_sent/candidate_reply). days_to_qualification
uses S-059's real SCREENED stage detection. BR-01 (exclude ghost
periods) uses the real CandidateGhostingStatus.ghosted_at.

"""
import os
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_engagement_metrics import CandidateEngagementMetrics
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_joining_score import CandidateJoiningScore
from app.models.candidate_sentiment_log import CandidateSentimentLog
from app.models.employee import Employee
from app.models.interview_pipeline import SubmissionInterview
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.submission import Submission
from app.models.user import Users, Jobs

import app.services.engagement_metrics_service as svc

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
    db_session.add(Users(UserID="U-HR", UserRole="HR Manager", UserEmail="hr@blitzenx.com", UserPassword="h", tenant_id=None))
    c = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    db_session.add(c)
    db_session.commit()
    return c

def _conversation(db, created_at=None):
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none")
    if created_at:
        conv.created_at = created_at
    db.add(conv)
    db.commit()
    return conv

def _outbound(db, conv, at):
    db.add(ConversationEvent(conversation_id=conv.id, event_type="ai_message_sent", event_data={"body": "hi"}, triggered_by="ai_agent", created_at=at))
    db.commit()

def _inbound(db, conv, at):
    db.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={"body": "hi back"}, triggered_by="candidate", created_at=at))
    db.commit()

# ── TC-001: zero response ────────────────────────────────────────────────

def test_zero_inbound_gives_zero_response_rate(db_session, candidate):
    conv = _conversation(db_session)
    base = datetime.utcnow() - timedelta(days=1)
    for i in range(5):
        _outbound(db_session, conv, base + timedelta(hours=i))

    result = svc.calculate_engagement_health(db_session, "C-1", "U-ORG")
    assert result["response_rate"] == 0
    assert result["avg_response_time_minutes"] is None

# ── TC-002: response time averaging ─────────────────────────────────────

def test_avg_response_time_computed_from_pairs(db_session, candidate):
    conv = _conversation(db_session)
    base = datetime.utcnow() - timedelta(days=1)
    _outbound(db_session, conv, base)
    _inbound(db_session, conv, base + timedelta(minutes=60))
    _outbound(db_session, conv, base + timedelta(hours=2))
    _inbound(db_session, conv, base + timedelta(hours=2, minutes=120))
    _outbound(db_session, conv, base + timedelta(hours=6))
    _inbound(db_session, conv, base + timedelta(hours=6, minutes=180))

    result = svc.calculate_engagement_health(db_session, "C-1", "U-ORG")
    assert result["avg_response_time_minutes"] == 120

def test_response_rate_capped_at_100(db_session, candidate):
    conv = _conversation(db_session)
    base = datetime.utcnow() - timedelta(days=1)
    _outbound(db_session, conv, base)
    _inbound(db_session, conv, base + timedelta(minutes=10))
    _inbound(db_session, conv, base + timedelta(minutes=20))  # more replies than outbound

    result = svc.calculate_engagement_health(db_session, "C-1", "U-ORG")
    assert result["response_rate"] == 100

def test_gap_over_7_days_excluded_from_average(db_session, candidate):
    conv = _conversation(db_session)
    base = datetime.utcnow() - timedelta(days=20)
    _outbound(db_session, conv, base)
    _inbound(db_session, conv, base + timedelta(days=10))  # ghosting-length gap, excluded
    _outbound(db_session, conv, base + timedelta(days=11))
    _inbound(db_session, conv, base + timedelta(days=11, minutes=30))

    result = svc.calculate_engagement_health(db_session, "C-1", "U-ORG")
    assert result["avg_response_time_minutes"] == 30

# ── total messages ────────────────────────────────────────────────────────

def test_total_messages_exchanged_counts_all(db_session, candidate):
    conv = _conversation(db_session)
    base = datetime.utcnow() - timedelta(days=1)
    _outbound(db_session, conv, base)
    _inbound(db_session, conv, base + timedelta(minutes=10))
    _outbound(db_session, conv, base + timedelta(hours=1))

    result = svc.calculate_engagement_health(db_session, "C-1", "U-ORG")
    assert result["total_messages_exchanged"] == 3

# ── BR-01: ghost period excluded from denominator ───────────────────────

def test_ghost_period_outbound_excluded_from_response_rate(db_session, candidate):
    conv = _conversation(db_session)
    base = datetime.utcnow() - timedelta(days=10)
    _outbound(db_session, conv, base)
    _inbound(db_session, conv, base + timedelta(minutes=10))

    ghosted_at = base + timedelta(days=1)
    db_session.add(CandidateGhostingStatus(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, ghosted_at=ghosted_at, is_reactivated=False))
    db_session.commit()
    # 3 more outbound messages sent DURING the ghost period, never replied to
    for i in range(3):
        _outbound(db_session, conv, ghosted_at + timedelta(hours=i + 1))

    result = svc.calculate_engagement_health(db_session, "C-1", "U-ORG")
    # denominator excludes the 3 ghost-period outbound messages -- only the 1 pre-ghost outbound counts
    assert result["response_rate"] == 100

# ── days_to_qualification (TC-003) ──────────────────────────────────────

def test_days_to_qualification_populated_when_screened(db_session, candidate):
    conv = _conversation(db_session, created_at=datetime.utcnow() - timedelta(days=10))
    _outbound(db_session, conv, datetime.utcnow() - timedelta(days=9))
    _inbound(db_session, conv, datetime.utcnow() - timedelta(days=9))

    job = Jobs(jobID="J-1", jobTitle="Sr. Dev", jobDescription="d", jobSkills="[]", jobExperience="5", jobLocation="Remote")
    db_session.add(job)
    db_session.commit()
    score = CandidateJobScore(tenant_id="U-HR", candidate_id="C-1", job_id="J-1", technical_score=90, compensation_score=90, availability_score=90, overall_score=90)
    score.calculated_at = datetime.utcnow() - timedelta(days=5)
    db_session.add(score)
    db_session.commit()

    result = svc.calculate_engagement_health(db_session, "C-1", "U-ORG")
    assert result["days_to_qualification"] == 5

def test_days_to_qualification_null_when_not_screened(db_session, candidate):
    conv = _conversation(db_session)
    _outbound(db_session, conv, datetime.utcnow())

    result = svc.calculate_engagement_health(db_session, "C-1", "U-ORG")
    assert result["days_to_qualification"] is None

# ── sentiment ──────────────────────────────────────────────────────────

def test_avg_sentiment_score_computed(db_session, candidate):
    conv = _conversation(db_session)
    _outbound(db_session, conv, datetime.utcnow())
    db_session.add(CandidateSentimentLog(tenant_id="U-ORG", candidate_id="C-1", message_event_id=None, sentiment="POSITIVE", confidence=0.9))
    db_session.add(CandidateSentimentLog(tenant_id="U-ORG", candidate_id="C-1", message_event_id=None, sentiment="NEGATIVE", confidence=0.9))
    db_session.add(CandidateSentimentLog(tenant_id="U-ORG", candidate_id="C-1", message_event_id=None, sentiment="NEUTRAL", confidence=0.9))
    db_session.commit()

    result = svc.calculate_engagement_health(db_session, "C-1", "U-ORG")
    assert result["avg_sentiment_score"] == 0.0

def test_no_sentiment_data_gives_none(db_session, candidate):
    conv = _conversation(db_session)
    _outbound(db_session, conv, datetime.utcnow())

    result = svc.calculate_engagement_health(db_session, "C-1", "U-ORG")
    assert result["avg_sentiment_score"] is None

# ── upsert + not found ───────────────────────────────────────────────────

def test_recalculation_upserts_not_duplicates(db_session, candidate):
    conv = _conversation(db_session)
    _outbound(db_session, conv, datetime.utcnow())
    svc.calculate_engagement_health(db_session, "C-1", "U-ORG")
    svc.calculate_engagement_health(db_session, "C-1", "U-ORG")

    rows = db_session.query(CandidateEngagementMetrics).filter(CandidateEngagementMetrics.candidate_id == "C-1").all()
    assert len(rows) == 1

def test_candidate_not_found(db_session):
    result = svc.calculate_engagement_health(db_session, "NOPE", "U-ORG")
    assert result["outcome"] == "not_found"

# ── job batch ─────────────────────────────────────────────────────────

def test_job_processes_all_open_conversations(db_session, candidate):
    _conversation(db_session)
    result = svc.run_engagement_metrics_job(db_session)
    assert result["calculated"] == 1
