"""
Guidewire candidate indicator, 2026-08-05. Avinash: "our bread and
butter comes from Guidewire SI work ... we nourish and take care of
these candidates well to be able to convert them." Throwaway SQLite --
never the real database.
"""
import os
import logging
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_skill_tag import CandidateSkillTag
from app.models.user import Jobs, Users

from app.services.guidewire_candidate_service import is_guidewire_candidate

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Jobs.__table__, Candidate.__table__, CandidateSkillTag.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

def _make_candidate(db, candidate_id="C-1", skills=None, job_id=None):
    candidate = Candidate(
        candidateID=candidate_id, candidateEmail=f"{candidate_id}@example.com",
        candidatePassword="h", candidateFirstName="Priya", candidateLastName="Rao",
        candidateSkills=skills, job_id=job_id,
    )
    db.add(candidate)
    db.commit()
    return candidate

def _make_job(db, job_id="J-1", title="Backend Engineer", skills="", domain=None):
    job = Jobs(
        jobID=job_id, jobTitle=title, jobDescription="desc", jobSkills=skills,
        jobExperience="3-5", jobLocation="Remote", domain=domain,
    )
    db.add(job)
    db.commit()
    return job

def test_true_when_structured_skill_tag_is_guidewire(db_session):
    candidate = _make_candidate(db_session, "C-1", skills=None)
    db_session.add(CandidateSkillTag(tenant_id="U-SYS", candidate_id="C-1", skill_canonical="Guidewire"))
    db_session.commit()

    assert is_guidewire_candidate(db_session, candidate) is True

def test_true_when_raw_skills_text_contains_a_known_synonym(db_session):
    candidate = _make_candidate(db_session, "C-1", skills="Java, GWPC, SQL")

    assert is_guidewire_candidate(db_session, candidate) is True

def test_true_when_raw_skills_text_says_guidewire_directly(db_session):
    candidate = _make_candidate(db_session, "C-1", skills="Guidewire PolicyCenter")

    assert is_guidewire_candidate(db_session, candidate) is True

def test_false_when_no_guidewire_signal_anywhere(db_session):
    candidate = _make_candidate(db_session, "C-1", skills="Java, SQL, AWS")

    assert is_guidewire_candidate(db_session, candidate) is False

def test_true_when_linked_job_is_a_guidewire_role_even_with_no_candidate_skills(db_session):
    _make_job(db_session, "J-1", title="Guidewire PolicyCenter Developer")
    candidate = _make_candidate(db_session, "C-1", skills=None, job_id="J-1")

    assert is_guidewire_candidate(db_session, candidate) is True

def test_false_when_linked_job_is_unrelated(db_session):
    _make_job(db_session, "J-1", title="Backend Engineer", skills="Python, Django")
    candidate = _make_candidate(db_session, "C-1", skills=None, job_id="J-1")

    assert is_guidewire_candidate(db_session, candidate) is False

def test_false_for_empty_candidate(db_session):
    candidate = _make_candidate(db_session, "C-1", skills="")

    assert is_guidewire_candidate(db_session, candidate) is False
