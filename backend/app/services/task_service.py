"""
S-434 -- Org-wide Task Dashboard, core service.

Real product decisions from Avinash, captured 2026-08-04 session:
- Task # is the org-wide, single-sequence primary key itself (see
  app.models.task's module docstring for why no separate counter table
  is needed).
- Priority (URGENT/HIGH/MEDIUM/LOW) is a real stored field. Creating a
  task with priority=URGENT triggers a Thunder plausibility check
  (validate_urgent_priority) BEFORE the task is treated as
  uncontested -- this doesn't block creation (the creator's own
  choice is respected), it surfaces a challenge for the creator to
  resolve, same advisory-not-blocking posture as every other
  consequential-action pattern in this codebase.
- Daily dashboard ranking is TWO layers, not one blended score (a
  single weighted Priority+DueDate score would let a Low-priority
  task due today get buried -- Avinash's own explicit correction):
    1. Inclusion (hard filter): every task due today, or overdue, is
       unconditionally on the daily list regardless of Priority.
    2. Ordering within that list: Priority, highest first.
  get_daily_task_list() implements exactly this.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.task import PRIORITY_ORDER, TASK_PRIORITIES, TASK_RECURRENCES, Task

logger = logging.getLogger(__name__)

TASK_URGENCY_VALIDATION_SYSTEM_PROMPT = (
    "You are Thunder, BlitzenX's operations assistant. A team member is "
    "creating a Task and marked it URGENT. Your job is to sanity-check that "
    "claim before it's accepted, so Urgent stays meaningful and doesn't get "
    "inflated. Respond with EXACTLY one line in the form "
    "'PLAUSIBLE: <yes|no> | NOTE: <one short sentence>'. Say PLAUSIBLE: yes "
    "for anything genuinely time-critical or safety/compliance/outage-"
    "shaped; say PLAUSIBLE: no for routine requests dressed up as urgent, "
    "and phrase NOTE as a brief, respectful question back to the creator "
    "(e.g. 'Is this blocking something today, or can it wait?')."
)

def _default_urgency_llm_call(system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
    from app.services.prompt_framework_service import _default_llm_call
    import os
    api_key = os.getenv("GEMINI_API_KEY", "")
    return _default_llm_call(system_prompt, user_prompt, max_tokens, temperature, api_key)

def validate_urgent_priority(
    db: Session, *, tenant_id: str, title: str, description: Optional[str], llm_call=None,
) -> "tuple[bool, str]":
    """Returns (is_plausible, note). Never raises into the caller -- an
    LLM failure here must never block task creation (BR: advisory
    check, not a hard gate); treated as plausible with a note saying
    the check itself couldn't run, so the creator isn't blocked by an
    LLM outage."""
    from app.services.prompt_framework_service import call_llm, LLMCallFailedError

    user_prompt = f"Task title: {title}\nDescription: {description or '(none)'}"
    try:
        response = call_llm(
            db, tenant_id=tenant_id, candidate_id=None,
            prompt_type="TASK_URGENCY_VALIDATION", template_version="v1.0",
            system_prompt=TASK_URGENCY_VALIDATION_SYSTEM_PROMPT, user_prompt=user_prompt,
            max_tokens=60, temperature=0.0, llm_call=llm_call,
        )
    except LLMCallFailedError:
        return True, "Urgency check unavailable right now -- accepted as-is."
    except Exception:
        return True, "Urgency check unavailable right now -- accepted as-is."

    is_plausible = "PLAUSIBLE: YES" in response.upper()
    note = response.split("NOTE:", 1)[1].strip() if "NOTE:" in response.upper() else response.strip()
    return is_plausible, note

TASK_LINK_MAX_LENGTH = 512


def validate_task_link(link: Optional[str]) -> None:
    """A task link is an in-app path: it starts with "/" and not "//" (which a browser reads as
    another site), with no whitespace or backslashes. None means no link."""
    if link is None:
        return
    if (not isinstance(link, str) or not link.startswith("/") or link.startswith("//") or "\\" in link
            or any(ch.isspace() for ch in link) or len(link) > TASK_LINK_MAX_LENGTH):
        raise ValueError(f"Task link must be an in-app path like '/jobs/123', got {link!r}")


def create_task(
    db: Session,
    *,
    title: str,
    description: Optional[str] = None,
    priority: str = "MEDIUM",
    created_by_user_id: Optional[str] = None,
    department_id: Optional[int] = None,
    due_date: Optional[datetime] = None,
    is_external: bool = False,
    visibility_scope: str = "ASSIGNEE_MANAGER_DEPARTMENT",
    task_type: str = "GENERAL",
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    parent_task_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    assigned_to_user_id: Optional[str] = None,
    expense_id: Optional[str] = None,
    invoice_id: Optional[str] = None,
    urgency_llm_call=None,
    link: Optional[str] = None,
    candidate_id: Optional[str] = None,
    recurrence: Optional[str] = None,
) -> Task:
    if priority not in TASK_PRIORITIES:
        raise ValueError(f"Unknown priority {priority!r}")
    if recurrence is not None and recurrence not in TASK_RECURRENCES:
        raise ValueError(f"Repeat must be one of {TASK_RECURRENCES}, got {recurrence!r}")
    if recurrence and due_date is None:
        raise ValueError("A repeating task needs a due date")
    validate_task_link(link)

    task = Task(
        title=title, description=description, priority=priority,
        created_by_user_id=created_by_user_id, department_id=department_id,
        due_date=due_date, is_external=is_external, visibility_scope=visibility_scope,
        task_type=task_type, category=category, subcategory=subcategory,
        parent_task_id=parent_task_id, tenant_id=tenant_id,
        assigned_to_user_id=assigned_to_user_id, expense_id=expense_id, invoice_id=invoice_id, link=link,
        candidate_id=candidate_id, recurrence=recurrence,
    )

    if priority == "URGENT":
        is_plausible, note = validate_urgent_priority(
            db, tenant_id=created_by_user_id or "system", title=title, description=description,
            llm_call=urgency_llm_call,
        )
        if not is_plausible:
            task.priority_challenged = True
            task.priority_challenge_note = note
        else:
            # Still record the attempt -- satisfies the model's own
            # ck_task_urgent_has_validation_attempt constraint and gives
            # a real audit trail even when Thunder agreed.
            task.priority_challenge_note = note

    db.add(task)
    db.flush()

    if department_id is not None and task.assigned_to_user_id is None:
        from app.services.task_assignment_service import assign_task_round_robin
        assign_task_round_robin(db, task)

    db.commit()
    db.refresh(task)
    return task

def confirm_urgent_task(db: Session, task: Task) -> Task:
    """Creator/manager explicitly confirms Urgent stands despite
    Thunder's challenge -- never a silent auto-downgrade."""
    task.priority_challenged = False
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

def _start_of_today(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)

def get_daily_task_list(db: Session, *, assigned_to_user_id: str, now: Optional[datetime] = None) -> List[Task]:
    """Layer 1 (hard filter): every open/in-progress task assigned to
    this user that's due today OR overdue is unconditionally included,
    regardless of Priority -- a Low-priority task due today is never
    buried. Layer 2 (ordering): Priority, highest first, then soonest
    due_date as the tiebreaker within the same priority tier."""
    now = now or datetime.utcnow()
    today_start = _start_of_today(now)
    tomorrow_start = today_start + timedelta(days=1)

    tasks = db.query(Task).filter(
        Task.assigned_to_user_id == assigned_to_user_id,
        Task.status.in_(("NEW", "IN_PROGRESS", "ON_HOLD")),
        Task.due_date.isnot(None),
        Task.due_date < tomorrow_start,  # due today or overdue -- the hard floor
    ).all()

    return sorted(
        tasks,
        key=lambda t: (-PRIORITY_ORDER.get(t.priority, 0), t.due_date or now),
    )

def get_upcoming_urgent_tasks(db: Session, *, assigned_to_user_id: str, now: Optional[datetime] = None) -> List[Task]:
    """Not-due-today Urgent tasks, surfaced separately as a heads-up --
    per the 2026-08-04 note, this stays a distinct 'upcoming' view
    rather than polluting today's must-do list."""
    now = now or datetime.utcnow()
    tomorrow_start = _start_of_today(now) + timedelta(days=1)

    return db.query(Task).filter(
        Task.assigned_to_user_id == assigned_to_user_id,
        Task.status.in_(("NEW", "IN_PROGRESS", "ON_HOLD")),
        Task.priority == "URGENT",
        (Task.due_date.is_(None)) | (Task.due_date >= tomorrow_start),
    ).order_by(Task.due_date.asc().nullslast()).all()

def get_scheduled_tasks(db: Session, *, assigned_to_user_id: str, now: Optional[datetime] = None,
                        days: Optional[int] = None) -> List[Task]:
    """Open non-urgent tasks due after today, soonest first, so the next actions are visible
    before their day. No horizon by default: an open task its owner cannot see anywhere is lost
    (a 45-day Core certification follow-up was hidden by the old 30-day window); `days` limits it."""
    now = now or datetime.utcnow()
    tomorrow_start = _start_of_today(now) + timedelta(days=1)
    query = db.query(Task).filter(
        Task.assigned_to_user_id == assigned_to_user_id,
        Task.status.in_(("NEW", "IN_PROGRESS", "ON_HOLD")),
        Task.priority != "URGENT",
        Task.due_date >= tomorrow_start,
    )
    if days is not None:
        query = query.filter(Task.due_date < tomorrow_start + timedelta(days=days))
    return query.order_by(Task.due_date.asc()).all()

def complete_task(db: Session, task: Task) -> Task:
    task.status = "COMPLETED"
    task.completed_at = datetime.utcnow()
    db.add(task)
    open_next_occurrence(db, task)
    db.commit()
    db.refresh(task)
    return task


def _add_months(moment: datetime, months: int) -> datetime:
    month = moment.month - 1 + months
    year, month = moment.year + month // 12, month % 12 + 1
    days_in_month = (datetime(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)).day
    return moment.replace(year=year, month=month, day=min(moment.day, days_in_month))


def next_due(due: datetime, recurrence: str) -> datetime:
    if recurrence == "WEEKLY":
        return due + timedelta(days=7)
    if recurrence == "BIWEEKLY":
        return due + timedelta(days=14)
    if recurrence == "MONTHLY":
        return _add_months(due, 1)
    if recurrence == "QUARTERLY":
        return _add_months(due, 3)
    raise ValueError(f"Unknown repeat {recurrence!r}")


def candidate_series_end(db: Session, candidate_id: str) -> Optional[str]:
    """Why a repeating task about this candidate stops, or None while it should go on: the
    candidate joined (is an employee), was archived, or is in a post-rejection no-contact period."""
    from app.models.candidate import Candidate
    from app.models.employee import Employee
    from app.services.candidate_contact_policy import is_archived, rejection_cooldown_until

    if db.query(Candidate.candidateID).filter(Candidate.candidateID == candidate_id).first() is None:
        return "the candidate no longer exists"
    if db.query(Employee.id).filter(Employee.candidate_id == candidate_id).first() is not None:
        return "the candidate joined"
    if is_archived(db, candidate_id):
        return "the candidate is archived"
    if rejection_cooldown_until(db, candidate_id) is not None:
        return "the candidate was rejected"
    return None


def open_next_occurrence(db: Session, task: Task, now: Optional[datetime] = None) -> Optional[Task]:
    """A completed repeating task opens the next one (same person, text and repeat), due one
    interval after this one and never in the past. Caller commits."""
    if not task.recurrence:
        return None
    if task.candidate_id:
        reason = candidate_series_end(db, task.candidate_id)
        if reason:
            logger.info(f"[Tasks] Task #{task.id} stops repeating: {reason}")
            return None
    now = now or datetime.utcnow()
    due = next_due(task.due_date or now, task.recurrence)
    while due <= now:
        due = next_due(due, task.recurrence)
    following = Task(
        title=task.title, description=task.description, priority=task.priority, status="NEW",
        task_type=task.task_type, category=task.category, subcategory=task.subcategory,
        tenant_id=task.tenant_id, assigned_to_user_id=task.assigned_to_user_id,
        created_by_user_id=task.created_by_user_id, department_id=task.department_id,
        candidate_id=task.candidate_id, parent_task_id=task.id, due_date=due, is_external=task.is_external,
        visibility_scope=task.visibility_scope, link=task.link, recurrence=task.recurrence,
    )
    db.add(following)
    db.flush()
    logger.info(f"[Tasks] Task #{task.id} repeats {task.recurrence.lower()}: next is #{following.id} due {due:%Y-%m-%d}")
    return following


def stop_repeating(db: Session, task: Task) -> Task:
    task.recurrence = None
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_candidate_tasks(db: Session, candidate_id: str, tenant_id: Optional[int]) -> List[Task]:
    """Open tasks first (soonest due first), then the finished ones, newest first."""
    from sqlalchemy import case, or_

    finished = Task.status.in_(("COMPLETED", "CANCELLED"))
    return (db.query(Task)
            .filter(Task.candidate_id == candidate_id, or_(Task.tenant_id.is_(None), Task.tenant_id == tenant_id))
            .order_by(case((finished, 1), else_=0), Task.due_date.asc().nullslast(), Task.completed_at.desc())
            .all())
