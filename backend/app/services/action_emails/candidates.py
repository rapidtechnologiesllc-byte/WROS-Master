"""Internal emails about a candidate (the candidate's own emails go through Thunder, never here): a
recruiter assigned to them (by a person or by auto-assignment), HR assigned to their onboarding,
and a pipeline status change. The people on a candidate: their assigned recruiter, their HR
(hr1, hr2) and the hiring manager and recruiter of the job they are on."""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.hr_assignment import HRAssignment
from app.models.user import Jobs, Users
from app.services.action_emails.core import Team, add, after_commit, name_of, send


def candidate_path(candidate_id: str) -> str:
    return f"/candidates/{candidate_id}"


def _name(candidate: Candidate) -> str:
    return f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip() or candidate.candidateID


def candidate_team(db: Session, candidate: Candidate) -> Team:
    team: Team = {}
    add(team, candidate.assigned_recruiter_id, "Recruiter")
    hr = db.query(HRAssignment).filter(HRAssignment.candidate_id == candidate.candidateID).first()
    if hr is not None:
        add(team, hr.hr1_id, "HR")
        add(team, hr.hr2_id, "HR (second)")
    job = db.query(Jobs).filter(Jobs.jobID == candidate.job_id).first() if candidate.job_id else None
    if job is not None:
        add(team, job.hiringManagerID, "Hiring Manager")
        add(team, job.recuriterID, "Job Recruiter")
    return team


@after_commit("candidates")
def notify_recruiter_assigned(db: Session, candidate: Candidate, *, actor_id: Optional[str]) -> int:
    """actor_id None: assigned by WROS (auto-assignment), so the recruiter is always told."""
    if not candidate.assigned_recruiter_id:
        return 0
    by = name_of(db.get(Users, actor_id)) if actor_id else None
    return send(db, {candidate.assigned_recruiter_id: ["Recruiter"]}, actor_id=actor_id,
                key=f"candidate-recruiter-{candidate.candidateID}",
                subject=f"New candidate for you: {_name(candidate)}",
                opening=f"{by or 'WROS'} made you the recruiter of {_name(candidate)}.",
                details=[f"Email: {candidate.candidateEmail}." if candidate.candidateEmail else None],
                link_path=candidate_path(candidate.candidateID), link_label="Open the candidate")


@after_commit("candidates")
def notify_hr_assigned(db: Session, assignment: HRAssignment, *, actor: Users,
                       previous: Optional[set] = None) -> int:
    """hr1 / hr2 who are new on the assignment (previous: the user ids it had before an edit)."""
    candidate = db.query(Candidate).filter(Candidate.candidateID == assignment.candidate_id).first()
    if candidate is None:
        raise ValueError(f"HR assignment {assignment.id} has unknown candidate {assignment.candidate_id}")
    team: Team = {}
    for user_id, role in ((assignment.hr1_id, "HR"), (assignment.hr2_id, "HR (second)")):
        if user_id not in (previous or set()):
            add(team, user_id, role)
    return send(db, team, actor_id=actor.UserID, key=f"candidate-hr-{assignment.id}",
                subject=f"HR for {_name(candidate)}",
                opening=f"{name_of(actor)} assigned you as HR for {_name(candidate)}'s onboarding.",
                link_path=candidate_path(candidate.candidateID), link_label="Open the candidate")


@after_commit("candidates")
def notify_pipeline_status(db: Session, candidate: Candidate, *, actor: Users, old_status: Optional[str],
                           new_status: str) -> int:
    if old_status == new_status:
        return 0
    return send(db, candidate_team(db, candidate), actor_id=actor.UserID,
                key=f"candidate-status-{candidate.candidateID}-{new_status}",
                subject=f"{_name(candidate)}: {new_status}",
                opening=f"{name_of(actor)} moved {_name(candidate)} from {old_status or 'no status'} to {new_status}.",
                link_path=candidate_path(candidate.candidateID), link_label="Open the candidate")
