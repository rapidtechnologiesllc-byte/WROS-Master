"""
Proves R-07: createCandidateSafe() is the only sanctioned candidate-
creation path, and dedup checks email, phone, and LinkedIn each
independently (the Development & Review Standard's own worked example
of the historical gap: "A duplicate check exists but only matches one
field (e.g., email), missing phone/LinkedIn").

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.services.candidate_service import (
    create_candidate_safe,
    find_duplicate_candidate,
    DuplicateCandidateError,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[Candidate.__table__])
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
