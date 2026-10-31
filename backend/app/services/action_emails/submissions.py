"""Submission emails: a candidate submitted to a client job, and each client response recorded on it
(shortlisted, interview, rejected, placed...). The people on a submission: who submitted it, the
job's hiring manager and recruiter, the candidate's assigned recruiter and the client's team."""
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.client import Client
from app.models.submission import Submission
from app.models.user import Jobs, Users
from app.services.action_emails.core import Team, add, after_commit, client_team, merge, name_of, send

SUBMISSIONS_PATH = "/pipeline?view=submissions"


def submission_team(db: Session, submission: Submission) -> Team:
    team: Team = {}
    add(team, submission.submitted_by_user_id, "Submitted it")
    job = db.query(Jobs).filter(Jobs.jobID == submission.demand_id).first()
    if job is not None:
        add(team, job.hiringManagerID, "Hiring Manager")
        add(team, job.recuriterID, "Recruiter")
    candidate = db.query(Candidate).filter(Candidate.candidateID == submission.candidate_id).first()
    if candidate is not None:
        add(team, candidate.assigned_recruiter_id, "Candidate's Recruiter")
    merge(team, client_team(db, submission.client_id))
    return team


def _label(db: Session, submission: Submission) -> str:
    candidate = db.query(Candidate).filter(Candidate.candidateID == submission.candidate_id).first()
    name = (f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip()
            if candidate is not None else "") or submission.candidate_id
    job = db.query(Jobs).filter(Jobs.jobID == submission.demand_id).first()
    client = db.query(Client).filter(Client.id == submission.client_id).first()
    where = " for ".join(p for p in [job.jobTitle if job else None, client.company_name if client else None] if p)
    return f"{name} to {where}" if where else name


@after_commit("submissions")
def notify_submitted(db: Session, submission: Submission, *, actor: Users) -> int:
    label = _label(db, submission)
    return send(db, submission_team(db, submission), actor_id=actor.UserID, key=f"submission-created-{submission.id}",
                subject=f"Submitted: {label}", opening=f"{name_of(actor)} submitted {label}.",
                link_path=SUBMISSIONS_PATH, link_label="Open Submissions")


@after_commit("submissions")
def notify_client_response(db: Session, submission: Submission, *, actor: Users) -> int:
    label = _label(db, submission)
    status = submission.status.replace("_", " ").lower()
    return send(db, submission_team(db, submission), actor_id=actor.UserID,
                key=f"submission-response-{submission.id}-{submission.status}",
                subject=f"Client response ({status}): {label}",
                opening=f"{name_of(actor)} recorded the client's response to {label}: {status}.",
                details=[f"Client feedback: {submission.client_feedback}" if submission.client_feedback else None],
                link_path=SUBMISSIONS_PATH, link_label="Open Submissions")
