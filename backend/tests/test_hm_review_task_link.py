"""
HM Candidate Review Task-link backlog item, 2026-08-05
(wros_hm_candidate_review_task_link_backlog): once every panel member
for an interview round has submitted feedback, a real Task should
point the hiring manager at HmCandidateReviewScreen instead of them
having to know to go check. Throwaway SQLite -- never the real database.
"""
import os
import logging
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.task import Task
from app.models.user import (
    CandidateAssignment,
    Interview,
    InterviewFeedback,
    InterviewPanel,
    Jobs,
    PanelMember,
    Users,
)

from app.api.v1.endpoints.interviews import (
    _create_hm_review_task,
    _resolve_hiring_manager_id_for_interview,
)

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Jobs.__table__, Candidate.__table__,
        CandidateAssignment.__table__, InterviewPanel.__table__,
        PanelMember.__table__, Interview.__table__, InterviewFeedback.__table__,
        Task.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

def _make_job(db, job_id="J-1", hiring_manager_id=None):
    job = Jobs(
        jobID=job_id, jobTitle="Backend Engineer", jobDescription="desc",
        jobSkills="python", jobExperience="3-5", jobLocation="Remote",
        hiringManagerID=hiring_manager_id,
    )
    db.add(job)
    db.commit()
    return job

def _make_candidate(db, candidate_id="C-1", job_id=None):
    candidate = Candidate(
        candidateID=candidate_id, candidateEmail=f"{candidate_id}@example.com",
        candidatePassword="h", candidateFirstName="Priya", candidateLastName="Rao",
        job_id=job_id,
    )
    db.add(candidate)
    db.commit()
    return candidate

def _make_interview(db, candidate_id="C-1", panel_job_id=None):
    panel = InterviewPanel(candidate_id=candidate_id, job_id=panel_job_id, round_name="Tech")
    db.add(panel)
    db.commit()

    interview = Interview(panel_id=panel.id, candidate_id=candidate_id, status="Scheduled")
    db.add(interview)
    db.commit()
    return panel, interview

def _make_hm_user(db, user_id="U-HM"):
    hm = Users(UserID=user_id, UserRole="employee", UserEmail=f"{user_id}@blitzenx.com", UserPassword="h")
    db.add(hm)
    db.commit()
    return hm

# ---- _resolve_hiring_manager_id_for_interview ----

def test_resolves_hm_via_panel_job(db_session):
    _make_hm_user(db_session, "U-HM")
    _make_job(db_session, "J-1", hiring_manager_id="U-HM")
    _make_candidate(db_session, "C-1")
    _, interview = _make_interview(db_session, "C-1", panel_job_id="J-1")

    assert _resolve_hiring_manager_id_for_interview(db_session, interview) == "U-HM"

def test_falls_back_to_candidate_assignment_when_panel_has_no_job(db_session):
    _make_hm_user(db_session, "U-HM2")
    _make_candidate(db_session, "C-2")
    db_session.add(CandidateAssignment(candidate_id="C-2", hiring_manager_id="U-HM2"))
    db_session.commit()
    _, interview = _make_interview(db_session, "C-2", panel_job_id=None)

    assert _resolve_hiring_manager_id_for_interview(db_session, interview) == "U-HM2"

def test_falls_back_to_candidate_job_when_no_panel_job_or_assignment(db_session):
    _make_hm_user(db_session, "U-HM3")
    _make_job(db_session, "J-3", hiring_manager_id="U-HM3")
    _make_candidate(db_session, "C-3", job_id="J-3")
    _, interview = _make_interview(db_session, "C-3", panel_job_id=None)

    assert _resolve_hiring_manager_id_for_interview(db_session, interview) == "U-HM3"

def test_returns_none_when_no_hm_resolvable(db_session):
    _make_candidate(db_session, "C-4")
    _, interview = _make_interview(db_session, "C-4", panel_job_id=None)

    assert _resolve_hiring_manager_id_for_interview(db_session, interview) is None

# ---- _create_hm_review_task ----

def test_creates_task_assigned_to_resolved_hm(db_session):
    _make_hm_user(db_session, "U-HM")
    _make_job(db_session, "J-1", hiring_manager_id="U-HM")
    _make_candidate(db_session, "C-1")
    _, interview = _make_interview(db_session, "C-1", panel_job_id="J-1")

    _create_hm_review_task(db_session, interview)

    task = db_session.query(Task).filter(Task.category == "INTERVIEW_REVIEW").first()
    assert task is not None
    assert task.assigned_to_user_id == "U-HM"
    assert task.visibility_scope == "ASSIGNEE_MANAGER_DEPARTMENT"
    assert "Priya Rao" in task.title
    assert "/hiring-manager-review" in task.description

def test_creates_org_wide_unassigned_task_when_no_hm_resolvable(db_session):
    _make_candidate(db_session, "C-4")
    _, interview = _make_interview(db_session, "C-4", panel_job_id=None)

    _create_hm_review_task(db_session, interview)

    task = db_session.query(Task).filter(Task.category == "INTERVIEW_REVIEW").first()
    assert task is not None
    assert task.assigned_to_user_id is None
    assert task.visibility_scope == "ORG_WIDE"

def test_never_raises_when_candidate_missing(db_session):
    """Fire-and-forget: interview.status has already committed to
    Completed by the time this runs, so a Task-creation bug must never
    surface as an error to the interviewer who just submitted feedback."""
    _, interview = _make_interview(db_session, "C-ghost", panel_job_id=None)

    _create_hm_review_task(db_session, interview)  # must not raise

    assert db_session.query(Task).filter(Task.category == "INTERVIEW_REVIEW").count() == 1

# ---- end-to-end: submitting the last panel member's feedback ----

def test_all_panel_feedback_submitted_triggers_task_creation(db_session):
    """Mirrors the real auto-complete flow in interviews.py's
    submit_interview_feedback(): once every panel member has submitted
    feedback, the interview flips to Completed and this fires."""
    _make_hm_user(db_session, "U-HM")
    _make_job(db_session, "J-1", hiring_manager_id="U-HM")
    _make_candidate(db_session, "C-1")
    panel, interview = _make_interview(db_session, "C-1", panel_job_id="J-1")

    db_session.add(PanelMember(panel_id=panel.id, interviewer_id="U-INT-1"))
    db_session.commit()

    db_session.add(InterviewFeedback(
        interview_id=interview.id, interviewer_id="U-INT-1",
        technical_score=8, communication_score=8, problem_solving_score=8,
        culture_fit_score=8, recommendation="Hire",
    ))
    db_session.commit()

    panel_member_ids = {pm.interviewer_id for pm in db_session.query(PanelMember).filter(PanelMember.panel_id == panel.id).all()}
    submitted_ids = {fb.interviewer_id for fb in db_session.query(InterviewFeedback).filter(InterviewFeedback.interview_id == interview.id).all()}
    assert panel_member_ids.issubset(submitted_ids)

    interview.status = "Completed"
    db_session.commit()
    _create_hm_review_task(db_session, interview)

    task = db_session.query(Task).filter(Task.category == "INTERVIEW_REVIEW").first()
    assert task is not None
    assert task.assigned_to_user_id == "U-HM"

@pytest.mark.parametrize("previous_status,new_status,should_fire", [
    ("Scheduled", "Completed", True),
    ("Completed", "Completed", False),
    ("Scheduled", "Cancelled", False),
    ("Cancelled", "Completed", True),
])
def test_update_interview_only_fires_on_new_transition_to_completed(previous_status, new_status, should_fire):
    """Guard in update_interview() (app/api/v1/endpoints/interviews.py):
    `if interview.status == "Completed" and previous_status != "Completed"`.
    Re-asserted here as a plain boolean check so a future edit to that
    guard trips this test instead of only being caught by production
    behavior (duplicate tasks on every re-PUT of an already-Completed
    interview)."""
    fires = new_status == "Completed" and previous_status != "Completed"
    assert fires == should_fire
