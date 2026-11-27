"""CEO 2026-11-27: a market candidate is screened and interviewed before there is a job, hired onto the bench, then
submitted to a client job; the job-less rounds (and that job's own rounds) are attached to the submission."""
from datetime import datetime

from app.models.client import Client
from app.models.submission import Submission, SubmissionInterviewRound
from app.models.user import Interview, InterviewPanel
from app.services.submission_service import submission_rounds, tag_interview_rounds
from tests import factories as f


def _panel(db, candidate, round_name, job_id=None, when=None):
    panel = InterviewPanel(candidate_id=candidate.candidateID, round_name=round_name, job_id=job_id)
    db.add(panel)
    db.flush()
    db.add(Interview(panel_id=panel.id, candidate_id=candidate.candidateID, start_time=when or datetime(2026, 11, 1),
                     end_time=when or datetime(2026, 11, 1), status="Completed"))
    db.flush()
    return panel


def _submission(db, candidate, job):
    client = Client(tenant_id=1, company_name=f"Client {f.uid()}")
    db.add(client)
    db.flush()
    submission = Submission(tenant_id=1, demand_id=job.jobID, client_id=client.id, candidate_id=candidate.candidateID)
    db.add(submission)
    db.flush()
    return submission


def test_job_less_rounds_and_this_jobs_rounds_go_with_the_submission(db):
    candidate = f.candidate(db)
    job, other_job = f.job(db), f.job(db)
    screening = _panel(db, candidate, "Screening", when=datetime(2026, 10, 1))
    l1 = _panel(db, candidate, "L1 Interview", when=datetime(2026, 10, 5))
    for_this_job = _panel(db, candidate, "Client", job_id=job.jobID, when=datetime(2026, 11, 2))
    _panel(db, candidate, "L1 Interview", job_id=other_job.jobID)  # another job's round stays out
    submission = _submission(db, candidate, job)

    assert tag_interview_rounds(db, submission) == 3
    rounds = submission_rounds(db, submission.id)
    assert [r.panel_id for r in rounds] == [screening.id, l1.id, for_this_job.id]
    assert [r.round_job_id for r in rounds] == [None, None, job.jobID]
    assert rounds[0].interviewed_at == datetime(2026, 10, 1)

    assert tag_interview_rounds(db, submission) == 0  # idempotent
    assert db.query(SubmissionInterviewRound).filter(SubmissionInterviewRound.submission_id == submission.id).count() == 3


def test_a_candidate_with_no_rounds_is_still_submitted(db):
    candidate = f.candidate(db)
    submission = _submission(db, candidate, f.job(db))
    assert tag_interview_rounds(db, submission) == 0
    assert submission_rounds(db, submission.id) == []


def test_screening_call_needs_no_verified_experience_but_l1_does(db):
    """CEO 2026-11-27: the screening call is where experience is verified; L1 onwards keep the 5-year rule, and a
    candidate verified under 5 years gets no screening call either."""
    import pytest
    from fastapi import HTTPException

    from app.services.interview_scheduling_service import require_experience

    unverified = f.candidate(db, total_experience_months=None)
    require_experience(unverified, "SCREEN")  # allowed
    with pytest.raises(HTTPException):
        require_experience(unverified, "L1")
    junior = f.candidate(db, total_experience_months=24)
    with pytest.raises(HTTPException):
        require_experience(junior, "SCREEN")
    require_experience(f.candidate(db, total_experience_months=72), "L1")
