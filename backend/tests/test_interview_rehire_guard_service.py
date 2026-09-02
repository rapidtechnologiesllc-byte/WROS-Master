"""
Rehire guard -- Part 2 of the interview regrouping + rehire guard
priority (wros_interview_regrouping_and_rehire_guard_priority memory).
Avinash's own words: "if there was a nohire in the past then when the
next time someone is trying to schedule interview to the candidate
they need to provide a clear justification an agentic bot should
review and decide or take approval from hiring manager before
import logging
scheduling the interview."

Throwaway SQLite -- never the real database.
"""
import json
import os
import tempfile
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.user import Interview, InterviewFeedback, InterviewPanel, Jobs, Users
from app.models.interview_rehire_review import InterviewRehireReview
from app.services.interview_rehire_guard_service import (
    FAIL_CLOSED_REASONING,
    RehireReviewAlreadyDecided,
    RehireReviewNotFound,
    candidate_has_past_no_hire,
    decide_rehire_review,
    get_past_no_hire_panels,
    get_pending_rehire_reviews,
    review_rehire_justification,
    submit_rehire_request,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Candidate.__table__, Users.__table__, Jobs.__table__,
        InterviewPanel.__table__, Interview.__table__, InterviewFeedback.__table__,
        InterviewRehireReview.__table__,
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
    c = Candidate(
        candidateID="C-REHIRE", candidateEmail="rehire@example.com", candidatePassword="h",
        candidateFirstName="Sam", candidateLastName="Lee",
    )
    db_session.add(c)
    db_session.commit()
    return c


def _make_panel(db, candidate_id, *, round_name="HR", job_id=None):
    panel = InterviewPanel(candidate_id=candidate_id, round_name=round_name, job_id=job_id, created_at=datetime.utcnow())
    db.add(panel)
    db.commit()
    return panel


def _make_interview(db, panel_id, candidate_id, *, status="Completed"):
    interview = Interview(panel_id=panel_id, candidate_id=candidate_id, status=status)
    db.add(interview)
    db.commit()
    return interview


def _make_feedback(db, interview_id, *, recommendation, comments=None):
    feedback = InterviewFeedback(interview_id=interview_id, interviewer_id="U-1", recommendation=recommendation, comments=comments)
    db.add(feedback)
    db.commit()
    return feedback


def _clear_llm(prompt):
    return json.dumps({"decision": "CLEAR", "reasoning": "Candidate closed the prior skill gap.", "confidence": 0.9})


def _escalate_llm(prompt):
    return json.dumps({"decision": "ESCALATE", "reasoning": "Justification too vague.", "confidence": 0.4})


def _broken_llm(prompt):
    raise RuntimeError("simulated LLM outage")


def _malformed_llm(prompt):
    return "not json at all"


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def test_no_past_no_hire_for_fresh_candidate(db_session, candidate):
    assert candidate_has_past_no_hire(db_session, candidate.candidateID) is False
    assert get_past_no_hire_panels(db_session, candidate.candidateID) == []


def test_hire_only_history_is_not_a_no_hire(db_session, candidate):
    panel = _make_panel(db_session, candidate.candidateID)
    interview = _make_interview(db_session, panel.id, candidate.candidateID)
    _make_feedback(db_session, interview.id, recommendation="Hire")
    assert candidate_has_past_no_hire(db_session, candidate.candidateID) is False


def test_reject_feedback_flags_past_no_hire(db_session, candidate):
    panel = _make_panel(db_session, candidate.candidateID, round_name="Technical")
    interview = _make_interview(db_session, panel.id, candidate.candidateID)
    _make_feedback(db_session, interview.id, recommendation="Reject", comments="Weak on Guidewire fundamentals")
    assert candidate_has_past_no_hire(db_session, candidate.candidateID) is True
    panels = get_past_no_hire_panels(db_session, candidate.candidateID)
    assert [p.id for p in panels] == [panel.id]


def test_past_no_hire_detected_across_a_different_job(db_session, candidate):
    """Avinash's own wording is candidate-scoped, not job-scoped -- a
    reject on job A must still be found when scheduling for job B."""
    panel = _make_panel(db_session, candidate.candidateID, round_name="HR", job_id="JOB-A")
    interview = _make_interview(db_session, panel.id, candidate.candidateID)
    _make_feedback(db_session, interview.id, recommendation="Reject")
    assert candidate_has_past_no_hire(db_session, candidate.candidateID) is True


# ---------------------------------------------------------------------------
# AI review -- fail-closed posture
# ---------------------------------------------------------------------------

def test_ai_review_clears_strong_justification():
    result = review_rehire_justification("Sam Lee", "- Round 'Technical': weak fundamentals", "Candidate completed a Guidewire certification since the rejection.", llm_call=_clear_llm)
    assert result["decision"] == "CLEAR"
    assert result["confidence"] == 0.9


def test_ai_review_escalates_weak_justification():
    result = review_rehire_justification("Sam Lee", "- Round 'Technical': weak fundamentals", "Seems like a good fit, let's give them another shot.", llm_call=_escalate_llm)
    assert result["decision"] == "ESCALATE"


def test_ai_review_fails_closed_on_llm_exception():
    result = review_rehire_justification("Sam Lee", "- context", "Some justification", llm_call=_broken_llm)
    assert result["decision"] == "ESCALATE"
    assert result["reasoning"] == FAIL_CLOSED_REASONING


def test_ai_review_fails_closed_on_malformed_json():
    result = review_rehire_justification("Sam Lee", "- context", "Some justification", llm_call=_malformed_llm)
    assert result["decision"] == "ESCALATE"
    assert result["reasoning"] == FAIL_CLOSED_REASONING


# ---------------------------------------------------------------------------
# submit_rehire_request
# ---------------------------------------------------------------------------

def _seed_past_reject(db, candidate_id):
    panel = _make_panel(db, candidate_id, round_name="Technical")
    interview = _make_interview(db, panel.id, candidate_id)
    _make_feedback(db, interview.id, recommendation="Reject", comments="Weak fundamentals")
    return panel


def test_submit_rehire_request_ai_cleared(db_session, candidate):
    _seed_past_reject(db_session, candidate.candidateID)
    review = submit_rehire_request(
        db_session, candidate.candidateID, "Sam Lee", "Technical", None, "U-RECRUITER",
        "Candidate completed a Guidewire PolicyCenter certification since the rejection.",
        llm_call=_clear_llm,
    )
    assert review.status == "AI_CLEARED"
    assert review.ai_decision == "CLEAR"
    assert review.past_no_hire_panel_ids  # captured real evidence


def test_submit_rehire_request_escalates_to_hm(db_session, candidate):
    _seed_past_reject(db_session, candidate.candidateID)
    review = submit_rehire_request(
        db_session, candidate.candidateID, "Sam Lee", "Technical", None, "U-RECRUITER",
        "Seems like a good fit now.",
        llm_call=_escalate_llm,
    )
    assert review.status == "PENDING_HM_APPROVAL"
    pending = get_pending_rehire_reviews(db_session)
    assert review.id in [r.id for r in pending]


def test_submit_rehire_request_fails_closed_when_llm_down(db_session, candidate):
    _seed_past_reject(db_session, candidate.candidateID)
    review = submit_rehire_request(
        db_session, candidate.candidateID, "Sam Lee", "Technical", None, "U-RECRUITER",
        "Candidate upskilled.",
        llm_call=_broken_llm,
    )
    assert review.status == "PENDING_HM_APPROVAL"
    assert review.ai_reasoning == FAIL_CLOSED_REASONING


# ---------------------------------------------------------------------------
# decide_rehire_review -- HM decision
# ---------------------------------------------------------------------------

def test_hm_approve_creates_the_panel_for_real(db_session, candidate):
    _seed_past_reject(db_session, candidate.candidateID)
    review = submit_rehire_request(
        db_session, candidate.candidateID, "Sam Lee", "Technical", None, "U-RECRUITER",
        "Weak justification.", llm_call=_escalate_llm,
    )
    assert review.status == "PENDING_HM_APPROVAL"

    decided = decide_rehire_review(db_session, review.id, "approve", "U-HM", note="Approved after phone screen")
    assert decided.status == "APPROVED"
    assert decided.resulting_panel_id is not None

    panel = db_session.query(InterviewPanel).filter(InterviewPanel.id == decided.resulting_panel_id).first()
    assert panel is not None
    assert panel.candidate_id == candidate.candidateID
    assert panel.round_name == "Technical"


def test_hm_reject_creates_no_panel(db_session, candidate):
    _seed_past_reject(db_session, candidate.candidateID)
    review = submit_rehire_request(
        db_session, candidate.candidateID, "Sam Lee", "Technical", None, "U-RECRUITER",
        "Weak justification.", llm_call=_escalate_llm,
    )

    decided = decide_rehire_review(db_session, review.id, "reject", "U-HM")
    assert decided.status == "REJECTED"
    assert decided.resulting_panel_id is None
    assert db_session.query(InterviewPanel).count() == 1  # only the original rejected-round panel from setup


def test_deciding_unknown_review_raises(db_session):
    with pytest.raises(RehireReviewNotFound):
        decide_rehire_review(db_session, 99999, "approve", "U-HM")


def test_deciding_an_already_decided_review_raises(db_session, candidate):
    _seed_past_reject(db_session, candidate.candidateID)
    review = submit_rehire_request(
        db_session, candidate.candidateID, "Sam Lee", "Technical", None, "U-RECRUITER",
        "Weak justification.", llm_call=_escalate_llm,
    )
    decide_rehire_review(db_session, review.id, "approve", "U-HM")
    with pytest.raises(RehireReviewAlreadyDecided):
        decide_rehire_review(db_session, review.id, "reject", "U-HM-2")
