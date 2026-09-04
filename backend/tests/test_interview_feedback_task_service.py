"""
Interview feedback Task linkage backlog item, 2026-08-05
(wros_interview_regrouping_and_rehire_guard_priority): a real Task per
panel member's pending feedback, scoped to (candidate, interview/round)
via Task.interview_id -- distinct from the pending-HM-decision Task
(category=INTERVIEW_REVIEW, see interviews.py::_create_hm_review_task).
Throwaway SQLite -- never the real database.
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
from app.models.user import Interview, InterviewFeedback, InterviewPanel, Jobs, PanelMember, Users

from app.services.interview_feedback_task_service import (
    close_pending_feedback_task,
    sync_pending_feedback_tasks_for_interview,
)

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Jobs.__table__, Candidate.__table__,
        InterviewPanel.__table__, PanelMember.__table__, Interview.__table__,
        InterviewFeedback.__table__, Task.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

def _make_candidate(db, candidate_id="C-1"):
    candidate = Candidate(
        candidateID=candidate_id, candidateEmail=f"{candidate_id}@example.com",
        candidatePassword="h", candidateFirstName="Priya", candidateLastName="Rao",
    )
    db.add(candidate)
    db.commit()
    return candidate

def _make_interviewer(db, user_id="U-INT-1"):
    u = Users(UserID=user_id, UserRole="employee", UserEmail=f"{user_id}@blitzenx.com", UserPassword="h")
    db.add(u)
    db.commit()
    return u

def _make_job(db, job_id="J-1", title="Guidewire Developer"):
    job = Jobs(
        jobID=job_id, jobTitle=title, jobDescription="desc", jobSkills="Guidewire",
        jobExperience="3-5", jobLocation="Remote",
    )
    db.add(job)
    db.commit()
    return job

def _make_panel_and_interview(db, candidate_id="C-1", job_id=None, round_name="L1"):
    panel = InterviewPanel(candidate_id=candidate_id, job_id=job_id, round_name=round_name)
    db.add(panel)
    db.commit()
    interview = Interview(panel_id=panel.id, candidate_id=candidate_id, status="Scheduled")
    db.add(interview)
    db.commit()
    return panel, interview

def test_creates_one_task_per_panel_member_with_no_feedback(db_session):
    _make_candidate(db_session, "C-1")
    _make_interviewer(db_session, "U-INT-1")
    _make_interviewer(db_session, "U-INT-2")
    _make_job(db_session, "J-1")
    panel, interview = _make_panel_and_interview(db_session, "C-1", job_id="J-1", round_name="L1")
    db_session.add_all([
        PanelMember(panel_id=panel.id, interviewer_id="U-INT-1"),
        PanelMember(panel_id=panel.id, interviewer_id="U-INT-2"),
    ])
    db_session.commit()

    sync_pending_feedback_tasks_for_interview(db_session, interview)

    tasks = db_session.query(Task).filter(Task.category == "INTERVIEW_FEEDBACK").all()
    assert len(tasks) == 2
    assignees = {t.assigned_to_user_id for t in tasks}
    assert assignees == {"U-INT-1", "U-INT-2"}
    for t in tasks:
        assert t.candidate_id == "C-1"
        assert t.interview_id == interview.id
        assert "Guidewire Developer" in t.title
        assert "L1" in t.title

def test_skips_member_who_already_submitted_feedback(db_session):
    _make_candidate(db_session, "C-1")
    _make_interviewer(db_session, "U-INT-1")
    panel, interview = _make_panel_and_interview(db_session, "C-1")
    db_session.add(PanelMember(panel_id=panel.id, interviewer_id="U-INT-1"))
    db_session.add(InterviewFeedback(
        interview_id=interview.id, interviewer_id="U-INT-1",
        technical_score=8, communication_score=8, problem_solving_score=8,
        culture_fit_score=8, recommendation="Hire",
    ))
    db_session.commit()

    sync_pending_feedback_tasks_for_interview(db_session, interview)

    assert db_session.query(Task).filter(Task.category == "INTERVIEW_FEEDBACK").count() == 0

def test_does_not_duplicate_task_on_second_sync_call(db_session):
    """Mirrors the real call site: assign_panel_member() re-syncs every
    active interview on the panel each time a new member joins."""
    _make_candidate(db_session, "C-1")
    _make_interviewer(db_session, "U-INT-1")
    panel, interview = _make_panel_and_interview(db_session, "C-1")
    db_session.add(PanelMember(panel_id=panel.id, interviewer_id="U-INT-1"))
    db_session.commit()

    sync_pending_feedback_tasks_for_interview(db_session, interview)
    sync_pending_feedback_tasks_for_interview(db_session, interview)

    assert db_session.query(Task).filter(Task.category == "INTERVIEW_FEEDBACK").count() == 1

def test_close_marks_the_right_members_task_completed(db_session):
    _make_candidate(db_session, "C-1")
    _make_interviewer(db_session, "U-INT-1")
    _make_interviewer(db_session, "U-INT-2")
    panel, interview = _make_panel_and_interview(db_session, "C-1")
    db_session.add_all([
        PanelMember(panel_id=panel.id, interviewer_id="U-INT-1"),
        PanelMember(panel_id=panel.id, interviewer_id="U-INT-2"),
    ])
    db_session.commit()
    sync_pending_feedback_tasks_for_interview(db_session, interview)

    close_pending_feedback_task(db_session, interview.id, "U-INT-1")

    tasks = {t.assigned_to_user_id: t for t in db_session.query(Task).filter(Task.category == "INTERVIEW_FEEDBACK").all()}
    assert tasks["U-INT-1"].status == "COMPLETED"
    assert tasks["U-INT-1"].completed_at is not None
    assert tasks["U-INT-2"].status == "NEW"

def test_close_is_a_no_op_when_no_task_exists(db_session):
    close_pending_feedback_task(db_session, 999, "U-GHOST")  # must not raise

def test_scoped_per_round_not_clubbed_across_candidates_other_jobs(db_session):
    """The whole point of Task.interview_id: two different rounds for
    the same candidate+interviewer must produce two separate tasks."""
    _make_candidate(db_session, "C-1")
    _make_interviewer(db_session, "U-INT-1")
    _make_job(db_session, "J-1", title="Guidewire Developer")
    _make_job(db_session, "J-2", title="Java Backend Engineer")
    panel_a, interview_a = _make_panel_and_interview(db_session, "C-1", job_id="J-1", round_name="L1")
    panel_b, interview_b = _make_panel_and_interview(db_session, "C-1", job_id="J-2", round_name="L1")
    db_session.add_all([
        PanelMember(panel_id=panel_a.id, interviewer_id="U-INT-1"),
        PanelMember(panel_id=panel_b.id, interviewer_id="U-INT-1"),
    ])
    db_session.commit()

    sync_pending_feedback_tasks_for_interview(db_session, interview_a)
    sync_pending_feedback_tasks_for_interview(db_session, interview_b)

    tasks = db_session.query(Task).filter(Task.category == "INTERVIEW_FEEDBACK").all()
    assert len(tasks) == 2
    interview_ids = {t.interview_id for t in tasks}
    assert interview_ids == {interview_a.id, interview_b.id}

    # Closing the task for round A must not touch round B's task.
    close_pending_feedback_task(db_session, interview_a.id, "U-INT-1")
    still_open = db_session.query(Task).filter(
        Task.category == "INTERVIEW_FEEDBACK", Task.interview_id == interview_b.id,
    ).first()
    assert still_open.status == "NEW"
