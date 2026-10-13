"""
S-037/HRMS-0437 -- Technical Qualification Score.

Real architecture under test (see technical_scoring_service module
docstring): candidate_job_scores/Jobs' 4 new structured columns are
genuinely new (Jobs has no required_skills/min_experience_years/domain/
certifications_preferred natively -- jobSkills/jobExperience are free
text, lazily parsed on first score); BR-01 canonical-to-canonical skill
matching only (no ClaimCenter/PolicyCenter sub-module partial credit --
the real synonym library collapses those to one canonical skill); BR-02
experience score capped at 20 more than 2 years below minimum; BR-03
recalculates on skill update, wired into
skill_extraction_service.extract_and_tag_skills(), never raises.

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
from app.models.candidate_resume_parsed import CandidateResumeParsed
from app.models.candidate_skill_tag import CandidateSkillTag
from app.models.user import Jobs, Users

import app.services.technical_scoring_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, Jobs.__table__, CandidateJobApplication.__table__,
        CandidateJobScore.__table__, CandidateResumeParsed.__table__, CandidateSkillTag.__table__,
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
    job = Jobs(jobID="J-1", jobTitle="Guidewire Developer", jobDescription="d", jobSkills="Guidewire, Java, SQL", jobExperience="5+ years", jobLocation="Bangalore")
    db_session.add_all([owner, candidate, job])
    db_session.commit()
    return candidate, job


def _tag(db_session, canonical, confidence=1.0):
    db_session.add(CandidateSkillTag(tenant_id="U-ORG", candidate_id="C-1", skill_canonical=canonical, skill_raw=canonical, confidence=confidence))
    db_session.commit()


def _resume(db_session, *, years=None, certs=None):
    db_session.add(CandidateResumeParsed(tenant_id="U-ORG", candidate_id="C-1", total_experience_years=years, certifications=certs or []))
    db_session.commit()


# ── TC-001: full match ─────────────────────────────────────────────────

def test_full_skill_and_experience_match_scores_at_least_80(db_session, seeded):
    candidate, job = seeded
    _tag(db_session, "Guidewire")
    _tag(db_session, "Java")
    _tag(db_session, "SQL")
    _resume(db_session, years=8.0)

    result = svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["technical_score"] >= 80
    assert result["score_breakdown"]["skill_match_pct"] == 100
    assert result["score_breakdown"]["experience_score"] == 100


# ── TC-002: partial skill match contributes proportionally ─────────────

def test_partial_skill_match_scores_proportionally(db_session, seeded):
    candidate, job = seeded  # requires Guidewire, Java, SQL (3 skills)
    _tag(db_session, "Guidewire")
    _tag(db_session, "Java")
    # SQL missing -> 2/3 matched = 67%
    _resume(db_session, years=8.0)

    result = svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["score_breakdown"]["skill_match_pct"] == 67
    assert set(result["score_breakdown"]["matched_skills"]) == {"Guidewire", "Java"}
    assert result["score_breakdown"]["missing_skills"] == ["SQL"]


def test_no_matching_skills_scores_zero_skill_match(db_session, seeded):
    candidate, job = seeded
    _tag(db_session, "Python")
    _resume(db_session, years=8.0)

    result = svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["score_breakdown"]["skill_match_pct"] == 0


def test_no_required_skills_gives_full_skill_credit(db_session, seeded):
    candidate, job = seeded
    job.jobSkills = ""
    db_session.commit()
    _resume(db_session, years=8.0)

    result = svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["score_breakdown"]["skill_match_pct"] == 100


# ── TC-003: experience tiers, BR-02 cap ─────────────────────────────────

def test_experience_exactly_at_minimum_scores_100(db_session, seeded):
    candidate, job = seeded  # min_experience_years parsed from "5+ years" -> 5
    _resume(db_session, years=5.0)
    result = svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["score_breakdown"]["experience_score"] == 100


def test_experience_one_year_below_minimum_scores_70(db_session, seeded):
    candidate, job = seeded
    _resume(db_session, years=4.5)
    result = svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["score_breakdown"]["experience_score"] == 70


def test_experience_two_years_below_minimum_scores_40(db_session, seeded):
    candidate, job = seeded
    _resume(db_session, years=3.5)
    result = svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["score_breakdown"]["experience_score"] == 40


def test_experience_three_years_below_minimum_capped_at_20(db_session, seeded):
    """BR-02: more than 2 years below minimum -> capped at 20."""
    candidate, job = seeded
    _resume(db_session, years=2.0)  # 3 years below the "5+ years" minimum
    result = svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["score_breakdown"]["experience_score"] == 20


def test_experience_falls_back_to_candidate_total_experience_months(db_session, seeded):
    """No CandidateResumeParsed row -- falls back to candidates.total_experience_months."""
    candidate, job = seeded
    candidate.total_experience_months = 96  # 8 years
    db_session.commit()
    result = svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["score_breakdown"]["experience_score"] == 100


# ── Certification scoring ───────────────────────────────────────────────

def test_no_certifications_preferred_scores_100(db_session, seeded):
    """Jobs has no real certifications-entry field -- certifications_preferred
    lazily defaults to empty, so certification_score is always 100 until a
    real UI to enter this exists (see module docstring)."""
    candidate, job = seeded
    _resume(db_session, years=8.0)
    result = svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["score_breakdown"]["certification_score"] == 100


def test_missing_preferred_certifications_penalized(db_session, seeded):
    candidate, job = seeded
    _resume(db_session, years=8.0, certs=[{"name": "Guidewire ACE"}])

    # First call triggers the lazy parse (required_skills_canonical etc. get
    # populated); only AFTER that is certifications_preferred safe to set
    # directly -- pre-setting it before the first-ever parse would get
    # clobbered by _ensure_job_requirements_parsed's own initialization,
    # which is correct since nothing else in this codebase currently
    # populates it (see module docstring -- no real UI exists yet).
    svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    job.certifications_preferred = ["Guidewire ACE", "AWS Certified"]
    db_session.commit()

    result = svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["score_breakdown"]["certification_score"] == 75  # 1 of 2 missing -> 100 - 25


# ── BR-01: canonical-only matching (no raw-string collisions) ──────────

def test_raw_abbreviation_does_not_match_without_normalization(db_session, seeded):
    """BR-01: 'GWCC' must not raw-string-match 'Guidewire' -- it's stored
    as its canonical form via normalize_skills(), same as every candidate
    skill tag in this codebase."""
    candidate, job = seeded
    _tag(db_session, "GWCC")  # a tag stored with a raw, non-canonical value
    _resume(db_session, years=8.0)

    result = svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    # job requires canonical "Guidewire" (normalize_skills("Guidewire") ==
    # "Guidewire"); a raw "GWCC" tag (not run through normalization) does
    # not match it -- proves matching is canonical-to-canonical, not substring.
    assert "Guidewire" not in result["score_breakdown"]["matched_skills"]


# ── TC-004: stored with full breakdown ──────────────────────────────────

def test_score_persisted_with_full_breakdown(db_session, seeded):
    candidate, job = seeded
    _tag(db_session, "Guidewire")
    _resume(db_session, years=8.0)

    svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    db_session.commit()

    row = db_session.query(CandidateJobScore).filter(CandidateJobScore.candidate_id == "C-1", CandidateJobScore.job_id == "J-1").first()
    assert row is not None
    assert row.technical_score is not None
    assert set(row.score_breakdown.keys()) == {"skill_match_pct", "experience_score", "certification_score", "matched_skills", "missing_skills"}


def test_recalculating_updates_existing_row_not_duplicate(db_session, seeded):
    candidate, job = seeded
    _resume(db_session, years=8.0)

    svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    db_session.commit()
    _tag(db_session, "Guidewire")
    svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")
    db_session.commit()

    rows = db_session.query(CandidateJobScore).filter(CandidateJobScore.candidate_id == "C-1", CandidateJobScore.job_id == "J-1").all()
    assert len(rows) == 1


def test_unknown_candidate_raises(db_session, seeded):
    candidate, job = seeded
    with pytest.raises(svc.CandidateNotFound):
        svc.calculate_technical_score(db_session, "NOPE", "J-1", "U-ORG")


def test_unknown_job_raises(db_session, seeded):
    candidate, job = seeded
    with pytest.raises(svc.JobNotFound):
        svc.calculate_technical_score(db_session, "C-1", "NOPE", "U-ORG")


# ── BR-03: recalculate_for_candidate() ──────────────────────────────────

def test_recalculate_for_candidate_scores_primary_linked_job(db_session, seeded):
    candidate, job = seeded
    candidate.job_id = "J-1"
    db_session.commit()
    _tag(db_session, "Guidewire")

    results = svc.recalculate_for_candidate(db_session, candidate, "U-ORG")
    assert len(results) == 1
    assert results[0]["job_id"] == "J-1"


def test_recalculate_for_candidate_scores_application_linked_jobs(db_session, seeded):
    candidate, job = seeded
    job2 = Jobs(jobID="J-2", jobTitle="Java Developer", jobDescription="d", jobSkills="Java", jobExperience="3+ years", jobLocation="Pune")
    db_session.add(job2)
    db_session.add(CandidateJobApplication(candidate_id="C-1", job_id="J-2"))
    db_session.commit()

    results = svc.recalculate_for_candidate(db_session, candidate, "U-ORG")
    job_ids = {r["job_id"] for r in results}
    assert job_ids == {"J-2"}


def test_recalculate_for_candidate_no_linked_jobs_returns_empty(db_session, seeded):
    candidate, job = seeded
    results = svc.recalculate_for_candidate(db_session, candidate, "U-ORG")
    assert results == []


def test_recalculate_for_candidate_never_raises_on_bad_job(db_session, seeded, monkeypatch):
    """A failure scoring one linked job must not propagate -- BR-03's own
    module-docstring guarantee."""
    candidate, job = seeded
    candidate.job_id = "J-1"
    db_session.commit()

    def _boom(db, cid, jid, tid):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(svc, "calculate_technical_score", _boom)
    results = svc.recalculate_for_candidate(db_session, candidate, "U-ORG")
    assert results == []  # failed silently, logged -- did not raise


# ── Wired into skill_extraction_service.extract_and_tag_skills() ───────

def test_extract_and_tag_skills_triggers_recalculation(db_session, seeded):
    import app.services.skill_extraction_service as skill_svc
    candidate, job = seeded
    candidate.job_id = "J-1"
    db_session.commit()
    _resume(db_session, years=8.0)

    skill_svc.extract_and_tag_skills(db_session, candidate, "U-ORG", ["Guidewire", "Java", "SQL"])

    row = db_session.query(CandidateJobScore).filter(CandidateJobScore.candidate_id == "C-1", CandidateJobScore.job_id == "J-1").first()
    assert row is not None
    assert row.score_breakdown["skill_match_pct"] == 100
