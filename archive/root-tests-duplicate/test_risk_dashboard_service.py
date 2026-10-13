"""
S-063/HRMS-0463 -- Candidate Risk Dashboard.

Real architecture under test (see risk_dashboard_service module
docstring): BR-01's "exclude COMPLETED/WITHDRAWN" maps to real
conversation.status=='closed' filtering (WITHDRAWN) -- COMPLETED
(JOINED) is already excluded by construction since S-060 never scores
a JOINED candidate. stage/top_risk_signal are read directly from
CandidateDropRisk.risk_signals (S-060's own real shape), no
recomputation.

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
from app.models.candidate_ai import CandidateConversation
from app.models.candidate_drop_risk import CandidateDropRisk
from app.models.candidate_sentiment_log import CandidateSentimentLog
from app.models.user import Users

import app.services.risk_dashboard_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__,
        CandidateDropRisk.__table__, CandidateSentimentLog.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _candidate(db, cid, first="Priya"):
    db.add(Candidate(candidateID=cid, candidateEmail=f"{cid.lower()}@example.com", candidatePassword="h", candidateFirstName=first))
    db.commit()


def _conversation(db, cid, status="open"):
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id=cid, status=status, owner_type="ai_agent", owner_id="Thunder", escalation_state="none")
    db.add(conv)
    db.commit()
    return conv


def _drop_risk(db, cid, score, level, stage, signals=None):
    row = CandidateDropRisk(tenant_id="U-ORG", candidate_id=cid, drop_risk_score=score, risk_level=level, risk_signals={"stage": stage, **(signals or {})}, is_flagged=score >= 70)
    db.add(row)
    db.commit()
    return row


@pytest.fixture()
def seeded_hr(db_session):
    db_session.add(Users(UserID="U-HR", UserRole="HR Manager", UserEmail="hr@blitzenx.com", UserPassword="h", tenant_id=None))
    db_session.commit()


# ── TC-001: dashboard structure ─────────────────────────────────────────

def test_dashboard_returns_all_sections(db_session, seeded_hr):
    _candidate(db_session, "C-1")
    _conversation(db_session, "C-1")
    _drop_risk(db_session, "C-1", 65, "HIGH", "INTERVIEW")

    result = svc.get_risk_dashboard(db_session, "U-ORG")
    assert set(result.keys()) == {"risk_summary", "candidates_at_risk", "sentiment_trend", "stage_risk_breakdown"}
    assert len(result["sentiment_trend"]) == 14


# ── TC-002: sorted DESC ──────────────────────────────────────────────────

def test_candidates_at_risk_sorted_desc(db_session, seeded_hr):
    for cid, score in [("C-1", 87), ("C-2", 43), ("C-3", 65)]:
        _candidate(db_session, cid)
        _conversation(db_session, cid)
        _drop_risk(db_session, cid, score, "HIGH", "OFFER")

    result = svc.get_risk_dashboard(db_session, "U-ORG")
    scores = [c["drop_risk_score"] for c in result["candidates_at_risk"]]
    assert scores == [87, 65, 43]


def test_below_threshold_excluded_from_at_risk_list(db_session, seeded_hr):
    _candidate(db_session, "C-1")
    _conversation(db_session, "C-1")
    _drop_risk(db_session, "C-1", 35, "LOW", "QUALIFYING")

    result = svc.get_risk_dashboard(db_session, "U-ORG")
    assert result["candidates_at_risk"] == []
    assert result["risk_summary"]["low_count"] == 1  # still counted in summary


# ── TC-004: BR-01 exclusions ──────────────────────────────────────────────

def test_closed_conversation_excluded_withdrawn_proxy(db_session, seeded_hr):
    _candidate(db_session, "C-1")
    _conversation(db_session, "C-1", status="closed")
    _drop_risk(db_session, "C-1", 90, "CRITICAL", "OFFER")

    result = svc.get_risk_dashboard(db_session, "U-ORG")
    assert result["candidates_at_risk"] == []
    assert result["risk_summary"]["critical_count"] == 0


def test_open_conversation_included(db_session, seeded_hr):
    _candidate(db_session, "C-1")
    _conversation(db_session, "C-1", status="open")
    _drop_risk(db_session, "C-1", 90, "CRITICAL", "OFFER")

    result = svc.get_risk_dashboard(db_session, "U-ORG")
    assert len(result["candidates_at_risk"]) == 1


# ── Top risk signal derivation ───────────────────────────────────────────

def test_top_risk_signal_picks_highest_contributor(db_session, seeded_hr):
    _candidate(db_session, "C-1")
    _conversation(db_session, "C-1")
    _drop_risk(db_session, "C-1", 70, "HIGH", "PREBOARDING", signals={"readiness_points": 49, "readiness_score": 30, "days_silent_points": 15})

    result = svc.get_risk_dashboard(db_session, "U-ORG")
    assert "30%" in result["candidates_at_risk"][0]["top_risk_signal"]


# ── Stage risk breakdown ─────────────────────────────────────────────────

def test_stage_risk_breakdown_averages_correctly(db_session, seeded_hr):
    for cid, score, stage in [("C-1", 60, "INTERVIEW"), ("C-2", 80, "INTERVIEW"), ("C-3", 40, "OFFER")]:
        _candidate(db_session, cid)
        _conversation(db_session, cid)
        _drop_risk(db_session, cid, score, "HIGH", stage)

    result = svc.get_risk_dashboard(db_session, "U-ORG")
    by_stage = {row["stage"]: row for row in result["stage_risk_breakdown"]}
    assert by_stage["INTERVIEW"]["avg_risk_score"] == 70
    assert by_stage["INTERVIEW"]["candidate_count"] == 2
    assert by_stage["OFFER"]["avg_risk_score"] == 40


# ── Sentiment trend ────────────────────────────────────────────────────

def test_sentiment_trend_computes_daily_percentages(db_session, seeded_hr):
    _candidate(db_session, "C-1")
    today = datetime.utcnow()
    db_session.add(CandidateSentimentLog(tenant_id="U-ORG", candidate_id="C-1", message_event_id=None, sentiment="POSITIVE", confidence=0.9, analyzed_at=today))
    db_session.add(CandidateSentimentLog(tenant_id="U-ORG", candidate_id="C-1", message_event_id=None, sentiment="POSITIVE", confidence=0.9, analyzed_at=today))
    db_session.add(CandidateSentimentLog(tenant_id="U-ORG", candidate_id="C-1", message_event_id=None, sentiment="NEGATIVE", confidence=0.9, analyzed_at=today))
    db_session.commit()

    result = svc.get_risk_dashboard(db_session, "U-ORG")
    today_point = result["sentiment_trend"][-1]
    assert today_point["avg_positive_pct"] == 67
    assert today_point["avg_negative_pct"] == 33


def test_sentiment_outside_14_days_excluded(db_session, seeded_hr):
    _candidate(db_session, "C-1")
    old = datetime.utcnow() - timedelta(days=20)
    db_session.add(CandidateSentimentLog(tenant_id="U-ORG", candidate_id="C-1", message_event_id=None, sentiment="NEGATIVE", confidence=0.9, analyzed_at=old))
    db_session.commit()

    result = svc.get_risk_dashboard(db_session, "U-ORG")
    assert all(p["avg_positive_pct"] == 0 and p["avg_negative_pct"] == 0 for p in result["sentiment_trend"])


def test_multiple_conversations_uses_most_recent(db_session, seeded_hr):
    _candidate(db_session, "C-1")
    _conversation(db_session, "C-1", status="closed")
    _conversation(db_session, "C-1", status="open")  # most recent, re-engaged
    _drop_risk(db_session, "C-1", 75, "HIGH", "QUALIFYING")

    result = svc.get_risk_dashboard(db_session, "U-ORG")
    assert len(result["candidates_at_risk"]) == 1  # uses the OPEN (most recent) conversation
