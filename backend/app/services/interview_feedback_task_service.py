"""
Interview feedback Task linkage. Backlog item, 2026-08-05
(wros_interview_regrouping_and_rehire_guard_priority): Avinash asked
whether the Task system (S-434) already distinguishes "interviewer
hasn't submitted feedback yet" from "hiring manager hasn't decided
yet" -- it didn't (zero create_task() calls anywhere in the interview
feedback flow). This module is the "pending-feedback" half; the
"pending-HM-decision" half already exists as
import logging
interviews.py::_create_hm_review_task() (category=INTERVIEW_REVIEW).

Real requirement: these must be real, separately-scoped Tasks per
(candidate, job, round) -- not clubbed across a candidate's other
rounds/jobs. Task.interview_id (added this same backlog item) is what
makes that scoping real instead of just a title convention.

One Task per (candidate_id, interview_id, assigned_to_user_id) -- never
duplicated if this runs again for the same interview (e.g. a new panel
member joins after the interview already exists, or a panel member
resubmits). Closed the moment that specific interviewer submits
feedback. Never raises -- a Task-sync bug must never block scheduling
an interview or submitting feedback, same fire-and-forget posture as
document_task_service.py and interviews.py::_create_hm_review_task.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.task import Task
from app.models.user import Interview, InterviewFeedback, InterviewPanel, Jobs, PanelMember
from app.services.task_service import create_task

FEEDBACK_TASK_CATEGORY = "INTERVIEW_FEEDBACK"

def _candidate_display_name(candidate: Optional[Candidate]) -> str:
    if not candidate:
        return "Unknown Candidate"
    parts = [candidate.candidateFirstName or "", candidate.candidateLastName or ""]
    return " ".join(p for p in parts if p).strip() or candidate.candidateID

def _existing_feedback_task(db: Session, candidate_id: str, interview_id: int, interviewer_id: str) -> Optional[Task]:
    return (
        db.query(Task)
        .filter(
            Task.candidate_id == candidate_id,
            Task.interview_id == interview_id,
            Task.assigned_to_user_id == interviewer_id,
            Task.category == FEEDBACK_TASK_CATEGORY,
        )
        .order_by(Task.id.desc())
        .first()
    )

def sync_pending_feedback_tasks_for_interview(db: Session, interview: Interview) -> None:
    """Call whenever the set of panel members for an interview may have
    changed (interview creation, a new panel member assigned to an
    already-existing interview) -- creates exactly one open Task per
    panel member who hasn't submitted feedback yet and doesn't already
    have one for this interview."""
    try:
        panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
        if not panel:
            return
        members = db.query(PanelMember).filter(PanelMember.panel_id == panel.id).all()
        if not members:
            return

        candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
        candidate_name = _candidate_display_name(candidate)
        round_name = panel.round_name or "Interview"
        job_title = None
        if panel.job_id:
            job = db.query(Jobs).filter(Jobs.jobID == panel.job_id).first()
            job_title = job.jobTitle if job else None
        scope_label = f"{job_title} -- {round_name}" if job_title else round_name

        submitted_ids = {
            fb.interviewer_id
            for fb in db.query(InterviewFeedback).filter(InterviewFeedback.interview_id == interview.id).all()
        }

        created_any = False
        for member in members:
            if member.interviewer_id in submitted_ids:
                continue
            if _existing_feedback_task(db, interview.candidate_id, interview.id, member.interviewer_id):
                continue

            task = create_task(
                db,
                title=f"Submit feedback: {candidate_name} -- {scope_label}",
                description=(
                    f"Your feedback for {candidate_name}'s {scope_label} interview round "
                    f"has not been submitted yet."
                ),
                priority="MEDIUM",
                assigned_to_user_id=member.interviewer_id,
                visibility_scope="ASSIGNEE_MANAGER_DEPARTMENT",
                task_type="GENERAL",
                category=FEEDBACK_TASK_CATEGORY,
                due_date=interview.end_time,
            )
            task.candidate_id = interview.candidate_id
            task.interview_id = interview.id
            db.add(task)
            created_any = True

        if created_any:
            db.commit()
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[InterviewFeedbackTask] Failed to sync pending-feedback tasks for interview {interview.id}: {exc}")
        db.rollback()

def close_pending_feedback_task(db: Session, interview_id: int, interviewer_id: str) -> None:
    """Call the moment an interviewer submits their feedback."""
    try:
        task = (
            db.query(Task)
            .filter(
                Task.interview_id == interview_id,
                Task.assigned_to_user_id == interviewer_id,
                Task.category == FEEDBACK_TASK_CATEGORY,
                Task.status != "COMPLETED",
            )
            .first()
        )
        if task is None:
            return
        task.status = "COMPLETED"
        task.completed_at = datetime.utcnow()
        db.add(task)
        db.commit()
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(
            f"[InterviewFeedbackTask] Failed to close pending-feedback task for interview "
            f"{interview_id}, interviewer {interviewer_id}: {exc}"
        )
        db.rollback()
