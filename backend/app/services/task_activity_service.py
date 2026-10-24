"""Task updates -- what was done on a task and what happens next.

log_task_update() is the single path:
1. records a TaskActivity (type, outcome, notes, next action),
2. if the task is about a candidate, writes the update to that
   candidate's history ("Activity Logged") so the profile shows the
   whole trail,
3. if a next action is given, creates it as a follow-up Task assigned
   to the same person, linked to the same candidate, due on the chosen
   date -- so it appears in their My Tasks that day,
4. moves the task to IN_PROGRESS, or COMPLETED when the caller says
   this update finishes it.
Everything commits together.
"""
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.task import (
    TASK_ACTIVITY_OUTCOMES, TASK_ACTIVITY_TYPES, TASK_NEXT_ACTION_TYPES, Task, TaskActivity,
)
from app.models.user import Users

logger = logging.getLogger(__name__)

HISTORY_EVENT_TYPE = "Activity Logged"


_LABEL_OVERRIDES = {"LINKEDIN_MESSAGE": "LinkedIn message", "WHATSAPP": "WhatsApp"}


def _label(code: Optional[str]) -> str:
    return _LABEL_OVERRIDES.get(code or "", (code or "").replace("_", " ").capitalize())


def update_options() -> dict:
    """Choices for the Log update form (single source: the model)."""
    return {
        "activity_types": [{"value": v, "label": _label(v)} for v in TASK_ACTIVITY_TYPES],
        "outcomes": [{"value": v, "label": _label(v)} for v in TASK_ACTIVITY_OUTCOMES],
        "next_action_types": [{"value": v, "label": _label(v)} for v in TASK_NEXT_ACTION_TYPES],
    }


def _history_note(activity: TaskActivity, task: Task) -> str:
    parts = [f"{_label(activity.activity_type)}"]
    if activity.outcome:
        parts[0] += f" -- {_label(activity.outcome)}"
    parts.append(activity.notes.strip())
    if activity.next_action_type:
        due = activity.next_action_due.strftime("%d %b %Y %H:%M") if activity.next_action_due else "no date"
        nxt = f"Next: {_label(activity.next_action_type)} by {due}"
        if activity.next_action_note:
            nxt += f" -- {activity.next_action_note.strip()}"
        parts.append(nxt)
    parts.append(f"(Task #{task.id}: {task.title})")
    return "\n".join(parts)


def log_task_update(
    db: Session,
    task: Task,
    user: Users,
    *,
    activity_type: str,
    notes: str,
    outcome: Optional[str] = None,
    next_action_type: Optional[str] = None,
    next_action_due: Optional[datetime] = None,
    next_action_note: Optional[str] = None,
    complete_task: bool = False,
) -> TaskActivity:
    """Raises ValueError on invalid input (nothing is written)."""
    if activity_type not in TASK_ACTIVITY_TYPES:
        raise ValueError(f"activity_type must be one of {TASK_ACTIVITY_TYPES}")
    if outcome and outcome not in TASK_ACTIVITY_OUTCOMES:
        raise ValueError(f"outcome must be one of {TASK_ACTIVITY_OUTCOMES}")
    if not notes or not notes.strip():
        raise ValueError("Describe what was done in notes")
    if next_action_type:
        if next_action_type not in TASK_NEXT_ACTION_TYPES:
            raise ValueError(f"next_action_type must be one of {TASK_NEXT_ACTION_TYPES}")
        if not next_action_due:
            raise ValueError("A next action needs a due date")
    elif next_action_due or (next_action_note and next_action_note.strip()):
        raise ValueError("Pick the next action type")
    if task.status in ("COMPLETED", "CANCELLED"):
        raise ValueError(f"Task #{task.id} is {task.status.lower()}; updates go on its follow-up task")

    activity = TaskActivity(
        tenant_id=task.tenant_id or user.tenant_id,
        task_id=task.id,
        candidate_id=task.candidate_id,
        activity_type=activity_type,
        outcome=outcome or None,
        notes=notes.strip(),
        next_action_type=next_action_type or None,
        next_action_due=next_action_due,
        next_action_note=(next_action_note or "").strip() or None,
        created_by_user_id=user.UserID,
    )
    db.add(activity)

    if next_action_type:
        title = f"{_label(next_action_type)}"
        if task.candidate_id and task.candidate is not None:
            name = " ".join(p for p in [task.candidate.candidateFirstName, task.candidate.candidateLastName] if p)
            title += f": {name or task.candidate_id}"
        else:
            title += f": {task.title}"
        follow_up = Task(
            title=title[:300],
            description=activity.next_action_note,
            priority=task.priority if task.priority != "URGENT" else "HIGH",
            status="NEW",
            task_type="GENERAL",
            category=task.category,
            subcategory=task.subcategory,
            tenant_id=task.tenant_id or user.tenant_id,
            assigned_to_user_id=task.assigned_to_user_id or user.UserID,
            created_by_user_id=user.UserID,
            department_id=task.department_id,
            candidate_id=task.candidate_id,
            parent_task_id=task.id,
            due_date=next_action_due,
            is_external=task.is_external,
            visibility_scope=task.visibility_scope,
        )
        db.add(follow_up)
        db.flush()
        activity.follow_up_task_id = follow_up.id

    if complete_task:
        from app.services.task_service import open_next_occurrence

        task.status = "COMPLETED"
        task.completed_at = datetime.utcnow()
        open_next_occurrence(db, task)
    elif task.status == "NEW":
        task.status = "IN_PROGRESS"
    db.add(task)
    db.flush()

    if task.candidate_id:
        from app.models.candidate_history import CandidateHistory
        db.add(CandidateHistory(
            candidateID=task.candidate_id,
            event_type=HISTORY_EVENT_TYPE,
            note=_history_note(activity, task),
            performed_by_id=user.UserID,
            performed_by_name=user.UserName or user.UserEmail,
            event_at=datetime.utcnow(),
        ))

    db.commit()
    db.refresh(activity)
    logger.info(f"[TaskActivity] Task #{task.id} update {activity.id} by {user.UserID} "
                f"(follow-up task {activity.follow_up_task_id})")
    return activity


def list_task_updates(db: Session, task: Task) -> List[TaskActivity]:
    """Updates on this task and on the tasks it was a follow-up of, newest first,
    so opening a follow-up shows the whole thread."""
    chain_ids = []
    current, seen = task, set()
    while current is not None and current.id not in seen:
        seen.add(current.id)
        chain_ids.append(current.id)
        current = current.parent_task
    return (
        db.query(TaskActivity)
        .filter(TaskActivity.task_id.in_(chain_ids))
        .order_by(TaskActivity.created_at.desc(), TaskActivity.id.desc())
        .all()
    )


def activity_to_dict(activity: TaskActivity) -> dict:
    creator = activity.created_by
    return {
        "id": activity.id,
        "task_id": activity.task_id,
        "candidate_id": activity.candidate_id,
        "activity_type": activity.activity_type,
        "outcome": activity.outcome,
        "notes": activity.notes,
        "next_action_type": activity.next_action_type,
        "next_action_due": activity.next_action_due.isoformat() if activity.next_action_due else None,
        "next_action_note": activity.next_action_note,
        "follow_up_task_id": activity.follow_up_task_id,
        "created_by_user_id": activity.created_by_user_id,
        "created_by_name": (creator.UserName or creator.UserEmail) if creator else None,
        "created_at": activity.created_at.isoformat() if activity.created_at else None,
    }
