"""
S-071/HRMS-0471 -- AI Recruiter Performance Analytics.

Real architecture under test (see thunder_analytics_service module
docstring): no agent_execution_log table -- Thunder-vs-human action
split reuses the real ConversationEvent.triggered_by field
(ai_message_sent vs hr_message_sent). No conversation_state_history --
"qualified" reuses S-059's real SCREENED marker (CandidateJobScore
existing). BR-01's 20% human-dependency target verified directly.

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
from app.models.candidate_drop_risk import CandidateDropRisk
from app.models.candidate_engagement_metrics import CandidateEngagementMetrics
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.candidate_job_score import CandidateJobScore
from app.models.user import Users, Jobs

import app.services.thunder_analytics_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Jobs.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        CandidateJobScore.__table__, CandidateGhostingStatus.__table__, CandidateEngagementMetrics.__table__, CandidateDropRisk.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def seeded_hr(db_session):
    db_session.add(Users(UserID="U-HR", UserRole="HR Manager", UserEmail="hr@blitzenx.com", UserPassword="h", tenant_id=None))
    db_session.commit()


def _candidate_with_conv(db, cid, created_at):
    db.add(Candidate(candidateID=cid, candidateEmail=f"{cid.lower()}@example.com", candidatePassword="h", candidateFirstName=cid))
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id=cid, status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", created_at=created_at)
    db.add(conv)
    db.commit()
    return conv


def _job_score(db, cid, calculated_at, job_id="J-1"):
    job = Jobs(jobID=job_id, jobTitle="Sr. Dev", jobDescription="d", jobSkills="[]", jobExperience="5", jobLocation="Remote")
    db.merge(job)
    db.commit()
    score = CandidateJobScore(tenant_id="U-HR", candidate_id=cid, job_id=job_id, technical_score=90, compensation_score=90, availability_score=90, overall_score=90)
    score.calculated_at = calculated_at
    db.add(score)
    db.commit()


# ── TC-001: qualification rate ──────────────────────────────────────────

def test_qualification_rate_computed_correctly(db_session, seeded_hr):
    now = datetime.utcnow()
    for i in range(10):
        _candidate_with_conv(db_session, f"C-{i}", now - timedelta(days=5))
    for i in range(7):
        _job_score(db_session, f"C-{i}", now - timedelta(days=2))

    result = svc.get_thunder_analytics(db_session, "U-ORG", date_from=(now - timedelta(days=10)).date(), date_to=now.date())
    assert result["summary"]["qualification_rate"] == 70


# ── TC-002: human intervention rate ──────────────────────────────────────

def test_human_intervention_rate_and_thunder_pct(db_session, seeded_hr):
    conv = _candidate_with_conv(db_session, "C-1", datetime.utcnow() - timedelta(days=1))
    now = datetime.utcnow()
    for _ in range(82):
        db_session.add(ConversationEvent(conversation_id=conv.id, event_type="ai_message_sent", event_data={}, triggered_by="ai_agent", created_at=now))
    for _ in range(18):
        db_session.add(ConversationEvent(conversation_id=conv.id, event_type="hr_message_sent", event_data={}, triggered_by="hr_user", created_at=now))
    db_session.commit()

    result = svc.get_thunder_analytics(db_session, "U-ORG")
    assert result["summary"]["human_intervention_rate"] == 18.0
    assert result["agent_actions_breakdown"]["thunder_pct"] == 82.0
    assert result["summary"]["human_dependency_target_pct"] == 20


# ── Escalation / ghosting rates ──────────────────────────────────────────

def test_escalation_and_ghosting_rates(db_session, seeded_hr):
    now = datetime.utcnow()
    conv1 = _candidate_with_conv(db_session, "C-1", now - timedelta(days=1))
    _candidate_with_conv(db_session, "C-2", now - timedelta(days=1))
    db_session.add(ConversationEvent(conversation_id=conv1.id, event_type="escalation_triggered", event_data={"reason": "x"}, triggered_by="ai_agent", created_at=now))
    db_session.add(CandidateGhostingStatus(tenant_id="U-ORG", candidate_id="C-2", conversation_id=conv1.id, ghosted_at=now, is_reactivated=False))
    db_session.commit()

    result = svc.get_thunder_analytics(db_session, "U-ORG")
    assert result["summary"]["escalation_rate"] == 50.0
    assert result["summary"]["ghosting_rate"] == 50.0


# ── Engagement metrics reuse ──────────────────────────────────────────────

def test_avg_days_to_qualify_reuses_engagement_metrics(db_session, seeded_hr):
    now = datetime.utcnow()
    _candidate_with_conv(db_session, "C-1", now - timedelta(days=5))
    db_session.add(CandidateEngagementMetrics(tenant_id="U-ORG", candidate_id="C-1", response_rate=80, total_messages_exchanged=10, days_to_qualification=3))
    db_session.commit()

    result = svc.get_thunder_analytics(db_session, "U-ORG")
    assert result["summary"]["avg_days_to_qualify"] == 3.0
    assert result["summary"]["avg_messages_per_candidate"] == 10.0


# ── Top risk candidates ──────────────────────────────────────────────────

def test_top_risk_candidates_returned(db_session, seeded_hr):
    _candidate_with_conv(db_session, "C-1", datetime.utcnow())
    db_session.add(CandidateDropRisk(tenant_id="U-ORG", candidate_id="C-1", drop_risk_score=88, risk_level="CRITICAL", risk_signals={"stage": "OFFER"}, is_flagged=True))
    db_session.commit()

    result = svc.get_thunder_analytics(db_session, "U-ORG")
    assert len(result["top_risk_candidates"]) == 1
    assert result["top_risk_candidates"][0]["drop_risk_score"] == 88


# ── Trends ──────────────────────────────────────────────────────────────

def test_trends_cover_full_date_range(db_session, seeded_hr):
    today = datetime.utcnow().date()
    result = svc.get_thunder_analytics(db_session, "U-ORG", date_from=today - timedelta(days=6), date_to=today)
    assert len(result["trends"]) == 7


def test_new_candidates_counted_per_day(db_session, seeded_hr):
    now = datetime.utcnow()
    _candidate_with_conv(db_session, "C-1", now)

    result = svc.get_thunder_analytics(db_session, "U-ORG", date_from=now.date(), date_to=now.date())
    assert result["trends"][0]["new_candidates"] == 1


# ── Empty state ───────────────────────────────────────────────────────────

def test_no_active_candidates_returns_zero_rates(db_session, seeded_hr):
    result = svc.get_thunder_analytics(db_session, "U-ORG")
    assert result["summary"]["qualification_rate"] == 0
    assert result["summary"]["escalation_rate"] == 0
    assert result["top_risk_candidates"] == []
