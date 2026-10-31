"""Job emails: created (written by the job_created_flash handler), approved, a new hiring manager or
recruiter on it, deleted. The people on a job: its hiring manager, recruiter, assigned recruiter
(employee login), creator and the head of its business unit for its client."""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import Jobs, Users
from app.services.action_emails.core import Team, add, after_commit, employee_login, name_of, send


def job_path(job_id: str) -> str:
    return f"/jobs/{job_id}/workspace"


def job_team(db: Session, job: Jobs) -> Team:
    from app.services.bu_leadership import head_for_client

    team: Team = {}
    add(team, job.hiringManagerID, "Hiring Manager")
    add(team, job.recuriterID, "Recruiter")
    add(team, employee_login(db, job.assigned_recruiter_employee_id), "Recruiter")
    add(team, job.created_by, "Created it")
    if job.business_unit_id is not None:
        add(team, head_for_client(db, job.business_unit_id, job.client_id), "BU Head")
    return team


def _title(job: Jobs) -> str:
    company = f" ({job.companyName})" if job.companyName else ""
    return f"{job.jobTitle or job.jobID}{company}"


def _facts(job: Jobs) -> str:
    facts = [f"Status: {job.jobStatus}"]
    if job.noOfPositions:
        facts.append(f"Positions: {job.noOfPositions}")
    if job.jobLocation:
        facts.append(f"Location: {job.jobLocation}")
    return ". ".join(facts) + "."


@after_commit("jobs")
def notify_job_created(db: Session, job: Jobs, *, actor_id: Optional[str]) -> int:
    by = name_of(db.query(Users).filter(Users.UserID == actor_id).first()) if actor_id else None
    return send(db, job_team(db, job), actor_id=actor_id, key=f"job-created-{job.jobID}",
                subject=f"New job: {_title(job)}",
                opening=f"{by or 'WROS'} created the job {_title(job)}.", details=[_facts(job)],
                link_path=job_path(job.jobID), link_label="Open the job")


@after_commit("jobs")
def notify_job_approved(db: Session, job: Jobs, *, actor: Users) -> int:
    return send(db, job_team(db, job), actor_id=actor.UserID, key=f"job-approved-{job.jobID}",
                subject=f"Job approved: {_title(job)}",
                opening=f"{name_of(actor)} approved the job {_title(job)}; it is live.", details=[_facts(job)],
                link_path=job_path(job.jobID), link_label="Open the job")


@after_commit("jobs")
def notify_job_assignees(db: Session, job: Jobs, *, actor: Users, previous_hiring_manager: Optional[str],
                         previous_recruiter: Optional[str]) -> int:
    """The new hiring manager and the new recruiter of an edited job (only those that changed)."""
    team: Team = {}
    if job.hiringManagerID != previous_hiring_manager:
        add(team, job.hiringManagerID, "Hiring Manager")
    if job.recuriterID != previous_recruiter:
        add(team, job.recuriterID, "Recruiter")
    queued = 0
    for user_id, roles in team.items():
        queued += send(db, {user_id: roles}, actor_id=actor.UserID,
                       key=f"job-assigned-{job.jobID}-{'-'.join(r.lower().replace(' ', '_') for r in roles)}",
                       subject=f"You are on the job {_title(job)}",
                       opening=f"{name_of(actor)} made you the {' and '.join(roles)} of the job {_title(job)}.",
                       details=[_facts(job)], link_path=job_path(job.jobID), link_label="Open the job")
    return queued


@after_commit("jobs")
def notify_job_deleted(db: Session, team: Team, *, job_id: str, title: str, actor: Users) -> int:
    """team is job_team() read before the delete (the row is gone after the commit)."""
    return send(db, team, actor_id=actor.UserID, key=f"job-deleted-{job_id}",
                subject=f"Job deleted: {title}", opening=f"{name_of(actor)} deleted the job {title}.",
                link_path="/jobs", link_label="Open Jobs")
