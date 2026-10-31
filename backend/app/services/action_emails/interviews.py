"""Interview emails: scheduled, rescheduled, cancelled or deleted, an interviewer added to a panel,
and the hiring manager's round verdict. The people on an interview: the panel's interviewers, the
job's hiring manager and recruiter, and the candidate's assigned recruiter.

On a new interview each interviewer already gets the feedback task's email (task_notification_
service), so the scheduled email goes to the hiring manager and recruiters only; a new time or a
cancellation goes to everyone, interviewers included."""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.user import Interview, InterviewPanel, Jobs, PanelMember, Users
from app.services.action_emails.core import Team, add, after_commit, name_of, send


def _candidate(db: Session, candidate_id: str) -> Optional[Candidate]:
    return db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()


def _candidate_name(candidate: Optional[Candidate], candidate_id: str) -> str:
    if candidate is None:
        return candidate_id
    return f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip() or candidate_id


def candidate_path(candidate_id: str) -> str:
    return f"/candidates/{candidate_id}"


def interview_team(db: Session, panel: InterviewPanel, *, interviewers: bool = True) -> Team:
    team: Team = {}
    if interviewers:
        for (user_id,) in db.query(PanelMember.interviewer_id).filter(PanelMember.panel_id == panel.id).all():
            add(team, user_id, "Interviewer")
    job = db.query(Jobs).filter(Jobs.jobID == panel.job_id).first() if panel.job_id else None
    if job is not None:
        add(team, job.hiringManagerID, "Hiring Manager")
        add(team, job.recuriterID, "Recruiter")
    candidate = _candidate(db, panel.candidate_id)
    if candidate is not None:
        add(team, candidate.assigned_recruiter_id, "Candidate's Recruiter")
    return team


def _round(panel: InterviewPanel, candidate_name: str) -> str:
    return f"{panel.round_name or 'Interview'} round with {candidate_name}"


def _when(interview: Interview) -> str:
    when = f"When: {interview.start_time:%Y-%m-%d %H:%M}-{interview.end_time:%H:%M} UTC."
    return when + (f" Link: {interview.meeting_link}" if interview.meeting_link else "")


@after_commit("interviews")
def notify_interview_scheduled(db: Session, interview: Interview, panel: InterviewPanel, *, actor: Users) -> int:
    name = _candidate_name(_candidate(db, interview.candidate_id), interview.candidate_id)
    return send(db, interview_team(db, panel, interviewers=False), actor_id=actor.UserID,
                key=f"interview-scheduled-{interview.id}", subject=f"Interview scheduled: {_round(panel, name)}",
                opening=f"{name_of(actor)} scheduled the {_round(panel, name)}.", details=[_when(interview)],
                link_path=candidate_path(interview.candidate_id), link_label="Open the candidate")


@after_commit("interviews")
def notify_interview_changed(db: Session, interview: Interview, *, actor: Users, rescheduled: bool,
                             cancelled: bool) -> int:
    """A new time and / or a cancellation of an existing interview, to everyone on it."""
    if not (rescheduled or cancelled):
        return 0
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
    if panel is None:
        raise ValueError(f"Interview {interview.id} has unknown panel {interview.panel_id}")
    name = _candidate_name(_candidate(db, interview.candidate_id), interview.candidate_id)
    if cancelled:
        key, subject = f"interview-cancelled-{interview.id}", f"Interview cancelled: {_round(panel, name)}"
        opening = f"{name_of(actor)} cancelled the {_round(panel, name)}."
    else:
        key = f"interview-rescheduled-{interview.id}-{interview.start_time:%Y%m%dT%H%M}"
        subject = f"Interview moved: {_round(panel, name)}"
        opening = f"{name_of(actor)} moved the {_round(panel, name)} to a new time."
    return send(db, interview_team(db, panel), actor_id=actor.UserID, key=key, subject=subject, opening=opening,
                details=[] if cancelled else [_when(interview)],
                link_path=candidate_path(interview.candidate_id), link_label="Open the candidate")


@after_commit("interviews")
def notify_interview_deleted(db: Session, team: Team, *, interview_id: int, round_label: str,
                             candidate_id: str, actor: Users) -> int:
    """team and round_label are read before the delete (the rows are gone after the commit)."""
    return send(db, team, actor_id=actor.UserID, key=f"interview-deleted-{interview_id}",
                subject=f"Interview removed: {round_label}",
                opening=f"{name_of(actor)} removed the {round_label} from WROS.",
                link_path=candidate_path(candidate_id), link_label="Open the candidate")


def deleted_interview_context(db: Session, interview: Interview):
    """(team, round label) of an interview about to be deleted."""
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
    name = _candidate_name(_candidate(db, interview.candidate_id), interview.candidate_id)
    if panel is None:
        return {}, f"interview with {name}"
    return interview_team(db, panel), _round(panel, name)


@after_commit("interviews")
def notify_panel_member_added(db: Session, member: PanelMember, *, actor: Users) -> int:
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == member.panel_id).first()
    if panel is None:
        raise ValueError(f"Panel member {member.id} has unknown panel {member.panel_id}")
    name = _candidate_name(_candidate(db, panel.candidate_id), panel.candidate_id)
    return send(db, {member.interviewer_id: ["Interviewer"]}, actor_id=actor.UserID,
                key=f"interview-panel-member-{member.id}", subject=f"You are on the panel: {_round(panel, name)}",
                opening=f"{name_of(actor)} added you as an interviewer on the {_round(panel, name)}.",
                details=["Each scheduled interview of this round puts a feedback task on My Tasks."],
                link_path=candidate_path(panel.candidate_id), link_label="Open the candidate")


@after_commit("interviews")
def notify_round_verdict(db: Session, panel: InterviewPanel, verdict: str, *, actor: Users,
                         rationale: Optional[str]) -> int:
    name = _candidate_name(_candidate(db, panel.candidate_id), panel.candidate_id)
    result = "passed" if verdict == "PASS" else "did not pass"
    return send(db, interview_team(db, panel), actor_id=actor.UserID,
                key=f"interview-verdict-{panel.id}-{verdict}",
                subject=f"Round {verdict.lower()}: {_round(panel, name)}",
                opening=f"{name_of(actor)} decided that {name} {result} the {panel.round_name or 'interview'} round.",
                details=[f"Rationale: {rationale}" if rationale else None],
                link_path=candidate_path(panel.candidate_id), link_label="Open the candidate")
