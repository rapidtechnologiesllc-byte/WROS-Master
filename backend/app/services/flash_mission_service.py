"""Flash missions (flash spec D, with the CEO's 2026-10-15 decisions): after a job is created in
the Flash chat, Flash works it until every position is filled and tells the requester what it did.

Deterministic code only -- no language model acts here. The flash_mission_sweep scheduled job
calls run_sweep every 5 minutes; each due mission advances in its own transaction.

advance(), in order:
 1. Acting user: the requester, active and in the mission's tenant. Someone who left hands the
    mission to the job's hiring manager, who is told in Flash; with nobody to take it the mission
    is BLOCKED(owner_inactive) and the recruiter gets a task.
 2. Tenant: the job must be in the mission's tenant; every query is tenant-filtered.
    A BLOCKED mission re-checks its block cause first (block_resolved) on every sweep; once the
    cause has gone it is ACTIVE again, its hand-off task is closed and the requester is told.
 3. Track progress (one track per candidate): a scheduled interview that ended awaits its verdict;
    Flash READS verdicts (interview_verdict_service, computed from people's feedback) and never
    writes one. PENDING -> chase the interviewer (and, after FLASH_FEEDBACK_CHASES_BEFORE_HM
    reminders, the hiring manager); NEEDS_DECISION -> AWAITING_HUMAN, surfaced to the hiring
    manager as a Flash decision; PASS on L1 with L2 required -> schedule L2; PASS on the last
    round -> OFFER_PENDING (people create the offer); FAIL -> the next candidate; a cancelled
    interview -> WITHDRAWN.
 4. Bench first (R-04), once: bench employees who match and could be submitted today
    (client_submission_blockers) become "Propose X to client" tasks for the recruiter -- Flash
    never submits to a client. Then external sourcing is enabled.
 5. Fill: while fewer than (open positions x FLASH_PARALLEL_CANDIDATES) candidates are in
    interviews, take the next ranked candidate (job_candidate_ranking_service: tenant, the
    requester's business units, the 5-year floor, the job's minimum, employment type by country),
    re-check pick_gate, and schedule the L1 -- as the requester, through
    interview_scheduling_service (their interviews.create/edit permission; otherwise
    BLOCKED(permission) and a hand-off task).
 6. Filled: a position is filled only when its candidate has JOINED (CEO 2026-10-15) -- see
    candidate_joined(). Offers pending or accepted never stop sourcing or interviewing. When
    joined == positions the mission closes; it also closes when the job is closed or deleted.
 7. Nobody fits: re-check every FLASH_MISSION_RECHECK_HOURS; after
    FLASH_MISSION_ESCALATE_AFTER_DAYS a task for the recruiter, then every
    FLASH_MISSION_REESCALATE_DAYS one for the hiring manager. Never closed for lack of a match.

Interviewer (CEO decision 4): the job's interview panel for that level, else the job's hiring
manager, else the client's BU head -- never the recruiter; none -> BLOCKED(no_interviewer) and a
task. Slot: interview_slot_service.next_free_slot; none -> BLOCKED(no_slot), retried.

Every state change writes a FlashMissionEvent and a message in the requester's Flash
conversation. Global Thunder pause: no new interview (no candidate email) is scheduled.
"""
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import Candidate
from app.models.flash_mission import (INTERVIEWING, SWEPT_STATES, FlashMission, FlashMissionCandidate,
                                      FlashMissionEvent)
from app.models.user import Interview, InterviewPanel, Jobs, Users
from app.services import flash_conversation_service as conversations

logger = logging.getLogger(__name__)

CLOSED_JOB_STATUSES = ("closed", "cancelled", "canceled", "filled", "deleted")
CLOSED_DEMAND_STATUSES = ("FILLED", "CANCELLED")
OPEN_TASK_EXCLUDED = ("COMPLETED", "CANCELLED")
LEVEL_LABELS = {"L1": "technical", "L2": "management"}
TASK_CATEGORY = "FLASH_MISSION"


class MissionError(ValueError):
    """A mission action the user may not take (shown to them)."""


# --------------------------------------------------------------------------- small helpers

def _person(user: Optional[Users]) -> str:
    return (user.UserName or user.UserEmail) if user else "someone"


def candidate_label(candidate: Optional[Candidate]) -> str:
    if candidate is None:
        return "the candidate"
    last = (candidate.candidateLastName or "").strip()
    return " ".join(p for p in [candidate.candidateFirstName, f"{last[0]}." if last else ""] if p) or candidate.candidateID


def _job_label(db: Session, job: Optional[Jobs]) -> str:
    if job is None:
        return "this job"
    client = job.companyName
    if not client and job.client_id:
        from app.models.client import Client

        row = db.query(Client).filter(Client.id == job.client_id).first()
        client = row.company_name if row else None
    return f"{job.jobTitle} ({client})" if client else job.jobTitle


def _local(start: datetime, tz_name: Optional[str]) -> str:
    local = start.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz_name or settings.INTERVIEW_DEFAULT_TIMEZONE))
    return f"{local:%a %d %b %H:%M} {local.tzname()}"


def _active_user(db: Session, user_id: Optional[str], tenant_id: int) -> Optional[Users]:
    if not user_id:
        return None
    user = db.query(Users).filter(Users.UserID == user_id).first()
    if user is None or user.tenant_id != tenant_id or user.terminated_at is not None:
        return None
    return user


def _event(db: Session, mission: FlashMission, kind: str, text: str, *, tell: bool = True, **detail) -> None:
    """Record what happened; with tell, say it in the requester's Flash conversation."""
    db.add(FlashMissionEvent(mission_id=mission.id, kind=kind, detail={"text": text, **detail}))
    if tell:
        conversations.post_event(db, mission.requested_by_user_id, mission.tenant_id, text,
                                 {"mission_id": mission.id, "kind": kind})
    db.flush()


def _tell(db: Session, mission: FlashMission, user_id: Optional[str], text: str, kind: str) -> None:
    if user_id:
        conversations.post_event(db, user_id, mission.tenant_id, text, {"mission_id": mission.id, "kind": kind})


def _task(db: Session, mission: FlashMission, assignee: Optional[str], title: str, description: str, link: str,
          candidate_id: Optional[str] = None):
    from app.services.task_service import create_task

    task = create_task(db, title=title[:300], description=description, priority="HIGH", tenant_id=mission.tenant_id,
                       category=TASK_CATEGORY, assigned_to_user_id=assignee, link=link,
                       created_by_user_id=mission.requested_by_user_id,
                       visibility_scope="ASSIGNEE_MANAGER_DEPARTMENT" if assignee else "ORG_WIDE")
    if candidate_id:
        task.candidate_id = candidate_id
    db.flush()
    return task


def _task_open(db: Session, task_id: Optional[int]) -> bool:
    from app.models.task import Task

    if task_id is None:
        return False
    task = db.query(Task).filter(Task.id == task_id).first()
    return task is not None and task.status not in OPEN_TASK_EXCLUDED


def _recruiter_id(db: Session, mission: FlashMission, job: Jobs) -> Optional[str]:
    for user_id in (job.recuriterID, job.hiringManagerID, mission.requested_by_user_id):
        if _active_user(db, user_id, mission.tenant_id):
            return user_id
    return None


def _job_closed(job: Jobs) -> bool:
    return bool(job.is_deleted or (job.jobStatus or "").lower() in CLOSED_JOB_STATUSES
                or (job.demand_status or "") in CLOSED_DEMAND_STATUSES)


def candidate_joined(db: Session, job_id: str, candidate_id: str, today: date) -> bool:
    """The strongest "actually started" fact in WROS (CEO 2026-10-15: filled = joined):
    - an Employee row for the candidate that has joined -- status past PRE_JOINING and not EXITED
      (employee_service moves PRE_JOINING employees to ACTIVE/ALLOCATED on their joining date)
      and joining_date on or before today; and
    - an accepted offer for this job (or, for an offer with no job, the candidate's job is this
      one), so a candidate who joined for another job never fills this one."""
    from app.models.employee import Employee
    from app.models.offer_letter import OfferLetter

    employee = (db.query(Employee.id)
                .filter(Employee.candidate_id == candidate_id, Employee.status.notin_(("PRE_JOINING", "EXITED")),
                        Employee.joining_date <= today).first())
    if employee is None:
        return False
    candidate_job = db.query(Candidate.job_id).filter(Candidate.candidateID == candidate_id).scalar()
    return db.query(OfferLetter.id).filter(
        OfferLetter.candidate_id == candidate_id, OfferLetter.offer_status == "Accepted",
        or_(OfferLetter.job_id == job_id, OfferLetter.job_id.is_(None) if candidate_job == job_id else False),
    ).first() is not None


def _offer_lost(db: Session, job_id: str, candidate_id: str) -> Optional[str]:
    """Why an OFFER_PENDING candidate can no longer fill the position (declined offer, closed
    pipeline), else None."""
    from app.models.hiring_pipeline import HiringPipeline
    from app.models.offer_letter import OfferLetter

    offer = (db.query(OfferLetter).filter(OfferLetter.candidate_id == candidate_id,
                                          OfferLetter.offer_status != "Cancelled",
                                          or_(OfferLetter.job_id == job_id, OfferLetter.job_id.is_(None)))
             .order_by(OfferLetter.id.desc()).first())
    if offer is not None and offer.offer_status == "Rejected":
        return "declined the offer"
    pipeline = (db.query(HiringPipeline).filter(HiringPipeline.candidate_id == candidate_id)
                .order_by(HiringPipeline.id.desc()).first())
    if pipeline is not None and pipeline.stage == "REJECTED":
        return "; ".join(pipeline.blockers or []) or "left the hiring pipeline"
    return None


# --------------------------------------------------------------------------- start

def start_mission(db: Session, user: Users, job_id: str, positions: int,
                  conversation_id: Optional[str] = None) -> FlashMission:
    """The mission for a job Flash just queued, created once (idempotent on job_id)."""
    existing = db.query(FlashMission).filter(FlashMission.job_id == job_id).first()
    if existing is not None:
        if existing.tenant_id != user.tenant_id:
            raise MissionError("That job belongs to another company.")
        return existing
    if positions < 1:
        raise MissionError("A search needs at least one position.")
    now = datetime.utcnow()
    try:
        with db.begin_nested():
            mission = FlashMission(tenant_id=user.tenant_id, job_id=job_id, requested_by_user_id=user.UserID,
                                   conversation_id=conversation_id, state="AWAITING_JOB", positions=positions,
                                   next_check_at=now)
            db.add(mission)
            db.flush()
    except IntegrityError:
        existing = db.query(FlashMission).filter(FlashMission.job_id == job_id).first()
        if existing is None:
            raise
        return existing
    db.add(FlashMissionEvent(mission_id=mission.id, kind="started", detail={"text": "Search started"}))
    db.flush()
    logger.info(f"[FlashMission] {mission.id} started for job {job_id} by {user.UserID}")
    return mission


# --------------------------------------------------------------------------- state changes

def _set_next(mission: FlashMission, now: datetime, delta: timedelta) -> None:
    mission.next_check_at = now + delta


def _close(db: Session, mission: FlashMission, now: datetime, text: str) -> None:
    mission.state, mission.closed_at, mission.block_reason = "CLOSED", now, None
    mission.state_reason = text
    _set_next(mission, now, timedelta(days=36500))
    _event(db, mission, "closed", text)


def _fail(db: Session, mission: FlashMission, now: datetime, text: str, job: Optional[Jobs] = None) -> None:
    mission.state, mission.closed_at, mission.state_reason = "FAILED", now, text
    _set_next(mission, now, timedelta(days=36500))
    _event(db, mission, "failed", text)
    if job is not None:
        _task(db, mission, _recruiter_id(db, mission, job), f"Flash stopped its search for {job.jobTitle}",
              f"{text} Check the job and take the search over.", f"/jobs/{job.jobID}")


def _block(db: Session, mission: FlashMission, now: datetime, reason: str, text: str, *,
           task: Optional[Dict] = None, task_after: Optional[timedelta] = None) -> None:
    """BLOCKED for `reason`; said once. The task (title/description/link/assignee) is created once,
    right away or after `task_after` blocked."""
    if mission.state != "BLOCKED" or mission.block_reason != reason:
        _close_block_task(db, mission)  # a different cause: the previous hand-off no longer applies
        mission.state, mission.block_reason, mission.blocked_since, mission.block_task_id = "BLOCKED", reason, now, None
        mission.state_reason = text
        _event(db, mission, f"blocked_{reason}", text)
    if task and mission.block_task_id is None and (task_after is None or now - mission.blocked_since >= task_after):
        mission.block_task_id = _task(db, mission, task["assignee"], task["title"], task["description"],
                                      task["link"], task.get("candidate_id")).id
    retry = timedelta(hours=settings.FLASH_NO_SLOT_RETRY_HOURS) if reason == "no_slot" else \
        timedelta(minutes=settings.FLASH_MISSION_TRACK_CHECK_MINUTES)
    _set_next(mission, now, retry)


def _close_block_task(db: Session, mission: FlashMission) -> None:
    """The block's hand-off task is done once its cause has gone (or the cause changed)."""
    from app.models.task import Task

    if mission.block_task_id is None:
        return
    task = db.query(Task).filter(Task.id == mission.block_task_id).first()
    if task is not None and task.status not in OPEN_TASK_EXCLUDED:
        task.status, task.completed_at = "COMPLETED", datetime.utcnow()
    mission.block_task_id = None


UNBLOCKED_WORDS = {"owner_inactive": "{owner} now runs the search",
                   "permission": "you can schedule interviews now",
                   "no_interviewer": "an interviewer is now available",
                   "no_slot": "the interview slot problem has cleared"}


def _unblock(db: Session, mission: FlashMission, job: Jobs) -> None:
    """Back to ACTIVE: the hand-off task is closed and the requester is told the search goes on."""
    if mission.state != "BLOCKED":
        return
    reason = mission.block_reason
    _close_block_task(db, mission)
    mission.state, mission.block_reason, mission.blocked_since, mission.state_reason = "ACTIVE", None, None, None
    owner = db.query(Users).filter(Users.UserID == mission.requested_by_user_id).first()
    why = UNBLOCKED_WORDS.get(reason, "the block has cleared").format(owner=_person(owner))
    _event(db, mission, "unblocked", f"{_job_label(db, job)}: {why}, so the search continues.",
           previous_reason=reason)


def _track_status(db: Session, mission: FlashMission, track: FlashMissionCandidate, status: str, text: str, *,
                  tell: bool = True, reason: Optional[str] = None) -> None:
    track.status = status
    if reason is not None:
        track.reason = reason
    _event(db, mission, f"track_{status.lower()}", text, tell=tell, candidate_id=track.candidate_id)


# --------------------------------------------------------------------------- acting user

def _acting_user(db: Session, mission: FlashMission, job: Jobs, now: datetime) -> Optional[Users]:
    user = _active_user(db, mission.requested_by_user_id, mission.tenant_id)
    if user is not None:
        return user
    manager = _active_user(db, job.hiringManagerID, mission.tenant_id)
    if manager is not None and manager.UserID != mission.requested_by_user_id:
        previous = db.query(Users).filter(Users.UserID == mission.requested_by_user_id).first()
        mission.requested_by_user_id, mission.conversation_id = manager.UserID, None
        label = _job_label(db, job)
        _event(db, mission, "transferred",
               f"{_person(previous)} has left, so Flash's search for {label} is now yours (you are the hiring "
               f"manager). {mission_summary(db, mission)} Say \"pause my {job.jobTitle} search\" or \"cancel my "
               f"{job.jobTitle} search\" to change it.", previous_owner=previous.UserID if previous else None)
        return manager
    _block(db, mission, now, "owner_inactive",
           f"The person who started Flash's search for {_job_label(db, job)} has left and the job has no active "
           "hiring manager to take it over.",
           task={"assignee": job.recuriterID, "title": f"Take over Flash's search for {job.jobTitle}",
                 "description": "The requester left and the job has no hiring manager. Set a hiring manager on the "
                                "job; Flash hands the search to them.", "link": f"/jobs/{job.jobID}"})
    return None


# --------------------------------------------------------------------------- gates and people

def pick_gate(db: Session, mission: FlashMission, candidate: Candidate, user: Users, job: Jobs) -> Optional[str]:
    """Why Flash may not interview this candidate for this job now (None: it may). Run when the
    candidate is picked and again just before scheduling."""
    from app.core.bu_scope import ensure_candidate_visible
    from app.services.candidate_contact_policy import is_contactable
    from app.services.employment_type_policy import interview_check
    from app.services.interview_rehire_guard_service import candidate_has_past_no_hire
    from app.services.submission_service import ExperienceIneligible, assert_experience_eligible

    if candidate.tenant_id != mission.tenant_id:
        return "another company's candidate"
    try:
        assert_experience_eligible(candidate, "schedule an interview")
    except ExperienceIneligible as exc:
        return str(exc)
    contactable, why = is_contactable(db, candidate)
    if not contactable:
        return f"cannot be contacted ({why})"
    if candidate_has_past_no_hire(db, candidate.candidateID):
        return "has a past no-hire; a person must justify a new round"
    if db.query(InterviewPanel.id).filter(InterviewPanel.candidate_id == candidate.candidateID,
                                          InterviewPanel.job_id == job.jobID).first():
        return "already has an interview round for this job"
    employment = interview_check(candidate)
    if not employment["allowed"]:
        return employment["message"]
    try:
        ensure_candidate_visible(db, candidate.candidateID, user)
    except HTTPException:
        return "outside the requester's business units"
    return None


def resolve_interviewer(db: Session, job: Jobs, level: str, tenant_id: int) -> Optional[Users]:
    """CEO decision 4: the job's interview panel for the level, else the job's hiring manager,
    else the client's BU head. Never the recruiter. Active users of the tenant only."""
    from app.models.employee import Employee
    from app.services.bu_leadership import head_for_client
    from app.services.interview_service import get_assigned_interviewer

    options: List[Optional[str]] = []
    panel = get_assigned_interviewer(db, demand_id=job.jobID, interview_level=level, tenant_id=tenant_id)
    if panel is not None:
        options.append(db.query(Employee.wros_user_id).filter(Employee.id == panel.employee_id).scalar())
    options.append(job.hiringManagerID)
    options.append(head_for_client(db, job.business_unit_id, job.client_id))
    for user_id in options:
        if user_id and user_id != job.recuriterID:
            user = _active_user(db, user_id, tenant_id)
            if user is not None:
                return user
    return None


def _may_schedule(db: Session, user: Users) -> bool:
    from app.core import authority

    return authority.has_permission(db, user, "interviews.create") and authority.has_permission(db, user,
                                                                                                "interviews.edit")


# --------------------------------------------------------------------------- scheduling

def _schedule(db: Session, mission: FlashMission, job: Jobs, user: Users, track: FlashMissionCandidate, level: str,
              now: datetime, *, graph_call: Optional[Callable] = None,
              graph_event_call: Optional[Callable] = None) -> bool:
    """Create the round, its interviewer and the interview as the requester; True when scheduled.
    A missing permission, interviewer or slot blocks the mission (said once, with a task)."""
    from app.services import interview_scheduling_service as scheduling
    from app.services.interview_slot_service import next_free_slot

    candidate = db.query(Candidate).filter(Candidate.candidateID == track.candidate_id).first()
    name, label = candidate_label(candidate), _job_label(db, job)
    if not _may_schedule(db, user):
        _block(db, mission, now, "permission",
               f"I can't schedule interviews for {label}: you don't have permission to create interviews. I've "
               f"asked the recruiter to schedule {name}'s {level}.",
               task={"assignee": _recruiter_id(db, mission, job), "title": f"Schedule {level} for {name}",
                     "description": f"Flash found {name} for {label} but the requester may not schedule "
                                    f"interviews. Schedule the {level} ({LEVEL_LABELS.get(level, level)}) round.",
                     "link": f"/candidates/{track.candidate_id}?tab=interview", "candidate_id": track.candidate_id})
        return False
    if track.status == "PROPOSED":
        reason = pick_gate(db, mission, candidate, user, job)
        if reason:
            _track_status(db, mission, track, "SKIPPED", f"Skipped {name} for {label}: {reason}.", tell=False,
                          reason=reason)
            return False
    interviewer = resolve_interviewer(db, job, level, mission.tenant_id)
    if interviewer is None:
        _block(db, mission, now, "no_interviewer",
               f"{label}: nobody can interview for the {level} round -- no interview panel for that level, no "
               "hiring manager and no BU head. I've asked the recruiter to assign one.",
               task={"assignee": _recruiter_id(db, mission, job),
                     "title": f"Assign an {level} interviewer for {job.jobTitle}",
                     "description": f"Flash is ready to schedule {level} interviews for {label} but the job has no "
                                    f"{level} interview panel, hiring manager or BU head.",
                     "link": f"/jobs/{job.jobID}"})
        return False
    slot = next_free_slot(db, interviewer, candidate, now=now, graph_call=graph_call)
    if slot is None:
        _block(db, mission, now, "no_slot",
               f"{label}: {_person(interviewer)} has no free slot in business hours for the next "
               f"{settings.INTERVIEW_HORIZON_DAYS} days. I'll keep looking.",
               task={"assignee": _recruiter_id(db, mission, job), "title": f"No interview slot for {job.jobTitle}",
                     "description": f"Flash has found no common free time for {_person(interviewer)} and {name}.",
                     "link": f"/candidates/{track.candidate_id}?tab=interview", "candidate_id": track.candidate_id},
               task_after=timedelta(hours=settings.FLASH_NO_SLOT_ESCALATE_HOURS))
        return False

    start, end = slot
    try:
        with db.begin_nested():
            created = scheduling.create_panel(db, user, candidate_id=track.candidate_id, job_id=job.jobID,
                                              round_name=f"{level} {LEVEL_LABELS.get(level, '').title()}".strip(),
                                              level=level)
            scheduling.assign_member(db, user, panel_id=created.panel.id, interviewer_id=interviewer.UserID)
            interview = scheduling.schedule_interview(db, user, panel_id=created.panel.id,
                                                      candidate_id=track.candidate_id, start=start, end=end)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        _track_status(db, mission, track, "SKIPPED", f"Could not schedule {name}'s {level} for {label}: {detail}",
                      tell=level != "L1", reason=detail)
        return False

    panel = created.panel
    track.panel_id, track.interview_id, track.interviewer_user_id, track.level = (panel.id, interview.id,
                                                                                  interviewer.UserID, level)
    track.feedback_chases, track.last_chased_at = 0, None
    if candidate is not None and not candidate.job_id:
        candidate.job_id = job.jobID
    _create_calendar_event(db, interview, interviewer, candidate, label, level, graph_event_call)
    _unblock(db, mission, job)
    mission.last_progress_at = now
    requester = db.query(Users).filter(Users.UserID == mission.requested_by_user_id).first()
    _track_status(db, mission, track, "SCHEDULED",
                  f"{label}: scheduled {level} for {name} with {_person(interviewer)} on "
                  f"{_local(start, requester.timezone if requester else None)}.")
    link_note = "" if interview.meeting_link else (" There is no meeting link yet: add it to the interview -- the "
                                                    "candidate was told it follows.")
    _tell(db, mission, interviewer.UserID,
          f"You're interviewing {name} for {label} ({level} {LEVEL_LABELS.get(level, '')}) on "
          f"{_local(start, interviewer.timezone)}. Your feedback task is in My Tasks.{link_note}", "interviewer")
    db.commit()
    scheduling.after_panel_created(panel)
    scheduling.after_commit(db, interview, panel)
    _complete_scheduling_tasks(db, track.candidate_id, level)
    db.flush()
    return True


def _create_calendar_event(db: Session, interview: Interview, interviewer: Users, candidate: Optional[Candidate],
                           label: str, level: str, call: Optional[Callable]) -> None:
    """Put the interview in the interviewer's Outlook calendar when Graph is on (or a call is
    injected). A failure is logged: the interview stands, the interviewer's task still asks for
    the link."""
    from app.services.interview_slot_service import graph_enabled

    if call is None:
        if not graph_enabled():
            return
        from app.services.interview_confirmation_service import _default_graph_create_event_call as call
    tz_name = interviewer.timezone or settings.INTERVIEW_DEFAULT_TIMEZONE
    start = interview.start_time.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz_name))
    end = interview.end_time.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz_name))
    try:
        interview.outlook_event_id = call(interviewer.UserEmail, f"{level} interview: {candidate_label(candidate)} -- {label}",
                                          start.replace(tzinfo=None).isoformat(), end.replace(tzinfo=None).isoformat(),
                                          tz_name, f"{level} interview for {label}, scheduled by Flash.",
                                          [interviewer.UserEmail])
    except Exception as exc:
        logger.error(f"[FlashMission] Outlook event for interview {interview.id} failed: {exc}", exc_info=True)


def _complete_scheduling_tasks(db: Session, candidate_id: str, level: str) -> None:
    """The hiring pipeline's "Schedule L1 interview" task for this candidate is done."""
    from app.models.task import Task

    for task in db.query(Task).filter(Task.candidate_id == candidate_id, Task.category == "INTERVIEW_SCHEDULING",
                                      Task.status.notin_(OPEN_TASK_EXCLUDED),
                                      Task.title.like(f"Schedule {level} %")).all():
        task.status, task.completed_at = "COMPLETED", datetime.utcnow()


# --------------------------------------------------------------------------- tracks

def _chase(db: Session, mission: FlashMission, job: Jobs, track: FlashMissionCandidate, interview: Interview,
           now: datetime) -> None:
    from app.services.interview_feedback_task_service import sync_pending_feedback_tasks_for_interview

    since = track.last_chased_at or interview.end_time
    if since is None or now - since < timedelta(hours=settings.FLASH_FEEDBACK_CHASE_HOURS):
        return
    candidate = db.query(Candidate).filter(Candidate.candidateID == track.candidate_id).first()
    name, label = candidate_label(candidate), _job_label(db, job)
    sync_pending_feedback_tasks_for_interview(db, interview)
    _tell(db, mission, track.interviewer_user_id,
          f"Your feedback on {name} ({track.level}, {label}) is still missing -- it's in My Tasks. The search waits "
          "on it.", "feedback_chase")
    track.feedback_chases, track.last_chased_at = (track.feedback_chases or 0) + 1, now
    _event(db, mission, "feedback_chased", f"Reminded the interviewer about {name}'s {track.level} feedback.",
           tell=False, candidate_id=track.candidate_id)
    if track.feedback_chases == settings.FLASH_FEEDBACK_CHASES_BEFORE_HM and job.hiringManagerID:
        _tell(db, mission, job.hiringManagerID,
              f"{name}'s {track.level} feedback for {label} is still missing after "
              f"{track.feedback_chases} reminders to the interviewer.", "feedback_chase_hm")


def _reconcile(db: Session, mission: FlashMission, job: Jobs, user: Users, track: FlashMissionCandidate,
               now: datetime, **calls) -> None:
    from app.services.interview_verdict_service import verdict_for_panel

    candidate = db.query(Candidate).filter(Candidate.candidateID == track.candidate_id).first()
    name, label = candidate_label(candidate), _job_label(db, job)
    if track.status == "SCHEDULED":
        interview = db.query(Interview).filter(Interview.id == track.interview_id).first()
        if interview is None or interview.status == "Cancelled":
            _track_status(db, mission, track, "WITHDRAWN",
                          f"{label}: {name}'s {track.level} interview was cancelled; I'm moving on to the next "
                          "candidate.")
            return
        if interview.status == "Completed" or (interview.end_time and interview.end_time <= now):
            track.status = "AWAITING_VERDICT"
    if track.status in ("AWAITING_VERDICT", "AWAITING_HUMAN"):
        panel = db.query(InterviewPanel).filter(InterviewPanel.id == track.panel_id).first()
        verdict = verdict_for_panel(db, panel).verdict if panel is not None else "FAIL"
        if verdict == "PENDING":
            interview = db.query(Interview).filter(Interview.id == track.interview_id).first()
            if interview is not None:
                _chase(db, mission, job, track, interview, now)
        elif verdict == "NEEDS_DECISION":
            if track.status != "AWAITING_HUMAN":
                _track_status(db, mission, track, "AWAITING_HUMAN",
                              f"{label}: the {track.level} feedback on {name} is mixed; the hiring manager decides. "
                              "I'll carry on when they do.")
                _tell(db, mission, job.hiringManagerID,
                      f"Mixed {track.level} feedback on {name} for {label}: your decision is waiting in Flash.",
                      "decision_needed")
        elif verdict == "FAIL":
            _track_status(db, mission, track, "FAILED", f"{label}: {name} did not pass {track.level}; moving on.",
                          reason=f"{track.level} not passed")
        elif verdict == "PASS":
            if track.level == "L1" and (job.interview_type_required or "L1_AND_L2") == "L1_AND_L2":
                _track_status(db, mission, track, "ROUND_PASSED", f"{label}: {name} passed L1; scheduling L2.")
            else:
                _track_status(db, mission, track, "OFFER_PENDING",
                              f"{label}: {name} passed the final round. The offer is with the people who make "
                              "offers; I keep interviewing until someone joins.")
                _tell(db, mission, job.hiringManagerID,
                      f"{name} passed the final round for {label}. The hiring pipeline has an offer task for the "
                      "recruiter.", "final_pass")
    if track.status == "ROUND_PASSED" and _may_email(db):
        _schedule(db, mission, job, user, track, "L2", now, **calls)
    if track.status == "OFFER_PENDING":
        if candidate_joined(db, job.jobID, track.candidate_id, now.date()):
            _track_status(db, mission, track, "FILLED", f"{label}: {name} has joined.")
            mission.last_progress_at = now
        else:
            lost = _offer_lost(db, job.jobID, track.candidate_id)
            if lost:
                _track_status(db, mission, track, "FAILED", f"{label}: {name} {lost}; the search goes on.",
                              reason=lost)


def _may_email(db: Session) -> bool:
    from app.services.thunder_pause_service import is_thunder_paused

    return not is_thunder_paused(db)


# --------------------------------------------------------------------------- bench and sourcing

def _bench_first(db: Session, mission: FlashMission, job: Jobs, user: Users) -> None:
    """R-04 once per job: deployable bench matches become proposal tasks for the recruiter (or the
    client's BU head); Flash never submits to a client. Then external sourcing opens."""
    from app.core.data_scope import bu_filter
    from app.models.employee import Employee
    from app.models.resource_management import BenchPoolEntry
    from app.services.bu_leadership import head_for_client
    from app.services.demand_service import enable_sourcing
    from app.services.skill_matching_service import SkillMatchingService
    from app.services.submission_service import client_submission_blockers

    label = _job_label(db, job)
    job_skills = SkillMatchingService.job_skills(job)
    assignee = (job.recuriterID if _active_user(db, job.recuriterID, mission.tenant_id) else None) or \
        head_for_client(db, job.business_unit_id, job.client_id) or job.hiringManagerID
    proposed = []
    rows = (db.query(Employee).join(BenchPoolEntry, BenchPoolEntry.employee_id == Employee.id)
            .filter(Employee.tenant_id == mission.tenant_id, Employee.candidate_id.isnot(None),
                    bu_filter(db, user, Employee.bu_id)).all()) if job_skills else []
    for employee in rows:
        candidate = db.query(Candidate).filter(Candidate.candidateID == employee.candidate_id).first()
        if candidate is None:
            continue
        match = SkillMatchingService.score_skills(job_skills, SkillMatchingService.candidate_skills(db, candidate),
                                                  mode=job.job_skills_boolean_mode or "AND")
        if not match["can_proceed"] or client_submission_blockers(db, candidate, job):
            continue
        name = f"{employee.first_name} {employee.last_name}".strip()
        _task(db, mission, assignee, f"Propose {name} to {label}",
              f"{name} is on the bench, matches {', '.join(match['matched'])} and can be submitted today. Flash "
              "does not submit to clients: propose them if they fit.",
              f"/candidates/{candidate.candidateID}", candidate.candidateID)
        proposed.append(name)
    job.bench_first_checked = True
    enable_sourcing(db, job)
    if proposed:
        _event(db, mission, "bench_first", f"{label}: {len(proposed)} bench employee(s) fit ({', '.join(proposed)}). "
               "I've asked the recruiter to propose them to the client, and I'm sourcing candidates too.")
    else:
        _event(db, mission, "bench_first", f"{label}: nobody on the bench fits, so I'm sourcing candidates.")


def _fill(db: Session, mission: FlashMission, job: Jobs, user: Users, now: datetime, filled: int, **calls) -> int:
    """Start interviews until the parallel cap; returns how many were scheduled."""
    from app.services.job_candidate_ranking_service import rank_candidates_for_job

    if not _may_email(db):
        return 0
    tracks = db.query(FlashMissionCandidate).filter(FlashMissionCandidate.mission_id == mission.id).all()
    interviewing = sum(1 for t in tracks if t.status in INTERVIEWING and t.status != "PROPOSED")
    cap = max(mission.positions - filled, 0) * settings.FLASH_PARALLEL_CANDIDATES
    scheduled = 0
    for track in [t for t in tracks if t.status == "PROPOSED"]:  # picked earlier, scheduling was blocked
        if interviewing >= cap:
            return scheduled
        if _schedule(db, mission, job, user, track, "L1", now, **calls):
            interviewing, scheduled = interviewing + 1, scheduled + 1
        elif mission.state == "BLOCKED":
            return scheduled
    tracked = {t.candidate_id for t in tracks}
    while interviewing < cap:
        ranked = rank_candidates_for_job(db, job, viewer=user, exclude_ids=tracked, limit=cap - interviewing)
        if not ranked:
            break
        for result in ranked:
            tracked.add(result.candidate_id)
            candidate = db.query(Candidate).filter(Candidate.candidateID == result.candidate_id).first()
            reason = pick_gate(db, mission, candidate, user, job)
            track = FlashMissionCandidate(mission_id=mission.id, candidate_id=result.candidate_id, score=result.score,
                                          status="SKIPPED" if reason else "PROPOSED", reason=reason)
            db.add(track)
            db.flush()
            if reason:
                _event(db, mission, "track_skipped", f"Skipped {candidate_label(candidate)}: {reason}.", tell=False,
                       candidate_id=result.candidate_id)
                continue
            if _schedule(db, mission, job, user, track, "L1", now, **calls):
                interviewing, scheduled = interviewing + 1, scheduled + 1
            elif mission.state == "BLOCKED":
                return scheduled
            if interviewing >= cap:
                break
    return scheduled


def _escalate_no_match(db: Session, mission: FlashMission, job: Jobs, now: datetime) -> None:
    """Never closes the search (CEO 2026-10-15): the recruiter after N days, then the hiring
    manager every M days, each only while the previous escalation task is not open."""
    if now - mission.created_at < timedelta(days=settings.FLASH_MISSION_ESCALATE_AFTER_DAYS):
        return
    if _task_open(db, mission.escalation_task_id):
        return
    label = _job_label(db, job)
    if mission.escalation_count == 0:
        assignee = _recruiter_id(db, mission, job)
    elif mission.last_escalated_at and now - mission.last_escalated_at >= timedelta(
            days=settings.FLASH_MISSION_REESCALATE_DAYS):
        assignee = _active_user(db, job.hiringManagerID, mission.tenant_id) and job.hiringManagerID
        assignee = assignee or _recruiter_id(db, mission, job)
    else:
        return
    task = _task(db, mission, assignee, f"No eligible match yet for {label}",
                 f"Flash has found no candidate who meets {label}'s requirements (skills, the 5-year rule, the "
                 "job's minimum experience). Widen the requirements, source directly, or cancel the search in Flash.",
                 f"/jobs/{job.jobID}")
    mission.escalation_task_id, mission.escalation_count, mission.last_escalated_at = (
        task.id, (mission.escalation_count or 0) + 1, now)
    _event(db, mission, "escalated", f"{label}: still no eligible candidate after "
           f"{(now - mission.created_at).days} days; I've asked {_person(db.query(Users).filter(Users.UserID == assignee).first())} "
           "to help. The search stays open.")


# --------------------------------------------------------------------------- blocks

def _pending_rounds(db: Session, mission: FlashMission) -> List[tuple]:
    """(track, level) waiting to be scheduled, in the order a sweep tries them: L2 rounds
    (_reconcile) before L1 picks (_fill)."""
    tracks = (db.query(FlashMissionCandidate)
              .filter(FlashMissionCandidate.mission_id == mission.id,
                      FlashMissionCandidate.status.in_(("ROUND_PASSED", "PROPOSED")))
              .order_by(FlashMissionCandidate.id).all())
    return ([(t, "L2") for t in tracks if t.status == "ROUND_PASSED"]
            + [(t, "L1") for t in tracks if t.status == "PROPOSED"])


def block_resolved(db: Session, mission: FlashMission, job: Jobs, user: Users, now: datetime, *,
                   graph_call: Optional[Callable] = None) -> bool:
    """Whether the cause of the mission's block has gone, checked fresh every sweep -- not only
    when something new needs scheduling.
    - owner_inactive: an active acting user was found (the caller only gets here with one).
    - permission: the acting user may create and edit interviews.
    - no_interviewer: every level waiting to be scheduled (L1 when nothing waits) has one.
    - no_slot: the round the sweep tries first has a free slot, or nothing waits for one."""
    from app.services.interview_slot_service import next_free_slot

    reason = mission.block_reason
    if reason == "owner_inactive":
        return user is not None
    if reason == "permission":
        return _may_schedule(db, user)
    pending = _pending_rounds(db, mission)
    if reason == "no_interviewer":
        levels = {level for _, level in pending} or {"L1"}
        return all(resolve_interviewer(db, job, level, mission.tenant_id) is not None for level in levels)
    if reason == "no_slot":
        if not pending:
            return True
        track, level = pending[0]
        candidate = db.query(Candidate).filter(Candidate.candidateID == track.candidate_id).first()
        interviewer = resolve_interviewer(db, job, level, mission.tenant_id)
        if candidate is None or interviewer is None:
            return False  # not a slot problem any more; scheduling re-blocks with the real cause
        return next_free_slot(db, interviewer, candidate, now=now, graph_call=graph_call) is not None
    raise ValueError(f"Flash mission {mission.id} is blocked for an unknown reason {reason!r}")


# --------------------------------------------------------------------------- advance / sweep

def advance(db: Session, mission: FlashMission, now: datetime, *, graph_call: Optional[Callable] = None,
            graph_event_call: Optional[Callable] = None) -> None:
    calls = {"graph_call": graph_call, "graph_event_call": graph_event_call}
    job = db.query(Jobs).filter(Jobs.jobID == mission.job_id).first()
    if mission.state == "AWAITING_JOB":
        if job is None:
            if now - mission.created_at > timedelta(hours=settings.FLASH_MISSION_JOB_WAIT_HOURS):
                _fail(db, mission, now, f"Job {mission.job_id} was never created, so Flash could not start its search.")
            else:
                _set_next(mission, now, timedelta(minutes=settings.FLASH_MISSION_TRACK_CHECK_MINUTES))
            return
    if job is None or job.tenant_id != mission.tenant_id:
        _fail(db, mission, now, f"Job {mission.job_id} is missing or belongs to another company.")
        return
    if _job_closed(job):
        _close(db, mission, now, f"{_job_label(db, job)} is closed, so Flash's search ended.")
        return
    if mission.state == "AWAITING_JOB":
        mission.state = "ACTIVE"
        _event(db, mission, "active", f"{_job_label(db, job)} is live. I'm checking the bench first, then sourcing "
               "candidates.")

    user = _acting_user(db, mission, job, now)
    if user is None:
        return
    if mission.state == "BLOCKED" and block_resolved(db, mission, job, user, now, graph_call=graph_call):
        _unblock(db, mission, job)
    tracks = (db.query(FlashMissionCandidate).filter(FlashMissionCandidate.mission_id == mission.id)
              .order_by(FlashMissionCandidate.id).all())
    for track in tracks:
        _reconcile(db, mission, job, user, track, now, **calls)
    filled = sum(1 for t in tracks if t.status == "FILLED")
    if filled >= mission.positions:
        names = [candidate_label(db.query(Candidate).filter(Candidate.candidateID == t.candidate_id).first())
                 for t in tracks if t.status == "FILLED"]
        _close(db, mission, now, f"{_job_label(db, job)}: all {mission.positions} position(s) filled -- "
               f"{', '.join(names)} joined. Search closed.")
        return
    if not job.bench_first_checked:
        _bench_first(db, mission, job, user)
    # A mission still BLOCKED (the cause is still there) tries again: scheduling unblocks it, or
    # blocks it again without repeating the message
    scheduled = _fill(db, mission, job, user, now, filled, **calls)
    if mission.state == "BLOCKED":
        return
    live = db.query(FlashMissionCandidate).filter(
        FlashMissionCandidate.mission_id == mission.id,
        FlashMissionCandidate.status.in_(INTERVIEWING + ("OFFER_PENDING", "FILLED"))).count()
    if scheduled == 0 and live == 0:
        _escalate_no_match(db, mission, job, now)
        _set_next(mission, now, timedelta(hours=settings.FLASH_MISSION_RECHECK_HOURS))
    else:
        _set_next(mission, now, timedelta(minutes=settings.FLASH_MISSION_TRACK_CHECK_MINUTES))


def backlog_guard(db: Session, now: datetime) -> None:
    """Before the sweep's first run: missions whose job never appeared within the wait fail
    instead of acting on a stale backlog."""
    cutoff = now - timedelta(hours=settings.FLASH_MISSION_JOB_WAIT_HOURS)
    for mission in db.query(FlashMission).filter(FlashMission.state == "AWAITING_JOB",
                                                 FlashMission.created_at < cutoff).all():
        _fail(db, mission, now, f"Job {mission.job_id} was never created, so Flash could not start its search.")


def run_sweep(db: Session, now: Optional[datetime] = None, *, brains=None, graph_call: Optional[Callable] = None,
              graph_event_call: Optional[Callable] = None) -> Dict:
    """Advance every due mission (at most FLASH_MISSION_BATCH), each in its own transaction. A
    mission that keeps failing (FLASH_MISSION_MAX_ERRORS in a row) stops with a task."""
    if not settings.FLASH_MISSIONS_ENABLED:
        return {"status": "disabled"}
    now = now or datetime.utcnow()
    due = [mid for (mid,) in db.query(FlashMission.id)
           .filter(FlashMission.state.in_(SWEPT_STATES), FlashMission.next_check_at <= now)
           .order_by(FlashMission.next_check_at).limit(settings.FLASH_MISSION_BATCH).all()]
    outcome = {"status": "ok", "advanced": 0, "errors": 0, "skipped": 0}
    for mission_id in due:
        mission = (db.query(FlashMission)
                   .filter(FlashMission.id == mission_id, FlashMission.state.in_(SWEPT_STATES),
                           FlashMission.next_check_at <= now)
                   .with_for_update(skip_locked=True).first())
        if mission is None:
            outcome["skipped"] += 1
            continue
        try:
            advance(db, mission, now, graph_call=graph_call, graph_event_call=graph_event_call)
            mission.consecutive_errors = 0
            db.commit()
            outcome["advanced"] += 1
        except Exception as exc:
            db.rollback()
            logger.error(f"[FlashMission] {mission_id} failed to advance: {exc}", exc_info=True)
            mission = db.query(FlashMission).filter(FlashMission.id == mission_id).first()
            mission.consecutive_errors = (mission.consecutive_errors or 0) + 1
            db.add(FlashMissionEvent(mission_id=mission.id, kind="error", detail={"text": str(exc)[:500]}))
            if mission.consecutive_errors >= settings.FLASH_MISSION_MAX_ERRORS:
                job = db.query(Jobs).filter(Jobs.jobID == mission.job_id).first()
                _fail(db, mission, now, f"Flash's search for {_job_label(db, job)} stopped after "
                      f"{mission.consecutive_errors} errors in a row ({type(exc).__name__}).", job)
            else:
                _set_next(mission, now, timedelta(minutes=settings.FLASH_MISSION_TRACK_CHECK_MINUTES))
            db.commit()
            outcome["errors"] += 1
    return outcome


# --------------------------------------------------------------------------- status and control

STATE_WORDS = {"AWAITING_JOB": "starting (the job is being created)", "ACTIVE": "active", "BLOCKED": "blocked",
               "PAUSED": "paused", "CLOSED": "closed", "CANCELLED": "cancelled", "FAILED": "stopped"}


def mission_summary(db: Session, mission: FlashMission) -> str:
    job = db.query(Jobs).filter(Jobs.jobID == mission.job_id).first()
    counts: Dict[str, int] = {}
    for status, count in (db.query(FlashMissionCandidate.status, func.count(FlashMissionCandidate.id))
                          .filter(FlashMissionCandidate.mission_id == mission.id)
                          .group_by(FlashMissionCandidate.status)):
        counts[status] = count
    interviewing = sum(counts.get(s, 0) for s in INTERVIEWING)
    parts = [f"{_job_label(db, job)}: {STATE_WORDS.get(mission.state, mission.state)}"
             + (f" ({mission.state_reason})" if mission.state in ("BLOCKED", "FAILED") and mission.state_reason else "")
             + "."]
    parts.append(f"{interviewing} in interviews ({counts.get('SCHEDULED', 0)} scheduled, "
                 f"{counts.get('AWAITING_VERDICT', 0)} awaiting feedback, {counts.get('AWAITING_HUMAN', 0)} waiting "
                 f"on the hiring manager), {counts.get('OFFER_PENDING', 0)} at offer, {counts.get('FILLED', 0)} of "
                 f"{mission.positions} joined.")
    last = (db.query(FlashMissionEvent).filter(FlashMissionEvent.mission_id == mission.id,
                                               FlashMissionEvent.kind.notin_(("error", "feedback_chased")))
            .order_by(FlashMissionEvent.id.desc()).first())
    if last is not None and (last.detail or {}).get("text"):
        parts.append(f"Latest: {last.detail['text']}")
    return " ".join(parts)


_QUERY_NOISE = {"my", "the", "our", "search", "searches", "status", "of", "for", "job", "jobs", "how", "is", "what",
                "flash", "mission", "missions", "s"}


def visible_missions(db: Session, user: Users, query: str = ""):
    """Missions this user started, or on jobs they can see; matched on job title or client name."""
    from app.core.data_scope import job_filter
    from app.models.client import Client

    q = (db.query(FlashMission).join(Jobs, Jobs.jobID == FlashMission.job_id)
         .outerjoin(Client, Client.id == Jobs.client_id)
         .filter(FlashMission.tenant_id == user.tenant_id,
                 or_(FlashMission.requested_by_user_id == user.UserID, job_filter(db, user, FlashMission.job_id))))
    for word in [w for w in re.findall(r"[\w+#.]+", (query or "").lower()) if w not in _QUERY_NOISE and len(w) > 1]:
        like = f"%{word}%"
        q = q.filter(or_(func.lower(Jobs.jobTitle).like(like), func.lower(Jobs.companyName).like(like),
                         func.lower(Client.company_name).like(like)))
    return q.order_by(FlashMission.created_at.desc())


def status_reply(db: Session, user: Users, query: str = "") -> str:
    missions = visible_missions(db, user, query).limit(3).all()
    if not missions:
        return f"I have no search matching \"{query}\"." if query else "You have no Flash searches."
    return "\n".join(mission_summary(db, m) for m in missions)


def _manageable(db: Session, user: Users, mission: FlashMission) -> None:
    from app.core import authority
    from app.core.data_scope import visible_job_or_404

    if mission.tenant_id != user.tenant_id:
        raise MissionError("That search was not found.")
    if mission.requested_by_user_id == user.UserID:
        return
    if not authority.has_permission(db, user, "jobs.edit"):
        raise MissionError("Only the person who started this search, or someone who can edit the job, can change it.")
    try:
        visible_job_or_404(db, user, mission.job_id)
    except HTTPException as exc:
        raise MissionError("That search was not found.") from exc


def control(db: Session, user: Users, mission: FlashMission, action: str, now: Optional[datetime] = None) -> str:
    """pause / resume / cancel, by the owner or someone who may edit the job."""
    now = now or datetime.utcnow()
    _manageable(db, user, mission)
    job = db.query(Jobs).filter(Jobs.jobID == mission.job_id).first()
    label = _job_label(db, job)
    if mission.state in ("CLOSED", "CANCELLED", "FAILED"):
        raise MissionError(f"The search for {label} has already ended ({STATE_WORDS[mission.state]}).")
    if action == "pause":
        mission.state = "PAUSED"
        text = f"Paused the search for {label}. Say resume to continue."
    elif action == "resume":
        if mission.state != "PAUSED":
            raise MissionError(f"The search for {label} isn't paused.")
        mission.state, mission.next_check_at = "ACTIVE", now
        text = f"Resumed the search for {label}."
    elif action == "cancel":
        mission.state, mission.closed_at = "CANCELLED", now
        text = f"Cancelled the search for {label}. Interviews already scheduled stay as they are."
    else:
        raise MissionError(f"Unknown action {action!r}")
    _event(db, mission, action, f"{text} ({_person(user)})", tell=mission.requested_by_user_id != user.UserID)
    return text


def control_by_query(db: Session, user: Users, action: str, query: str) -> str:
    missions = visible_missions(db, user, query).filter(FlashMission.state.notin_(("CLOSED", "CANCELLED", "FAILED"))).all()
    if not missions:
        return f"I have no open search matching \"{query}\"."
    if len(missions) > 1:
        return "Which search? " + "; ".join(_job_label(db, db.query(Jobs).filter(Jobs.jobID == m.job_id).first())
                                            for m in missions) + "."
    try:
        return control(db, user, missions[0], action)
    except MissionError as exc:
        return str(exc)


# --------------------------------------------------------------------------- Flash tools

def _register_tools() -> None:
    from app.services.flash_brain.tools import FlashTool, ToolError, first_line, register, said, schema

    def status_tool(ctx, args):
        missions = visible_missions(ctx.db, ctx.user, args.get("query") or "").limit(3).all()
        return {"text": status_reply(ctx.db, ctx.user, args.get("query") or ""),
                "items": [{"mission_id": m.id, "state": m.state, "job_id": m.job_id} for m in missions]}

    def control_tool(action):
        def handler(ctx, args):
            mission = ctx.db.query(FlashMission).filter(FlashMission.id == (args.get("mission_id") or "")).first()
            if mission is None:
                raise ToolError("That search was not found.")
            try:
                return {"text": control(ctx.db, ctx.user, mission, action, ctx.now), "mission_id": mission.id}
            except MissionError as exc:
                raise ToolError(str(exc)) from exc
        return handler

    register(FlashTool("mission_status", "Progress of Flash's searches (missions) the user started or can see, "
                       "matched on job title or client; empty query = all.",
                       schema({"query": {"type": "string"}}), "jobs.view", status_tool, "see jobs",
                       summary=said(lambda a, o: "Checked on your Flash searches.")))
    for action in ("pause", "resume", "cancel"):
        register(FlashTool(f"{action}_mission", f"{action.title()} one of Flash's searches (id from mission_status). "
                           "Allowed for the person who started it or someone who can edit the job.",
                           schema({"mission_id": {"type": "string"}}), None, control_tool(action),
                           f"{action} this search", mutating=True, summary=first_line))


_register_tools()
