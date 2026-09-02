"""
R-05 ("L1 must pass before L2 can be scheduled") applied to the legacy
`InterviewPanel`/`Interview`/`InterviewFeedback` system -- the original
"Schedule Interview" feature the Development & Review Standard names
as having "zero enforcement... today." This is separate from the newer
leveled `submission_interviews` system's own R-05 gate (already covered
import logging
by tests/test_submission_interview_pipeline.py).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.user import Interview, InterviewFeedback, InterviewPanel, Users
from app.services.interview_sequencing_service import (
    PriorRoundNotPassed,
    enforce_interview_sequencing_gate,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Candidate.__table__, Users.__table__,
        InterviewPanel.__table__, Interview.__table__, InterviewFeedback.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def candidate(db_session):
    c = Candidate(candidateID="C-SEQ", candidateEmail="seq@example.com", candidatePassword="h")
    db_session.add(c)
    db_session.commit()
    return c


def _make_panel(db, candidate_id, *, round_name="HR"):
    panel = InterviewPanel(candidate_id=candidate_id, round_name=round_name, created_at=datetime.utcnow())
    db.add(panel)
    db.commit()
    return panel


def _make_interview(db, panel_id, candidate_id, *, status="Completed"):
    interview = Interview(panel_id=panel_id, candidate_id=candidate_id, status=status)
    db.add(interview)
    db.commit()
    return interview


def _make_feedback(db, interview_id, *, recommendation):
    feedback = InterviewFeedback(interview_id=interview_id, interviewer_id="U-1", recommendation=recommendation)
    db.add(feedback)
    db.commit()
    return feedback


def test_first_round_always_allowed(db_session, candidate):
    enforce_interview_sequencing_gate(db_session, candidate.candidateID)  # must not raise


def test_second_round_blocked_when_no_prior_interview_scheduled(db_session, candidate):
    _make_panel(db_session, candidate.candidateID)
    with pytest.raises(PriorRoundNotPassed):
        enforce_interview_sequencing_gate(db_session, candidate.candidateID)


def test_second_round_blocked_when_prior_interview_not_completed(db_session, candidate):
    panel = _make_panel(db_session, candidate.candidateID)
    _make_interview(db_session, panel.id, candidate.candidateID, status="Scheduled")
    with pytest.raises(PriorRoundNotPassed):
        enforce_interview_sequencing_gate(db_session, candidate.candidateID)


def test_second_round_blocked_when_completed_but_no_feedback_yet(db_session, candidate):
    panel = _make_panel(db_session, candidate.candidateID)
    _make_interview(db_session, panel.id, candidate.candidateID, status="Completed")
    with pytest.raises(PriorRoundNotPassed):
        enforce_interview_sequencing_gate(db_session, candidate.candidateID)


def test_second_round_blocked_when_feedback_is_hold_only(db_session, candidate):
    panel = _make_panel(db_session, candidate.candidateID)
    interview = _make_interview(db_session, panel.id, candidate.candidateID, status="Completed")
    _make_feedback(db_session, interview.id, recommendation="Hold")
    with pytest.raises(PriorRoundNotPassed):
        enforce_interview_sequencing_gate(db_session, candidate.candidateID)


def test_second_round_blocked_when_any_reject_present_even_with_a_hire(db_session, candidate):
    """Fail-closed: one Reject among multiple interviewers blocks
    progression even if another interviewer recommended Hire."""
    panel = _make_panel(db_session, candidate.candidateID)
    interview = _make_interview(db_session, panel.id, candidate.candidateID, status="Completed")
    _make_feedback(db_session, interview.id, recommendation="Hire")
    _make_feedback(db_session, interview.id, recommendation="Reject")
    with pytest.raises(PriorRoundNotPassed):
        enforce_interview_sequencing_gate(db_session, candidate.candidateID)


def test_second_round_allowed_when_prior_round_passed(db_session, candidate):
    panel = _make_panel(db_session, candidate.candidateID)
    interview = _make_interview(db_session, panel.id, candidate.candidateID, status="Completed")
    _make_feedback(db_session, interview.id, recommendation="Hire")
    enforce_interview_sequencing_gate(db_session, candidate.candidateID)  # must not raise


def test_gate_checks_the_most_recent_panel_not_an_earlier_one(db_session, candidate):
    """If round 1 passed and round 2 was created but hasn't passed yet,
    a round-3 attempt must be blocked against round 2, not incorrectly
    re-validated against the already-passed round 1."""
    panel_1 = _make_panel(db_session, candidate.candidateID, round_name="HR")
    interview_1 = _make_interview(db_session, panel_1.id, candidate.candidateID, status="Completed")
    _make_feedback(db_session, interview_1.id, recommendation="Hire")

    panel_2 = _make_panel(db_session, candidate.candidateID, round_name="Technical")
    # panel_2 has no interview/feedback yet -- has not passed.

    with pytest.raises(PriorRoundNotPassed) as exc_info:
        enforce_interview_sequencing_gate(db_session, candidate.candidateID)
    assert str(panel_2.id) in str(exc_info.value) or "Technical" in str(exc_info.value)


def test_gate_is_scoped_per_candidate(db_session):
    """Another candidate's unpassed round must not block this candidate."""
    c1 = Candidate(candidateID="C-A", candidateEmail="a@example.com", candidatePassword="h")
    c2 = Candidate(candidateID="C-B", candidateEmail="b@example.com", candidatePassword="h")
    db_session.add_all([c1, c2])
    db_session.commit()

    _make_panel(db_session, "C-A")  # C-A's first round, unresolved -- irrelevant to C-B

    enforce_interview_sequencing_gate(db_session, "C-B")  # C-B's first round -- must not raise
