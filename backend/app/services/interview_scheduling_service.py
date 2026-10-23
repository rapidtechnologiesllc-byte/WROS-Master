"""The one way an interview round is set up: a panel, its interviewers, the interview itself.

The Interviews screens (POST /interviews/panels/create, /panel-members/assign, /create) and
Flash both call these functions, acting as the requesting user. Every gate runs at every step
(CEO 2026-10-10: the 5-year rule wherever it applies), so scheduling an interview re-checks
the experience floor, the round sequencing (L2 only after an L1 pass) and the rehire guard that
creating the panel already checked: facts can change between the two calls.

Nothing here commits; the caller commits, then calls the matching after_* function, which
queues the side effects (so a rolled-back interview never leaves a queued message behind).
Gate failures raise HTTPException, the repo convention the scope helpers already follow.

Times are stored as naive UTC. An aware datetime is converted; a naive one is taken as UTC
(every screen sends ISO 8601 with an offset).
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.bu_scope import candidate_scope_filter, ensure_candidate_visible
from app.core.data_scope import job_filter, visible_job_or_404
from app.models.candidate import Candidate
from app.models.interview_rehire_review import InterviewRehireReview
from app.models.user import Interview, InterviewPanel, Jobs, PanelMember, Users

logger = logging.getLogger(__name__)

INTERVIEW_SCHEDULED_TASK = "interview_scheduled"
INVITE_KIND = "INTERVIEW_INVITE"
CLEARED_REHIRE_STATUSES = ("AI_CLEARED", "APPROVED")


@dataclass
class PanelCreated:
    panel: InterviewPanel
    job: Optional[Jobs]
    level: str
    verdict: str
    rehire_review_id: Optional[int] = None
    rehire_cleared_by: Optional[str] = None


# --------------------------------------------------------------------------- scope and time

def panel_scope(db: Session, user):
    """WHERE clause on InterviewPanel: its candidate and its job are in the caller's scope."""
    return and_(candidate_scope_filter(db, user, InterviewPanel.candidate_id),
                job_filter(db, user, InterviewPanel.job_id))


def visible_panel_or_404(db: Session, user, panel_id: int) -> InterviewPanel:
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == panel_id, panel_scope(db, user)).first()
    if panel is None:
        raise HTTPException(status_code=404, detail=f"Interview panel with ID {panel_id} not found")
    return panel


def to_naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Storage convention for interview times: naive UTC."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def candidate_display_name(candidate: Optional[Candidate]) -> str:
    if candidate is None:
        return "N/A"
    parts = [candidate.candidateFirstName, candidate.candidateMiddleName, candidate.candidateLastName]
    return " ".join(p for p in parts if p).strip() or "N/A"


# --------------------------------------------------------------------------- gates

def require_experience(candidate: Candidate) -> None:
    """CEO rule: nobody under 5 years' experience (or unverified) is interviewed."""
    from app.services.submission_service import ExperienceIneligible, assert_experience_eligible

    try:
        assert_experience_eligible(candidate, "schedule an interview")
    except ExperienceIneligible as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def require_employment_type(candidate: Candidate) -> None:
    """Interview selection (CEO 2026-10-15): an explicit C2C/1099, or a type the candidate's
    country does not accept, is not interviewed; UNKNOWN may interview."""
    from app.services.employment_type_policy import EmploymentTypeNotAccepted, assert_may_interview

    try:
        assert_may_interview(candidate, "schedule an interview")
    except EmploymentTypeNotAccepted as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _require_sequencing(db: Session, candidate_id: str, level: str, job_id: Optional[str],
                        panel: Optional[InterviewPanel] = None) -> None:
    from app.services.interview_sequencing_service import PriorRoundNotPassed, enforce_interview_sequencing_gate

    try:
        enforce_interview_sequencing_gate(db, candidate_id, level=level, job_id=job_id, before_panel=panel)
    except PriorRoundNotPassed as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _panel_level(db: Session, panel: InterviewPanel) -> str:
    from app.services.interview_verdict_service import ensure_verdict_row

    return ensure_verdict_row(db, panel).level


def _require_rehire_clearance(db: Session, panel: InterviewPanel) -> None:
    """A candidate with a no-hire on another round may only be interviewed on a panel the rehire
    guard cleared (AI-cleared justification or hiring-manager approval)."""
    from app.services.interview_rehire_guard_service import get_past_no_hire_panels

    if not [p for p in get_past_no_hire_panels(db, panel.candidate_id) if p.id != panel.id]:
        return
    cleared = db.query(InterviewRehireReview.id).filter(
        InterviewRehireReview.resulting_panel_id == panel.id,
        InterviewRehireReview.status.in_(CLEARED_REHIRE_STATUSES),
    ).first()
    if cleared is None:
        raise HTTPException(status_code=409, detail=(
            "This candidate has a past no-hire outcome and this round was not cleared by the rehire "
            "guard. Create the round with a written justification first."))


# --------------------------------------------------------------------------- panel

def create_panel(db: Session, user: Users, *, candidate_id: str, job_id: Optional[str], round_name: str,
                 level: Optional[str] = None, rehire_justification: Optional[str] = None) -> PanelCreated:
    """A new interview round for the candidate, with every gate. A rehire request that the AI
    does not clear is recorded (the request commits itself, for the hiring manager) and the
    panel is not created (409)."""
    from app.services.interview_rehire_guard_service import candidate_has_past_no_hire, submit_rehire_request
    from app.services.interview_verdict_service import LEVELS, ensure_verdict_row, infer_level

    candidate = ensure_candidate_visible(db, candidate_id, user)
    job = visible_job_or_404(db, user, job_id, f"Job with ID {job_id}") if job_id else None
    require_experience(candidate)
    require_employment_type(candidate)

    level = (level or infer_level(round_name)).upper()
    if level not in LEVELS:
        raise HTTPException(status_code=400, detail=f"level must be one of {', '.join(LEVELS)}")
    _require_sequencing(db, candidate_id, level, job_id)

    review = None
    if candidate_has_past_no_hire(db, candidate_id):
        if not rehire_justification or not rehire_justification.strip():
            raise HTTPException(status_code=400, detail=(
                "This candidate has a past no-hire outcome on record. A written "
                "justification is required to schedule a new interview round."))
        review = submit_rehire_request(db, candidate_id, candidate_display_name(candidate), round_name,
                                       job_id, user.UserID, rehire_justification)
        if review.status != "AI_CLEARED":
            raise HTTPException(status_code=409, detail={
                "error": "rehire_review_pending",
                "review_id": review.id,
                "msg": ("This candidate has a past no-hire outcome. The justification has been sent to "
                        "the hiring manager for approval before this round can be scheduled."),
                "ai_reasoning": review.ai_reasoning,
            })

    panel = InterviewPanel(candidate_id=candidate_id, round_name=round_name, job_id=job_id)
    db.add(panel)
    db.flush()
    verdict = ensure_verdict_row(db, panel, level)
    if review is not None:
        review.resulting_panel_id = panel.id  # the cleared round is this panel
    return PanelCreated(panel=panel, job=job, level=verdict.level, verdict=verdict.verdict,
                        rehire_review_id=review.id if review else None,
                        rehire_cleared_by="AI" if review else None)


def after_panel_created(panel: InterviewPanel) -> None:
    from app.services.hiring_pipeline_service import notify

    notify(panel.candidate_id, "panel_created", panel.id)


# --------------------------------------------------------------------------- interviewers

def panel_diversity_warning(db: Session, panel: InterviewPanel, interviewer_id: str) -> Optional[str]:
    """Advisory: the interviewer already sat a panel for this candidate on a DIFFERENT job
    (Avinash: a different job deserves a fresh perspective). Same job, other rounds is normal."""
    past = (db.query(InterviewPanel).join(PanelMember, PanelMember.panel_id == InterviewPanel.id)
            .filter(InterviewPanel.candidate_id == panel.candidate_id, InterviewPanel.id != panel.id,
                    PanelMember.interviewer_id == interviewer_id).all())
    if panel.job_id is not None:
        past = [p for p in past if p.job_id != panel.job_id]
    if not past:
        return None
    return (f"Interviewer {interviewer_id} already served on a panel for this candidate "
            f"on {len(past)} other job(s) -- consider a different interviewer for "
            f"a fresh perspective.")


def assign_member(db: Session, user: Users, *, panel_id: int, interviewer_id: str) -> Tuple[PanelMember, Optional[str]]:
    panel = visible_panel_or_404(db, user, panel_id)
    interviewer = db.query(Users).filter(Users.UserID == interviewer_id).first()
    if interviewer is None or interviewer.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail=f"Interviewer with ID {interviewer_id} not found")
    if db.query(PanelMember.id).filter(PanelMember.panel_id == panel_id,
                                       PanelMember.interviewer_id == interviewer_id).first():
        raise HTTPException(status_code=400,
                            detail=f"Interviewer {interviewer_id} is already assigned to panel {panel_id}")
    warning = panel_diversity_warning(db, panel, interviewer_id)
    member = PanelMember(panel_id=panel_id, interviewer_id=interviewer_id)
    db.add(member)
    db.flush()
    return member, warning


def after_member_assigned(db: Session, panel_id: int) -> None:
    """The new interviewer gets a feedback task on the round's scheduled interviews."""
    from app.services.interview_feedback_task_service import sync_pending_feedback_tasks_for_interview

    for interview in db.query(Interview).filter(Interview.panel_id == panel_id,
                                                Interview.status == "Scheduled").all():
        sync_pending_feedback_tasks_for_interview(db, interview)


# --------------------------------------------------------------------------- interview

def schedule_interview(db: Session, user: Users, *, panel_id: int, candidate_id: str, start: datetime,
                       end: datetime, meeting_link: Optional[str] = None, outlook_event_id: Optional[str] = None,
                       status: str = "Scheduled") -> Interview:
    panel = visible_panel_or_404(db, user, panel_id)
    candidate = ensure_candidate_visible(db, candidate_id, user)
    if panel.candidate_id != candidate.candidateID:
        raise HTTPException(status_code=400, detail="The interview's candidate must be the panel's candidate")
    require_experience(candidate)
    require_employment_type(candidate)
    _require_sequencing(db, candidate.candidateID, _panel_level(db, panel), panel.job_id, panel)
    _require_rehire_clearance(db, panel)

    start, end = to_naive_utc(start), to_naive_utc(end)
    if end <= start:
        raise HTTPException(status_code=400, detail="End time must be after start time")
    interview = Interview(panel_id=panel.id, candidate_id=candidate.candidateID, start_time=start, end_time=end,
                          meeting_link=meeting_link, outlook_event_id=outlook_event_id, status=status)
    db.add(interview)
    db.flush()
    return interview


def after_commit(db: Session, interview: Interview, panel: InterviewPanel) -> None:
    """Side effects of a committed new interview: Thunder's outreach pauses (interview_scheduled),
    the hiring pipeline re-evaluates, each interviewer gets a feedback task and the candidate
    gets an invitation (once per interview and time)."""
    from app.services.hiring_pipeline_service import notify
    from app.services.interview_feedback_task_service import sync_pending_feedback_tasks_for_interview
    from app.services.thunder_mail.cadence_service import enqueue_once

    candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
    enqueue_once(INTERVIEW_SCHEDULED_TASK, f"interview-scheduled:{interview.id}", {
        "interview_id": interview.id, "candidate_id": interview.candidate_id, "panel_id": panel.id,
        "start_time": interview.start_time.isoformat(), "end_time": interview.end_time.isoformat(),
        "meeting_link": interview.meeting_link,
    }, candidate.tenant_id if candidate else None)
    notify(interview.candidate_id, "interview_scheduled", interview.id)
    sync_pending_feedback_tasks_for_interview(db, interview)
    queue_invite(db, interview)


def invite_ref(interview: Interview) -> str:
    """One invitation per interview and start time: a rescheduled interview invites again."""
    return f"{interview.id}:{interview.start_time:%Y%m%dT%H%M}"


def invite_email_id(interview: Interview) -> str:
    from app.services.hiring_onboarding_service import pipeline_email_id

    return pipeline_email_id(INVITE_KIND, interview.candidate_id, invite_ref(interview))


def queue_invite(db: Session, interview: Interview) -> Optional[str]:
    """Queue the candidate's INTERVIEW_INVITE (built at send time from the interview row).
    Commits the pipeline_emails row before queueing it; returns the email id, None when the
    candidate may not be emailed or the invitation already exists."""
    from app.core.config import settings
    from app.services.candidate_contact_policy import can_receive_transactional
    from app.services.hiring_onboarding_service import PIPELINE_EMAIL_TASK, queue_candidate_email
    from app.services.thunder_mail.cadence_service import enqueue_once

    if interview.status != "Scheduled":
        return None
    candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
    allowed, reason = can_receive_transactional(db, candidate)
    if not allowed:
        logger.info(f"[InterviewInvite] interview {interview.id}: no invitation ({reason})")
        return None
    email_id = queue_candidate_email(db, candidate, INVITE_KIND, invite_ref(interview))
    if email_id is None:
        return None
    db.commit()
    enqueue_once(PIPELINE_EMAIL_TASK, email_id, {"email_id": email_id, "candidate_id": candidate.candidateID},
                 candidate.tenant_id, delay_seconds=settings.INTERVIEW_INVITE_DELAY_SECONDS)
    return email_id


def mark_invite_sent(db: Session, interview: Interview) -> None:
    """An invitation sent from the screen (Teams invite) stands for the automatic one."""
    from app.models.pipeline_email import PipelineEmail

    candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
    email_id = invite_email_id(interview)
    row = db.query(PipelineEmail).filter(PipelineEmail.id == email_id).first()
    if row is None:
        row = PipelineEmail(id=email_id, tenant_id=candidate.tenant_id if candidate else None,
                            candidate_id=interview.candidate_id, kind=INVITE_KIND, ref=invite_ref(interview))
        db.add(row)
    if row.sent_at is None:
        row.sent_at = datetime.utcnow()
