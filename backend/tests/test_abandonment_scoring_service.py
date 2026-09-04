"""
import logging
S-046/HRMS-0446 -- Candidate Abandonment Prediction.

Real architecture under test (see abandonment_scoring_service module
docstring): pure formula, not ML; response rate/sentiment trend/days
since last reply/follow-up count, 30/25/25/20 weighted; BR-02 eligible
conversations use the same 3-condition filter (owner_type='ai_agent',
status!='closed', escalation_state!='escalated') S-041/S-042 already
established for the identical spec language; no event bus -- is_flagged
on the row itself is the real signal, with a recruiter notified once on
the newly-flagged transition only.

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
from app.models.candidate_abandonment_score import CandidateAbandonmentScore
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.candidate_sentiment_log import CandidateSentimentLog
from app.models.follow_up_schedule import FollowUpSchedule
from app.models.notification import Notification
from app.models.user import Users

import app.services.abandonment_scoring_service as svc

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        CandidateAbandonmentScore.__table__, CandidateSentimentLog.__table__, FollowUpSchedule.__table__,
        CandidateAIAssignment.__table__, Notification.__table__,
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
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya", candidateMobile="+919876543210")
    db_session.add_all([owner, candidate])
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp", created_at=datetime.utcnow() - timedelta(days=20))
    db_session.add(conv)
    db_session.commit()
    return candidate, conv

def _add_events(db_session, conv, ai_count, reply_count, *, within_days=7):
    now = datetime.utcnow()
    for i in range(ai_count):
        db_session.add(ConversationEvent(conversation_id=conv.id, event_type="ai_message_sent", event_data={}, triggered_by="ai_agent", created_at=now - timedelta(days=1, hours=i)))
    for i in range(reply_count):
        db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={}, triggered_by="candidate", created_at=now - timedelta(hours=i + 1)))
    db_session.commit()

def _add_sentiments(db_session, sentiments):
    now = datetime.utcnow()
    for i, s in enumerate(sentiments):
        db_session.add(CandidateSentimentLog(tenant_id="U-ORG", candidate_id="C-1", conversation_id=1, sentiment=s, confidence=0.9, analyzed_at=now - timedelta(hours=i)))
    db_session.commit()

# ── AC-1: returns 0-100 integer, upserts ─────────────────────────────

def test_returns_score_in_range_and_persists(db_session, seeded):
    candidate, conv = seeded
    result = svc.calculate_abandonment_score(db_session, "C-1", "U-ORG", conv)
    assert 0 <= result["abandonment_score"] <= 100
    assert isinstance(result["abandonment_score"], int)

    row = db_session.query(CandidateAbandonmentScore).filter(CandidateAbandonmentScore.candidate_id == "C-1").first()
    assert row is not None
    assert row.abandonment_score == result["abandonment_score"]

def test_recalculation_upserts_not_duplicates(db_session, seeded):
    candidate, conv = seeded
    svc.calculate_abandonment_score(db_session, "C-1", "U-ORG", conv)
    svc.calculate_abandonment_score(db_session, "C-1", "U-ORG", conv)

    rows = db_session.query(CandidateAbandonmentScore).filter(CandidateAbandonmentScore.candidate_id == "C-1").all()
    assert len(rows) == 1

# ── AC-2 / TC-001: worst case -> score >= 70, flagged ─────────────────

def test_worst_case_flags_high_risk(db_session, seeded):
    candidate, conv = seeded
    conv.created_at = datetime.utcnow() - timedelta(days=30)
    db_session.commit()

    _add_events(db_session, conv, ai_count=3, reply_count=0)  # 0% response rate over last 7 days
    _add_sentiments(db_session, ["NEGATIVE"] * 5)  # all negative
    for i in range(3):
        db_session.add(FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=datetime.utcnow(), status="SENT", follow_up_number=i + 1))
    db_session.commit()

    result = svc.calculate_abandonment_score(db_session, "C-1", "U-ORG", conv)
    assert result["abandonment_score"] >= 70
    assert result["is_flagged"] is True

# ── AC-3 / TC-002: best case -> score near 0, not flagged ─────────────

def test_best_case_scores_near_zero(db_session, seeded):
    candidate, conv = seeded
    _add_events(db_session, conv, ai_count=3, reply_count=3)  # 100% response rate
    db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "candidate_reply").update({"created_at": datetime.utcnow()})
    db_session.commit()
    _add_sentiments(db_session, ["POSITIVE"] * 5)

    result = svc.calculate_abandonment_score(db_session, "C-1", "U-ORG", conv)
    assert result["abandonment_score"] <= 10
    assert result["is_flagged"] is False

# ── Component-level checks ────────────────────────────────────────────

def test_no_outbound_yet_scores_zero_response_rate_points(db_session, seeded):
    candidate, conv = seeded
    pts = svc._response_rate_points(db_session, conv.id, datetime.utcnow())
    assert pts == 0

def test_no_sentiment_data_treated_as_neutral(db_session, seeded):
    candidate, conv = seeded
    pts = svc._sentiment_trend_points(db_session, "C-1")
    assert pts == 0

def test_mixed_sentiment_scores_middle_points(db_session, seeded):
    candidate, conv = seeded
    _add_sentiments(db_session, ["POSITIVE", "NEGATIVE", "POSITIVE", "NEGATIVE", "POSITIVE"])
    pts = svc._sentiment_trend_points(db_session, "C-1")
    assert pts == 5

def test_three_negatives_not_all_scores_15(db_session, seeded):
    candidate, conv = seeded
    _add_sentiments(db_session, ["NEGATIVE", "NEGATIVE", "NEGATIVE", "POSITIVE", "POSITIVE"])
    pts = svc._sentiment_trend_points(db_session, "C-1")
    assert pts == 15

def test_followup_count_points_scale(db_session, seeded):
    candidate, conv = seeded
    assert svc._followup_count_points(db_session, "U-ORG", "C-1", conv.id) == 0

    db_session.add(FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=datetime.utcnow(), status="SENT", follow_up_number=1))
    db_session.commit()
    assert svc._followup_count_points(db_session, "U-ORG", "C-1", conv.id) == 5

    db_session.add(FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=datetime.utcnow(), status="SENT", follow_up_number=2))
    db_session.commit()
    assert svc._followup_count_points(db_session, "U-ORG", "C-1", conv.id) == 12

    db_session.add(FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=datetime.utcnow(), status="SENT", follow_up_number=3))
    db_session.commit()
    assert svc._followup_count_points(db_session, "U-ORG", "C-1", conv.id) == 20

def test_days_since_last_reply_falls_back_to_conversation_created_at_when_never_replied(db_session, seeded):
    candidate, conv = seeded
    conv.created_at = datetime.utcnow() - timedelta(days=15)
    db_session.commit()
    pts = svc._days_since_last_reply_points(db_session, conv, datetime.utcnow())
    assert pts == 25  # 10+ days

def test_days_since_last_reply_uses_most_recent_reply_event(db_session, seeded):
    candidate, conv = seeded
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={}, triggered_by="candidate", created_at=datetime.utcnow() - timedelta(days=4)))
    db_session.commit()
    pts = svc._days_since_last_reply_points(db_session, conv, datetime.utcnow())
    assert pts == 15  # 3-5 days

# ── AC-5 / TC-003: job scores all eligible conversations ─────────────

def test_job_scores_all_eligible_conversations(db_session, seeded):
    candidate, conv = seeded
    result = svc.run_abandonment_scoring_job(db_session)
    assert result["scored"] == 1

def test_job_skips_recruiter_owned_conversation(db_session, seeded):
    candidate, conv = seeded
    conv.owner_type = "hr_user"
    conv.owner_id = "U-RECRUITER"
    db_session.commit()

    result = svc.run_abandonment_scoring_job(db_session)
    assert result["scored"] == 0

def test_job_skips_closed_conversation(db_session, seeded):
    candidate, conv = seeded
    conv.status = "closed"
    db_session.commit()

    result = svc.run_abandonment_scoring_job(db_session)
    assert result["scored"] == 0

def test_job_skips_escalated_conversation(db_session, seeded):
    candidate, conv = seeded
    conv.escalation_state = "escalated"
    db_session.commit()

    result = svc.run_abandonment_scoring_job(db_session)
    assert result["scored"] == 0

def test_job_never_raises_on_bad_conversation(db_session, seeded, monkeypatch):
    candidate, conv = seeded

    def _boom(db, cand_id, tenant_id, conversation):
        raise RuntimeError("simulated failure")
    monkeypatch.setattr(svc, "calculate_abandonment_score", _boom)

    result = svc.run_abandonment_scoring_job(db_session)  # should not raise
    assert result["scored"] == 0

# ── BR-01: notification fires once, only on the newly-flagged transition ─

def test_job_notifies_recruiter_only_on_newly_flagged_transition(db_session, seeded):
    candidate, conv = seeded
    conv.created_at = datetime.utcnow() - timedelta(days=30)
    _add_events(db_session, conv, ai_count=3, reply_count=0)
    _add_sentiments(db_session, ["NEGATIVE"] * 5)
    for i in range(3):
        db_session.add(FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=datetime.utcnow(), status="SENT", follow_up_number=i + 1))
    db_session.commit()

    svc.run_abandonment_scoring_job(db_session)
    notifications_after_first = db_session.query(Notification).all()
    assert len(notifications_after_first) == 1

    svc.run_abandonment_scoring_job(db_session)  # still flagged, should NOT notify again
    notifications_after_second = db_session.query(Notification).all()
    assert len(notifications_after_second) == 1
