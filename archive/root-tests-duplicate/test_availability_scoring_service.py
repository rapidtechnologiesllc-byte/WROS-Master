"""
S-039/HRMS-0439 -- Availability Score.

Real architecture under test (see availability_scoring_service module
docstring): candidates.notice_period_days doesn't exist -- read from
candidate_memory_facts (category=AVAILABILITY, key=notice_period_days)
and always run through response_parser_service.normalize_notice_period_days()
since the only live producer stores raw strings; jobs.startDate is the
real equivalent of required_start_date; jobs.urgency is genuinely new;
BR-01 null notice period -> neutral 50; BR-02 FLEXIBLE never reaches
100 even at 0 notice; boundary ambiguity resolved per TC-002 ("+"
tiers are strictly-greater-than); score_breakdown flat-merges with the
other two scoring services, never overwrites.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateJobApplication
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_memory import CandidateMemory, CandidateMemoryFact
from app.models.candidate_resume_parsed import CandidateResumeParsed
from app.models.candidate_skill_tag import CandidateSkillTag
from app.models.user import Jobs, Users

import app.services.availability_scoring_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, Jobs.__table__, CandidateJobApplication.__table__,
        CandidateJobScore.__table__, CandidateMemory.__table__, CandidateMemoryFact.__table__,
        CandidateResumeParsed.__table__, CandidateSkillTag.__table__,
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
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    job = Jobs(jobID="J-1", jobTitle="Guidewire Developer", jobDescription="d", jobSkills="Guidewire", jobExperience="5+ years", jobLocation="Bangalore")
    db_session.add_all([owner, candidate, job])
    db_session.commit()
    return candidate, job


def _kolkata_today():
    """Matches the service's own _local_today("Asia/Kolkata") exactly --
    candidate.timezone defaults to Asia/Kolkata, and using plain
    date.today() (the TEST RUNNER's system-local date) here would be
    flaky whenever the test machine's local date and Kolkata's current
    date differ near a day boundary."""
    return datetime.now(dt_timezone.utc).astimezone(ZoneInfo("Asia/Kolkata")).date()


def _set_notice(db_session, raw_value):
    db_session.add(CandidateMemoryFact(tenant_id="U-ORG", candidate_id="C-1", fact_category="AVAILABILITY", fact_key="notice_period_days", fact_value=raw_value, confidence=0.9))
    db_session.commit()


# ── TC-001/TC-002: IMMEDIATE urgency ────────────────────────────────

def test_immediate_zero_notice_scores_100(db_session, seeded):
    candidate, job = seeded
    job.urgency = "IMMEDIATE"
    db_session.commit()
    _set_notice(db_session, "0 days")

    result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["availability_score"] == 100


def test_immediate_sixty_days_notice_scores_30(db_session, seeded):
    """TC-002: resolves the 31-60/60+ boundary ambiguity -- 60 itself
    falls in the inclusive 31-60 bucket (30), not the '60+' bucket."""
    candidate, job = seeded
    job.urgency = "IMMEDIATE"
    db_session.commit()
    _set_notice(db_session, "60 days")

    result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["availability_score"] == 30


def test_immediate_sixty_one_days_notice_scores_10(db_session, seeded):
    candidate, job = seeded
    job.urgency = "IMMEDIATE"
    db_session.commit()
    _set_notice(db_session, "61 days")
    result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["availability_score"] == 10


def test_immediate_boundary_tiers(db_session, seeded):
    candidate, job = seeded
    job.urgency = "IMMEDIATE"
    db_session.commit()
    for notice, expected in [(1, 85), (14, 85), (15, 60), (30, 60), (31, 30)]:
        db_session.query(CandidateMemoryFact).delete()
        db_session.commit()
        _set_notice(db_session, f"{notice} days")
        result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
        assert result["availability_score"] == expected, f"notice={notice}"


# ── TC-003: NORMAL urgency ───────────────────────────────────────────

def test_normal_thirty_days_notice_scores_100(db_session, seeded):
    candidate, job = seeded
    job.urgency = "NORMAL"
    db_session.commit()
    _set_notice(db_session, "30 days")

    result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["availability_score"] == 100


def test_normal_boundary_tiers(db_session, seeded):
    candidate, job = seeded
    job.urgency = "NORMAL"
    db_session.commit()
    for notice, expected in [(60, 100), (61, 80), (90, 80), (91, 50)]:
        db_session.query(CandidateMemoryFact).delete()
        db_session.commit()
        _set_notice(db_session, f"{notice} days")
        result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
        assert result["availability_score"] == expected, f"notice={notice}"


# ── HIGH urgency (narrated, no direct AC/TC, still built per formula) ──

def test_high_boundary_tiers(db_session, seeded):
    candidate, job = seeded
    job.urgency = "HIGH"
    db_session.commit()
    for notice, expected in [(30, 100), (31, 70), (60, 70), (61, 40)]:
        db_session.query(CandidateMemoryFact).delete()
        db_session.commit()
        _set_notice(db_session, f"{notice} days")
        result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
        assert result["availability_score"] == expected, f"notice={notice}"


# ── BR-02: FLEXIBLE never reaches 100, even at 0 notice ──────────────

def test_flexible_zero_notice_scores_90_not_100(db_session, seeded):
    candidate, job = seeded
    job.urgency = "FLEXIBLE"
    db_session.commit()
    _set_notice(db_session, "0 days")

    result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["availability_score"] == 90


def test_flexible_long_notice_still_scores_90(db_session, seeded):
    candidate, job = seeded
    job.urgency = "FLEXIBLE"
    db_session.commit()
    _set_notice(db_session, "365 days")

    result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["availability_score"] == 90


# ── start_date branch (narrated, no direct AC/TC, still built per formula) ──

def test_start_date_within_notice_scores_100(db_session, seeded):
    candidate, job = seeded
    job.startDate = _kolkata_today() + timedelta(days=30)
    db_session.commit()
    _set_notice(db_session, "20 days")

    result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["availability_score"] == 100
    assert result["score_breakdown"]["branch"] == "start_date"


def test_start_date_over_by_boundary_tiers(db_session, seeded):
    candidate, job = seeded
    job.startDate = _kolkata_today() + timedelta(days=10)  # days_until_start = 10
    db_session.commit()
    # notice=24 -> over by 14 -> 70; notice=25 -> over by 15 -> 40; notice=40 -> over by 30 -> 40; notice=41 -> over by 31 -> 15
    for notice, expected in [(10, 100), (24, 70), (25, 40), (40, 40), (41, 15)]:
        db_session.query(CandidateMemoryFact).delete()
        db_session.commit()
        _set_notice(db_session, f"{notice} days")
        result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
        assert result["availability_score"] == expected, f"notice={notice}"


def test_start_date_takes_priority_over_urgency(db_session, seeded):
    """Step 1: required_start_date branch is used when set, urgency is
    the fallback only when no start date exists."""
    candidate, job = seeded
    job.startDate = _kolkata_today() + timedelta(days=100)
    job.urgency = "IMMEDIATE"  # would score very differently if this were used instead
    db_session.commit()
    _set_notice(db_session, "10 days")

    result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["availability_score"] == 100
    assert result["score_breakdown"]["branch"] == "start_date"


# ── TC-004 / BR-01: null notice period -> neutral 50 ────────────────

def test_null_notice_period_scores_50_neutral(db_session, seeded):
    candidate, job = seeded
    job.urgency = "IMMEDIATE"
    db_session.commit()
    result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["availability_score"] == 50


def test_unparseable_notice_period_scores_50_neutral(db_session, seeded):
    candidate, job = seeded
    job.urgency = "IMMEDIATE"
    db_session.commit()
    _set_notice(db_session, "whenever works")  # no number

    result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["availability_score"] == 50


def test_no_start_date_and_no_urgency_scores_50_neutral(db_session, seeded):
    """No documented AC/TC for this case -- implemented as 'no
    comparison point available', same posture as S-038's no-budget-set case."""
    candidate, job = seeded
    _set_notice(db_session, "10 days")
    result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["availability_score"] == 50
    assert result["score_breakdown"]["branch"] == "no_comparison_point"


# ── score stored with breakdown ─────────────────────────────────────

def test_score_stored_with_breakdown(db_session, seeded):
    candidate, job = seeded
    job.urgency = "NORMAL"
    db_session.commit()
    _set_notice(db_session, "30 days")

    svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
    db_session.commit()

    row = db_session.query(CandidateJobScore).filter(CandidateJobScore.candidate_id == "C-1", CandidateJobScore.job_id == "J-1").first()
    assert row.availability_score == 100
    assert row.score_breakdown["notice_period_days"] == 30
    assert row.score_breakdown["urgency_used"] == "NORMAL"


# ── score_breakdown merge (not overwrite) with the other 2 scoring services ─

def test_score_breakdown_merges_with_existing_technical_and_compensation_data(db_session, seeded):
    candidate, job = seeded
    job.urgency = "NORMAL"
    existing = CandidateJobScore(
        tenant_id="U-ORG", candidate_id="C-1", job_id="J-1", technical_score=85, compensation_score=100,
        score_breakdown={"skill_match_pct": 100, "expected_ctc_paise": 1800000},
    )
    db_session.add(existing)
    db_session.commit()
    _set_notice(db_session, "30 days")

    result = svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")

    assert result["technical_score"] == 85  # untouched
    assert result["compensation_score"] == 100  # untouched
    assert result["score_breakdown"]["skill_match_pct"] == 100  # preserved
    assert result["score_breakdown"]["expected_ctc_paise"] == 1800000  # preserved
    assert result["score_breakdown"]["notice_period_days"] == 30  # this service's own key added


def test_availability_rescore_does_not_erase_other_scores_data(db_session, seeded):
    """The reverse direction -- an availability rescore must not wipe
    out technical/compensation keys either."""
    import app.services.technical_scoring_service as tech_svc

    candidate, job = seeded
    job.urgency = "NORMAL"
    db_session.commit()
    tech_svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    _set_notice(db_session, "30 days")
    svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")
    svc.calculate_availability_score(db_session, "C-1", "J-1", "U-ORG")  # recalculate again

    row = db_session.query(CandidateJobScore).filter(CandidateJobScore.candidate_id == "C-1", CandidateJobScore.job_id == "J-1").first()
    assert "skill_match_pct" in row.score_breakdown
    assert "notice_period_days" in row.score_breakdown


# ── recalculate_for_candidate() ─────────────────────────────────────

def test_recalculate_for_candidate_scores_linked_job(db_session, seeded):
    candidate, job = seeded
    candidate.job_id = "J-1"
    job.urgency = "IMMEDIATE"
    db_session.commit()
    _set_notice(db_session, "0 days")

    results = svc.recalculate_for_candidate(db_session, candidate, "U-ORG")
    assert len(results) == 1
    assert results[0]["availability_score"] == 100


def test_recalculate_for_candidate_never_raises(db_session, seeded, monkeypatch):
    candidate, job = seeded
    candidate.job_id = "J-1"
    db_session.commit()

    def _boom(db, cid, jid, tid):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(svc, "calculate_availability_score", _boom)
    results = svc.recalculate_for_candidate(db_session, candidate, "U-ORG")
    assert results == []


def test_unknown_candidate_raises(db_session, seeded):
    with pytest.raises(svc.CandidateNotFound):
        svc.calculate_availability_score(db_session, "NOPE", "J-1", "U-ORG")


def test_unknown_job_raises(db_session, seeded):
    with pytest.raises(svc.JobNotFound):
        svc.calculate_availability_score(db_session, "C-1", "NOPE", "U-ORG")
