"""
import logging
S-073/HRMS-0473 -- Candidate Preference Capture Engine.

Real architecture under test (see preference_capture_service module
docstring): no new table -- reuses S-021's real candidate_memory_facts/
upsert_fact() directly, category=PREFERENCE. BR-01 (only after 100%
completeness) reuses the real get_missing_fields() denominator. BR-02
(optional, "Not specified" default) verified directly.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_memory import CandidateMemory, CandidateMemoryFact
from app.models.user import Users

import app.services.preference_capture_service as svc

ALL_REQUIRED_FIELDS = dict(
    candidateFirstName="Priya", candidateLastName="S", candidateMobile="+919876543210",
    candidateGender="Female", candidateDateOfBirth="1995-01-01", candidateCurrentLocation="Bangalore",
    candidateJoiningDate="2026-09-01", candidateExperience="5", candidateJobTitle="Guidewire Developer",
)

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__, CandidateMemory.__table__, CandidateMemoryFact.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

def _complete_candidate(db, cid="C-1"):
    from datetime import date
    c = Candidate(
        candidateID=cid, candidateEmail=f"{cid.lower()}@example.com", candidatePassword="h",
        candidateFirstName="Priya", candidateLastName="S", candidateMobile="+919876543210",
        candidateGender="Female", candidateDateOfBirth=date(1995, 1, 1), candidateCurrentLocation="Bangalore",
        candidateJoiningDate=date(2026, 9, 1), candidateExperience="5", candidateJobTitle="Guidewire Developer",
    )
    db.add(c)
    db.add(CandidateInfoForm(candidateID=cid, marital_status="Single", nationality="Indian", permanent_address="Bangalore, KA, India"))
    db.commit()
    return c

def _incomplete_candidate(db, cid="C-1"):
    c = Candidate(candidateID=cid, candidateEmail=f"{cid.lower()}@example.com", candidatePassword="h", candidateFirstName="Priya")
    db.add(c)
    db.commit()
    return c

@pytest.fixture()
def seeded_hr(db_session):
    db_session.add(Users(UserID="U-HR", UserRole="HR Manager", UserEmail="hr@blitzenx.com", UserPassword="h", tenant_id=None))
    db_session.commit()

# ── TC-001: first preference question ────────────────────────────────────

def test_first_preference_question_returned_when_complete(db_session, seeded_hr):
    _complete_candidate(db_session)
    result = svc.ask_preference_question(db_session, "C-1", "U-ORG")
    assert result["preference_type"] == "WORK_ENVIRONMENT"
    assert "remote" in result["question"].lower()

# ── TC-004: not before qualification ─────────────────────────────────────

def test_no_question_when_profile_incomplete(db_session, seeded_hr):
    _incomplete_candidate(db_session)
    result = svc.ask_preference_question(db_session, "C-1", "U-ORG")
    assert result is None

# ── Sequential questions ──────────────────────────────────────────────────

def test_returns_next_unasked_question_in_order(db_session, seeded_hr):
    _complete_candidate(db_session)
    svc.record_preference_answer(db_session, "C-1", "U-ORG", "WORK_ENVIRONMENT", "remote")

    result = svc.ask_preference_question(db_session, "C-1", "U-ORG")
    assert result["preference_type"] == "DOMAIN_PREFERENCE"

# ── TC-002: all asked ─────────────────────────────────────────────────────

def test_returns_none_when_all_five_asked(db_session, seeded_hr):
    _complete_candidate(db_session)
    for item in svc.PREFERENCE_QUESTIONS:
        svc.record_preference_answer(db_session, "C-1", "U-ORG", item["preference_type"], "some answer")

    result = svc.ask_preference_question(db_session, "C-1", "U-ORG")
    assert result is None

# ── TC-003: preference captured ──────────────────────────────────────────

def test_record_preference_answer_stores_fact(db_session, seeded_hr):
    _complete_candidate(db_session)
    svc.record_preference_answer(db_session, "C-1", "U-ORG", "WORK_ENVIRONMENT", "remote")

    fact = db_session.query(CandidateMemoryFact).filter(CandidateMemoryFact.candidate_id == "C-1", CandidateMemoryFact.fact_category == "PREFERENCE").first()
    assert fact is not None
    assert fact.fact_key == "WORK_ENVIRONMENT"
    assert fact.fact_value == "remote"

# ── BR-02: skip / not specified ──────────────────────────────────────────

def test_mark_preference_skipped_records_not_specified(db_session, seeded_hr):
    _complete_candidate(db_session)
    svc.mark_preference_skipped(db_session, "C-1", "U-ORG", "WORK_ENVIRONMENT")

    fact = db_session.query(CandidateMemoryFact).filter(CandidateMemoryFact.candidate_id == "C-1", CandidateMemoryFact.fact_key == "WORK_ENVIRONMENT").first()
    assert fact.fact_value == "Not specified"

    # Skipped preference is never re-asked.
    result = svc.ask_preference_question(db_session, "C-1", "U-ORG")
    assert result["preference_type"] == "DOMAIN_PREFERENCE"

# ── Message appending ─────────────────────────────────────────────────────

def test_append_preference_question_to_message(db_session):
    message = "Thank you! I now have everything I need."
    item = {"preference_type": "WORK_ENVIRONMENT", "question": "Remote or hybrid?"}
    result = svc.append_preference_question_to_message(message, item)
    assert result == "Thank you! I now have everything I need. Just one more thing -- Remote or hybrid?"

def test_append_with_no_question_returns_message_unchanged():
    message = "Thank you! I now have everything I need."
    assert svc.append_preference_question_to_message(message, None) == message
