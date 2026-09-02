"""
Proves R-07: createCandidateSafe() is the only sanctioned candidate-
creation path, and dedup checks email, phone, and LinkedIn each
independently (the Development & Review Standard's own worked example
of the historical gap: "A duplicate check exists but only matches one
import logging
field (e.g., email), missing phone/LinkedIn").

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.candidate import Candidate
from app.models.consent import ConsentRecord
from app.models.user import Users
from app.services.candidate_service import (
    create_candidate_safe,
    find_duplicate_candidate,
    parse_experience_to_months,
    DuplicateCandidateError,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[Candidate.__table__, Users.__table__, AuditLog.__table__, ConsentRecord.__table__])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _seed_existing(db, **overrides):
    defaults = dict(
        candidateID="C-EXISTING", candidateEmail="existing@example.com",
        candidatePassword="hashed", candidateMobile="+19995551111",
        linkedin_url="https://linkedin.com/in/existing",
    )
    defaults.update(overrides)
    candidate = Candidate(**defaults)
    db.add(candidate)
    db.commit()
    return candidate


# ---------------------------------------------------------------------------
# R-07: each field independently catches a duplicate
# ---------------------------------------------------------------------------

def test_email_match_caught_independently(db_session):
    existing = _seed_existing(db_session)
    hit, matched_on = find_duplicate_candidate(db_session, email="existing@example.com", mobile="+10000000000")
    assert hit.candidateID == existing.candidateID
    assert matched_on == "email"


def test_phone_match_caught_independently(db_session):
    existing = _seed_existing(db_session)
    hit, matched_on = find_duplicate_candidate(db_session, email="new@example.com", mobile="+19995551111")
    assert hit.candidateID == existing.candidateID
    assert matched_on == "phone"


def test_linkedin_match_caught_independently(db_session):
    existing = _seed_existing(db_session)
    hit, matched_on = find_duplicate_candidate(
        db_session, email="new@example.com", mobile="+10000000000",
        linkedin_url="https://linkedin.com/in/existing",
    )
    assert hit.candidateID == existing.candidateID
    assert matched_on == "linkedin"


def test_no_match_when_all_fields_differ(db_session):
    _seed_existing(db_session)
    hit, matched_on = find_duplicate_candidate(
        db_session, email="new@example.com", mobile="+10000000000",
        linkedin_url="https://linkedin.com/in/newperson",
    )
    assert hit is None
    assert matched_on is None


# ---------------------------------------------------------------------------
# create_candidate_safe
# ---------------------------------------------------------------------------

def test_create_candidate_safe_creates_when_no_duplicate(db_session):
    candidate = create_candidate_safe(
        db_session, email="fresh@example.com", mobile="+15551234567",
        candidateFirstName="Fresh", candidateLastName="Candidate",
    )
    db_session.commit()

    assert candidate.candidateID is not None
    assert candidate.candidateEmail == "fresh@example.com"
    # password is hashed, never stored in plaintext in the real column
    assert candidate.candidatePassword != candidate.candidateTempPassword
    assert candidate.candidateTempPassword  # plaintext preserved only for the credential email


def test_create_candidate_safe_raises_on_email_duplicate(db_session):
    _seed_existing(db_session)
    with pytest.raises(DuplicateCandidateError) as exc_info:
        create_candidate_safe(db_session, email="existing@example.com", mobile="+10000000000")
    assert exc_info.value.matched_on == "email"


def test_create_candidate_safe_raises_on_phone_duplicate(db_session):
    _seed_existing(db_session)
    with pytest.raises(DuplicateCandidateError) as exc_info:
        create_candidate_safe(db_session, email="new@example.com", mobile="+19995551111")
    assert exc_info.value.matched_on == "phone"


def test_create_candidate_safe_raises_on_linkedin_duplicate(db_session):
    _seed_existing(db_session)
    with pytest.raises(DuplicateCandidateError) as exc_info:
        create_candidate_safe(
            db_session, email="new@example.com", mobile="+10000000000",
            linkedin_url="https://linkedin.com/in/existing",
        )
    assert exc_info.value.matched_on == "linkedin"


def test_create_candidate_safe_does_not_insert_on_duplicate(db_session):
    _seed_existing(db_session)
    with pytest.raises(DuplicateCandidateError):
        create_candidate_safe(db_session, email="existing@example.com")

    count = db_session.query(Candidate).count()
    assert count == 1  # no second row inserted


def test_create_candidate_safe_accepts_arbitrary_extra_fields(db_session):
    candidate = create_candidate_safe(
        db_session, email="fresh2@example.com",
        candidateRole="Recruiter Sourced", candidateSource="referral",
    )
    db_session.commit()
    assert candidate.candidateRole == "Recruiter Sourced"
    assert candidate.candidateSource == "referral"


# ---------------------------------------------------------------------------
# R-01 (HRMS-P601) -- 5-year experience gate at creation time.
# Reuses app.services.submission_service.check_experience_eligibility(),
# not a second implementation -- these tests exercise the creation-time
# wrapper (parsing + gate + override), not the eligibility math itself
# (already covered by tests/test_submission_interview_pipeline.py).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected_months", [
    ("5", 60),
    ("3.5", 42),
    ("10+ years", 120),
    ("7 years", 84),
    ("Fresher", None),
    ("Intern", None),
    ("", None),
    (None, None),
])
def test_parse_experience_to_months(raw, expected_months):
    assert parse_experience_to_months(raw) == expected_months


# REMOVED 2026-07-23, direct instruction from Avinash: R-01 must never
# block candidate creation/DB capture ("we should still gather all
# resumes not stop building our DB") -- enforce_experience_gate_at_creation()
# and its dedicated call site in onboarding.py's create_candidate were
# deleted entirely. R-01 still applies for real at the point it actually
# matters -- submission/matching to a role requiring 5+ years -- via
# app.services.submission_service.check_experience_eligibility(), fully
# unaffected by this change and covered by
# tests/test_submission_interview_pipeline.py. total_experience_months
# is still computed and stored at creation time (see
# test_parse_experience_to_months above) so that later submission-time
# gate has real data to check -- only the creation-time BLOCK is gone.
