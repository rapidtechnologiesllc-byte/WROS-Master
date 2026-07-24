"""
S-030/HRMS-0430 -- Resume Completeness Score.

Real architecture under test: candidate_resume_parsed (S-028) already
has the exact fields this scoring function needs; no adaptation
required. BR-01 (distinct from profile completeness) is structural --
this module never reads get_missing_fields(). BR-02 (must run after
skill extraction) is verified via resume_parsing_service's call order.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_resume_parsed import CandidateResumeParsed
from app.models.user import Users

import app.services.resume_completeness_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[Users.__table__, Candidate.__table__, CandidateResumeParsed.__table__])
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
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h")
    db_session.add_all([owner, candidate])
    db_session.commit()
    return candidate


def test_calculate_resume_completeness_none_returns_zero():
    assert svc.calculate_resume_completeness(None) == 0


def test_calculate_resume_completeness_empty_record_returns_zero(db_session, seeded):
    parsed = CandidateResumeParsed(tenant_id="U-ORG", candidate_id="C-1")
    assert svc.calculate_resume_completeness(parsed) == 0


def test_calculate_resume_completeness_rich_resume_scores_high():
    """TC-002: name, 3 work entries + descriptions, education, 10 skills, 2 certs, 6yr experience -> >=80."""
    parsed = CandidateResumeParsed(
        tenant_id="U-ORG", candidate_id="C-1",
        full_name="Priya Sharma", email="priya@example.com",
        work_history=[
            {"employer": "A", "description": "Built backend systems"},
            {"employer": "B", "description": "Led a team of engineers"},
            {"employer": "C", "description": "Owned platform architecture"},
        ],
        education=[{"institution": "State University", "degree": "B.Tech"}],
        skills=["Python", "SQL", "AWS", "Java", "Docker", "Kubernetes", "Git", "Linux", "React", "Node"],
        certifications=[{"name": "AWS Certified"}, {"name": "PMP"}],
        total_experience_months=72,
    )
    score = svc.calculate_resume_completeness(parsed)
    assert score >= 80


def test_calculate_resume_completeness_component_breakdown():
    parsed = CandidateResumeParsed(
        tenant_id="U-ORG", candidate_id="C-1",
        full_name="Priya", phone="+919876543210",  # contact: 10
        work_history=[{"employer": "A", "description": "did work"}],  # 1 entry: 10, +1 description: 5
        education=[],  # 0
        skills=["Python", "SQL"],  # 1-4 skills: 5
        certifications=[],  # 0
        total_experience_months=30,  # < 60: 0
    )
    # 10 (contact) + 10 (1 work entry) + 5 (1 description) + 0 + 5 (skills) + 0 + 0 = 30
    assert svc.calculate_resume_completeness(parsed) == 30


def test_calculate_resume_completeness_experience_bonus_only_at_5_years():
    below = CandidateResumeParsed(tenant_id="U-ORG", candidate_id="C-1", total_experience_months=59)
    at_threshold = CandidateResumeParsed(tenant_id="U-ORG", candidate_id="C-1", total_experience_months=60)
    assert svc.calculate_resume_completeness(below) == 0
    assert svc.calculate_resume_completeness(at_threshold) == 10


def test_calculate_resume_completeness_maxes_out_every_component():
    """The spec's own stated component weights (10+20+15+10+15+10+10)
    sum to 90, not the spec's separately-claimed 'Total max: 100' --
    a documented inconsistency in the source spec (same class as
    S-028's "3 years" vs 42-month discrepancy). This test asserts the
    real, correct max given every component maxed out; the function
    still caps at 100 as a defensive ceiling in case components change."""
    parsed = CandidateResumeParsed(
        tenant_id="U-ORG", candidate_id="C-1",
        full_name="Priya", email="priya@example.com",
        work_history=[{"description": f"job {i}"} for i in range(5)],
        education=[{"institution": "X"}],
        skills=[f"skill{i}" for i in range(15)],
        certifications=[{"name": "Cert"}],
        total_experience_months=100,
    )
    assert svc.calculate_resume_completeness(parsed) == 90


def test_update_resume_completeness_score_stores_on_both_tables(db_session, seeded):
    candidate = seeded
    parsed = CandidateResumeParsed(
        tenant_id="U-ORG", candidate_id="C-1", full_name="Priya", email="priya@example.com",
        work_history=[{"description": "did work"}], skills=["Python"],
    )
    db_session.add(parsed)
    db_session.commit()

    result = svc.update_resume_completeness_score(db_session, candidate, "U-ORG")
    assert result["resume_completeness_score"] > 0

    db_session.refresh(candidate)
    db_session.refresh(parsed)
    assert candidate.resume_completeness_score == result["resume_completeness_score"]
    assert parsed.resume_completeness_score == result["resume_completeness_score"]
    assert parsed.score_calculated_at is not None


def test_update_resume_completeness_score_no_parsed_record_yet_returns_zero(db_session, seeded):
    candidate = seeded
    result = svc.update_resume_completeness_score(db_session, candidate, "U-ORG")
    assert result["resume_completeness_score"] == 0
    db_session.refresh(candidate)
    assert candidate.resume_completeness_score == 0
