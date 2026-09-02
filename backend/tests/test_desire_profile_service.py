"""
S-348/HRMS-P118 -- Desire Profile Builder.
Throwaway SQLite -- never the real database.
"""
import os
import tempfile
import logging
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_desire_profile import CandidateDesireProfile
from app.models.candidate_desire_signal import CandidateDesireSignal
from app.models.event_log import EventLog
from app.models.user import Users

import app.services.desire_profile_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateDesireSignal.__table__,
        CandidateDesireProfile.__table__, EventLog.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def tenant_and_candidate(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate = Candidate(candidateID="C-DP", candidateEmail="dp@example.com", candidatePassword="h")
    db_session.add_all([owner, candidate])
    db_session.commit()
    return owner, candidate


def _signal(db, tenant_id, candidate_id, *, source="CHAT_MESSAGE", category=None, direction=None, strength=None, data=None, age_days=0, processed=True):
    row = CandidateDesireSignal(
        tenant_id=tenant_id, candidate_id=candidate_id, signal_source=source,
        signal_data=data or {"message_body": "hello"}, desire_category=category, desire_direction=direction,
        desire_strength=strength, processed=processed,
        processed_at=datetime.utcnow() - timedelta(days=age_days) if processed else None,
    )
    db.add(row)
    db.commit()
    row.created_at = datetime.utcnow() - timedelta(days=age_days)
    db.commit()
    db.refresh(row)
    return row


def test_build_profile_ranks_by_score_desc(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _signal(db_session, owner.UserID, candidate.candidateID, category="CAREER_GROWTH", direction="TOWARDS", strength=0.9)
    _signal(db_session, owner.UserID, candidate.candidateID, category="COMPENSATION", direction="TOWARDS", strength=0.3)

    profile = svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)

    assert profile.top_desire_category == "CAREER_GROWTH"
    assert [r["category"] for r in profile.desire_ranking] == ["CAREER_GROWTH", "COMPENSATION"]


def test_build_profile_recency_weighting(db_session, tenant_and_candidate):
    """A fresh 0.9-strength signal (weight 1.5) should outweigh an old
    0.9-strength signal (weight 0.5) mixed with a fresh low one."""
    owner, candidate = tenant_and_candidate
    _signal(db_session, owner.UserID, candidate.candidateID, category="CAREER_GROWTH", direction="TOWARDS", strength=0.9, age_days=1)
    _signal(db_session, owner.UserID, candidate.candidateID, category="CAREER_GROWTH", direction="TOWARDS", strength=0.1, age_days=60)

    profile = svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)
    entry = profile.desire_ranking[0]
    # weighted avg = (0.9*1.5 + 0.1*0.5) / (1.5+0.5) = 1.4/2 = 0.7
    assert entry["score"] == pytest.approx(0.7, abs=0.01)
    assert entry["signal_count"] == 2


def test_primary_fear_from_away_from_signals(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _signal(db_session, owner.UserID, candidate.candidateID, category="STABILITY", direction="AWAY_FROM", strength=0.8)
    _signal(db_session, owner.UserID, candidate.candidateID, category="CAREER_GROWTH", direction="TOWARDS", strength=0.5)

    profile = svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)

    assert profile.primary_fear == "STABILITY"
    assert profile.primary_fear_score == pytest.approx(0.8, abs=0.01)
    # AWAY_FROM signals must not pollute the TOWARDS ranking
    assert all(r["category"] != "STABILITY" for r in profile.desire_ranking)


@pytest.mark.parametrize("minutes,expected_level", [(30, "HOT"), (300, "WARM"), (1500, "COOL"), (3500, "COLD")])
def test_engagement_level_thresholds(db_session, tenant_and_candidate, minutes, expected_level):
    owner, candidate = tenant_and_candidate
    _signal(db_session, owner.UserID, candidate.candidateID, source="RESPONSE_SPEED", data={"minutes": minutes})

    profile = svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)
    assert profile.engagement_level == expected_level


def test_no_response_speed_signals_leaves_engagement_level_null(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    profile = svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)
    assert profile.engagement_level is None


def test_competing_offer_keyword_forces_urgent_regardless_of_trend(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _signal(db_session, owner.UserID, candidate.candidateID, source="CHAT_MESSAGE", data={"message_body": "I have another offer I'm considering"})
    # slow-trending response speed, which alone would be SLOW not URGENT
    for i, minutes in enumerate([10, 10, 100, 100]):
        _signal(db_session, owner.UserID, candidate.candidateID, source="RESPONSE_SPEED", data={"minutes": minutes})

    profile = svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)

    assert profile.has_competing_offer is True
    assert profile.decision_urgency == "URGENT"


def test_decision_urgency_speeding_up_is_urgent(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    for minutes in [100, 100, 10, 10]:
        _signal(db_session, owner.UserID, candidate.candidateID, source="RESPONSE_SPEED", data={"minutes": minutes})

    profile = svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)
    assert profile.decision_urgency == "URGENT"


def test_decision_urgency_slowing_down_is_slow(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    for minutes in [10, 10, 100, 100]:
        _signal(db_session, owner.UserID, candidate.candidateID, source="RESPONSE_SPEED", data={"minutes": minutes})

    profile = svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)
    assert profile.decision_urgency == "SLOW"


def test_decision_urgency_insufficient_data_is_normal(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _signal(db_session, owner.UserID, candidate.candidateID, source="RESPONSE_SPEED", data={"minutes": 30})

    profile = svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)
    assert profile.decision_urgency == "NORMAL"


def test_unprocessed_signals_are_ignored(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _signal(db_session, owner.UserID, candidate.candidateID, category="CAREER_GROWTH", direction="TOWARDS", strength=0.9, processed=False)

    profile = svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)
    assert profile.top_desire_category is None
    assert profile.desire_ranking == []


def test_build_upserts_not_duplicates(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _signal(db_session, owner.UserID, candidate.candidateID, category="CAREER_GROWTH", direction="TOWARDS", strength=0.5)
    svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)
    svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)

    assert db_session.query(CandidateDesireProfile).filter(CandidateDesireProfile.candidate_id == candidate.candidateID).count() == 1


def test_build_emits_profile_updated_and_shift_detected_events(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _signal(db_session, owner.UserID, candidate.candidateID, category="CAREER_GROWTH", direction="TOWARDS", strength=0.9)
    svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)

    _signal(db_session, owner.UserID, candidate.candidateID, category="COMPENSATION", direction="TOWARDS", strength=0.99)
    svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)

    events = db_session.query(EventLog).filter(EventLog.candidate_id == candidate.candidateID).all()
    event_types = [e.event_type for e in events]
    assert event_types.count("candidate.desire_profile_updated") == 2
    assert "candidate.desire_shift_detected" in event_types


def test_build_emits_competing_offer_event_only_once(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _signal(db_session, owner.UserID, candidate.candidateID, source="CHAT_MESSAGE", data={"message_body": "I have another offer"})
    svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)
    svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)  # still competing -- must not re-fire

    events = db_session.query(EventLog).filter(EventLog.event_type == "candidate.competing_offer_detected").all()
    assert len(events) == 1


# ---------------------------------------------------------------------------
# Narrative generation -- fail-soft
# ---------------------------------------------------------------------------

def test_generate_narrative_success(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _signal(db_session, owner.UserID, candidate.candidateID, category="CAREER_GROWTH", direction="TOWARDS", strength=0.9)
    profile = svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)

    narrative = svc.generate_desire_narrative(db_session, profile, llm_call=lambda p: "Paragraph 1...\n\nParagraph 2...\n\nParagraph 3...")
    assert narrative.startswith("Paragraph 1")


def test_generate_narrative_fails_soft(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    profile = svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)

    def _broken(prompt):
        raise RuntimeError("simulated LLM outage")

    narrative = svc.generate_desire_narrative(db_session, profile, llm_call=_broken)
    assert narrative is None


# ---------------------------------------------------------------------------
# DesireProfileUpdateJob
# ---------------------------------------------------------------------------

def test_update_job_picks_up_candidate_with_new_signals(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _signal(db_session, owner.UserID, candidate.candidateID, category="CAREER_GROWTH", direction="TOWARDS", strength=0.9)

    result = svc.run_desire_profile_update_job(db_session, llm_call=lambda p: "narrative")

    assert result["updated"] == 1
    profile = db_session.query(CandidateDesireProfile).filter(CandidateDesireProfile.candidate_id == candidate.candidateID).first()
    assert profile is not None
    assert profile.narrative_summary == "narrative"


def test_update_job_skips_candidate_already_current(db_session, tenant_and_candidate):
    owner, candidate = tenant_and_candidate
    _signal(db_session, owner.UserID, candidate.candidateID, category="CAREER_GROWTH", direction="TOWARDS", strength=0.9)
    svc.build_desire_profile(db_session, owner.UserID, candidate.candidateID)

    result = svc.run_desire_profile_update_job(db_session, llm_call=lambda p: "narrative")

    assert result["candidates_due"] == 0
