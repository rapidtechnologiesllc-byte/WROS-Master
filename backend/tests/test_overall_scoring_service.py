"""
import logging
S-040/HRMS-0440 -- Overall Candidate Score & Ranking.

Real architecture under test (see overall_scoring_service module
docstring): weights are 40/30/20/10 (technical/compensation/
availability/resume_completeness) per the docx's self-consistent
formula, NOT the xlsx summary's "communication" artifact; missing
component scores are calculated first, then combined; score_breakdown
flat-merges with the other three scoring services, never overwrites;
BR-03 rank is computed on read, never stored.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

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

import app.services.overall_scoring_service as svc


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
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya", candidateLastName="Sharma", resume_completeness_score=70)
    job = Jobs(jobID="J-1", jobTitle="Guidewire Developer", jobDescription="d", jobSkills="Guidewire", jobExperience="5+ years", jobLocation="Bangalore")
    db_session.add_all([owner, candidate, job])
    db_session.commit()
    return candidate, job


def _seed_scores(db_session, *, technical=80, compensation=100, availability=90):
    row = CandidateJobScore(tenant_id="U-ORG", candidate_id="C-1", job_id="J-1", technical_score=technical, compensation_score=compensation, availability_score=availability, score_breakdown={})
    db_session.add(row)
    db_session.commit()
    return row


# ── TC-001: weighted formula ─────────────────────────────────────────

def test_weighted_formula_matches_worked_example(db_session, seeded):
    """TC-001: technical=80, compensation=100, availability=90, resume=70
    -> ROUND(32+30+18+7) = 87."""
    candidate, job = seeded
    _seed_scores(db_session, technical=80, compensation=100, availability=90)

    result = svc.calculate_overall_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["overall_score"] == 87


def test_weights_are_40_30_20_10(db_session, seeded):
    candidate, job = seeded
    _seed_scores(db_session, technical=80, compensation=100, availability=90)
    result = svc.calculate_overall_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["score_breakdown"]["weights"] == {"technical": 0.40, "compensation": 0.30, "availability": 0.20, "resume_completeness": 0.10}


def test_resume_completeness_score_read_from_candidate(db_session, seeded):
    candidate, job = seeded
    _seed_scores(db_session)
    result = svc.calculate_overall_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["score_breakdown"]["resume_completeness_score"] == 70


def test_null_resume_completeness_treated_as_zero(db_session, seeded):
    candidate, job = seeded
    candidate.resume_completeness_score = None
    db_session.commit()
    _seed_scores(db_session, technical=100, compensation=100, availability=100)

    result = svc.calculate_overall_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["overall_score"] == 90  # 40+30+20+0


# ── missing components calculated first ─────────────────────────────

def test_missing_components_are_calculated_before_combining(db_session, seeded):
    candidate, job = seeded  # no CandidateJobScore row exists yet at all
    result = svc.calculate_overall_score(db_session, "C-1", "J-1", "U-ORG")

    assert result["technical_score"] is not None
    assert result["compensation_score"] is not None
    assert result["availability_score"] is not None
    assert result["overall_score"] is not None


def test_partially_missing_component_is_calculated(db_session, seeded):
    candidate, job = seeded
    # technical_score present, compensation/availability missing.
    row = CandidateJobScore(tenant_id="U-ORG", candidate_id="C-1", job_id="J-1", technical_score=80, score_breakdown={"skill_match_pct": 100})
    db_session.add(row)
    db_session.commit()

    result = svc.calculate_overall_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["technical_score"] == 80  # untouched, not recomputed
    assert result["compensation_score"] is not None  # calculated
    assert result["availability_score"] is not None  # calculated
    assert result["score_breakdown"]["skill_match_pct"] == 100  # preserved through the merge


# ── score_breakdown merge (not overwrite) with the other 3 scoring services ─

def test_score_breakdown_merges_all_four_services_keys(db_session, seeded):
    candidate, job = seeded
    row = CandidateJobScore(
        tenant_id="U-ORG", candidate_id="C-1", job_id="J-1", technical_score=80, compensation_score=100, availability_score=90,
        score_breakdown={"skill_match_pct": 100, "expected_ctc_paise": 1800000, "notice_period_days": 30},
    )
    db_session.add(row)
    db_session.commit()

    result = svc.calculate_overall_score(db_session, "C-1", "J-1", "U-ORG")

    assert result["score_breakdown"]["skill_match_pct"] == 100
    assert result["score_breakdown"]["expected_ctc_paise"] == 1800000
    assert result["score_breakdown"]["notice_period_days"] == 30
    assert "resume_completeness_score" in result["score_breakdown"]
    assert "weights" in result["score_breakdown"]


# ── TC-003: auto-recalc reflects a component update ─────────────────

def test_overall_score_reflects_updated_technical_score(db_session, seeded):
    candidate, job = seeded
    _seed_scores(db_session, technical=80, compensation=100, availability=90)
    first = svc.calculate_overall_score(db_session, "C-1", "J-1", "U-ORG")
    assert first["overall_score"] == 87

    row = db_session.query(CandidateJobScore).filter(CandidateJobScore.candidate_id == "C-1", CandidateJobScore.job_id == "J-1").first()
    row.technical_score = 40  # simulate a technical rescore landing a lower value
    db_session.commit()

    second = svc.calculate_overall_score(db_session, "C-1", "J-1", "U-ORG")
    assert second["overall_score"] != first["overall_score"]
    assert second["overall_score"] == round(40 * 0.40 + 100 * 0.30 + 90 * 0.20 + 70 * 0.10)


def test_skill_extraction_wiring_triggers_overall_recalc(db_session, seeded):
    import app.services.skill_extraction_service as skill_svc
    candidate, job = seeded
    candidate.job_id = "J-1"
    db_session.commit()

    skill_svc.extract_and_tag_skills(db_session, candidate, "U-ORG", ["Guidewire"])

    row = db_session.query(CandidateJobScore).filter(CandidateJobScore.candidate_id == "C-1", CandidateJobScore.job_id == "J-1").first()
    assert row is not None
    assert row.overall_score is not None


# ── TC-002 / Step 2: ranking ─────────────────────────────────────────

def test_get_ranked_candidates_sorts_highest_first(db_session, seeded):
    candidate, job = seeded
    c2 = Candidate(candidateID="C-2", candidateEmail="c2@example.com", candidatePassword="h", candidateFirstName="Raj", resume_completeness_score=50)
    c3 = Candidate(candidateID="C-3", candidateEmail="c3@example.com", candidatePassword="h", candidateFirstName="Anita", resume_completeness_score=60)
    db_session.add_all([c2, c3])
    db_session.commit()

    db_session.add_all([
        CandidateJobScore(tenant_id="U-ORG", candidate_id="C-1", job_id="J-1", overall_score=87),
        CandidateJobScore(tenant_id="U-ORG", candidate_id="C-2", job_id="J-1", overall_score=63),
        CandidateJobScore(tenant_id="U-ORG", candidate_id="C-3", job_id="J-1", overall_score=41),
    ])
    db_session.commit()

    ranked = svc.get_ranked_candidates(db_session, "J-1", "U-ORG")
    assert [r["rank"] for r in ranked] == [1, 2, 3]
    assert [r["overall_score"] for r in ranked] == [87, 63, 41]
    assert [r["candidate_id"] for r in ranked] == ["C-1", "C-2", "C-3"]


def test_get_ranked_candidates_includes_candidate_name(db_session, seeded):
    candidate, job = seeded
    db_session.add(CandidateJobScore(tenant_id="U-ORG", candidate_id="C-1", job_id="J-1", overall_score=87))
    db_session.commit()

    ranked = svc.get_ranked_candidates(db_session, "J-1", "U-ORG")
    assert ranked[0]["candidate_name"] == "Priya Sharma"


def test_get_ranked_candidates_scoped_to_job_and_tenant(db_session, seeded):
    candidate, job = seeded
    job2 = Jobs(jobID="J-2", jobTitle="Java Developer", jobDescription="d", jobSkills="Java", jobExperience="3+ years", jobLocation="Pune")
    db_session.add(job2)
    db_session.add_all([
        CandidateJobScore(tenant_id="U-ORG", candidate_id="C-1", job_id="J-1", overall_score=87),
        CandidateJobScore(tenant_id="U-ORG", candidate_id="C-1", job_id="J-2", overall_score=55),
    ])
    db_session.commit()

    ranked = svc.get_ranked_candidates(db_session, "J-1", "U-ORG")
    assert len(ranked) == 1
    assert ranked[0]["candidate_id"] == "C-1"
    assert ranked[0]["overall_score"] == 87


def test_get_ranked_candidates_empty_for_job_with_no_scores(db_session, seeded):
    candidate, job = seeded
    ranked = svc.get_ranked_candidates(db_session, "J-1", "U-ORG")
    assert ranked == []


# ── recalculate_for_candidate() ─────────────────────────────────────

def test_recalculate_for_candidate_never_raises(db_session, seeded, monkeypatch):
    candidate, job = seeded
    candidate.job_id = "J-1"
    db_session.commit()

    def _boom(db, cid, jid, tid):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(svc, "calculate_overall_score", _boom)
    results = svc.recalculate_for_candidate(db_session, candidate, "U-ORG")
    assert results == []


def test_unknown_candidate_raises(db_session, seeded):
    with pytest.raises(svc.CandidateNotFound):
        svc.calculate_overall_score(db_session, "NOPE", "J-1", "U-ORG")
