"""Emails about tasks, through the staff mail path (staff_mail_service.queue_staff_email):

  - assigned:    a task lands on someone other than the person who created it (system tasks such
                 as Thunder reply hand-offs and forwarded emails have no creator, so they always mail);
  - next step:   the next action logged on a task (Log update) becomes a follow-up task;
  - reassigned:  a manager approved moving the task to someone else;
  - due:         task_due_reminders job (every 5 min): the task's due time has come and it is still
                 open. Sent only within TASK_DUE_REMINDER_GRACE_MINUTES of the due time, so a
                 stopped worker or a first run never mails a stale backlog; skipped when the task was
                 created already due (its assignment email said so).

Each email has a deterministic key (task, kind, assignee, due time), so it goes out once; a new
due date or a new assignee gets a fresh one. Emails are queued after the task is committed and a
failure to queue never undoes the task: it is logged with the stack and the task stays on My Tasks."""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.user import Users

logger = logging.getLogger(__name__)

OPEN_STATUSES = ("NEW", "IN_PROGRESS", "ON_HOLD")
DESCRIPTION_PREVIEW_CHARS = 600


def task_path(task: Task) -> str:
    """Where the email's button opens: the task's own link, the candidate it is about, or the task
    itself on My Tasks (?task= opens it there)."""
    if task.link:
        return task.link
    if task.candidate_id:
        return f"/candidates/{task.candidate_id}"
    return f"/my-tasks?task={task.id}"


def _due_text(task: Task) -> str:
    return f"Due: {task.due_date:%Y-%m-%d %H:%M} UTC" if task.due_date else "No due date"


def _queue(db: Session, task: Task, kind: str, subject: str, opening: str) -> bool:
    assignee = db.query(Users).filter(Users.UserID == task.assigned_to_user_id).first()
    if assignee is None:
        raise ValueError(f"Task #{task.id} is assigned to unknown user {task.assigned_to_user_id}")
    from app.services.staff_mail_service import queue_staff_email

    description = (task.description or "").strip()
    if len(description) > DESCRIPTION_PREVIEW_CHARS:
        description = description[:DESCRIPTION_PREVIEW_CHARS].rstrip() + "..."
    due_key = f"{task.due_date:%Y%m%dT%H%M}" if task.due_date else "none"
    return queue_staff_email(
        assignee, key=f"task-{kind}-{task.id}-{assignee.UserID}-{due_key}",
        subject=subject, link_path=task_path(task), link_label="Open the task",
        paragraphs=[opening, f"Priority: {task.priority.capitalize()}. {_due_text(task)}.", description or None],
    )


def notify_task_assigned(db: Session, task: Task, *, kind: str = "assigned") -> bool:
    """Queue the assignment email for a committed task. kind: "assigned", "next_step" or
    "reassigned". Returns whether an email was queued; never raises (the task already exists)."""
    if not task.assigned_to_user_id or task.status not in OPEN_STATUSES:
        return False
    if kind == "assigned" and task.created_by_user_id == task.assigned_to_user_id:
        return False  # you made it for yourself
    try:
        if kind == "next_step":
            return _queue(db, task, kind, f"Next step: {task.title}"[:250],
                          f"Your next step is scheduled as task #{task.id}: {task.title}.")
        if kind == "reassigned":
            return _queue(db, task, kind, f"Task #{task.id} moved to you: {task.title}"[:250],
                          f"Task #{task.id} was reassigned to you: {task.title}.")
        creator = db.query(Users).filter(Users.UserID == task.created_by_user_id).first() \
            if task.created_by_user_id else None
        by = f" by {creator.UserName or creator.UserEmail}" if creator else ""
        return _queue(db, task, kind, f"New task #{task.id}: {task.title}"[:250],
                      f"Task #{task.id} was assigned to you{by}: {task.title}.")
    except Exception as exc:
        logger.error(f"[TaskEmail] {kind} email for task #{task.id} not queued: {exc}", exc_info=True)
        return False


def backlog_guard(db: Session, now: datetime) -> None:
    """Nothing to expire: run() only mails tasks that fell due within the last grace window."""
    from app.core.config import settings

    logger.info(f"[TaskEmail] first run: tasks due before "
                f"{now - timedelta(minutes=settings.TASK_DUE_REMINDER_GRACE_MINUTES):%Y-%m-%d %H:%M} UTC "
                f"get no due email")


def run_due_reminders(db: Session, now: Optional[datetime] = None) -> Dict:
    """task_due_reminders job: one email per open, assigned task whose due time just came."""
    from app.core.config import settings

    now = now or datetime.utcnow()
    since = now - timedelta(minutes=settings.TASK_DUE_REMINDER_GRACE_MINUTES)
    due = db.query(Task).filter(
        Task.status.in_(OPEN_STATUSES), Task.assigned_to_user_id.isnot(None),
        Task.due_date.isnot(None), Task.due_date > since, Task.due_date <= now,
    ).all()
    queued = skipped = failed = 0
    for task in due:
        # Created already due (e.g. a Thunder hand-off due now): its assignment email covered it
        if task.created_at is not None and task.created_at >= task.due_date - timedelta(minutes=5):
            skipped += 1
            continue
        try:
            if _queue(db, task, "due", f"Due now: task #{task.id} {task.title}"[:250],
                      f"Task #{task.id} is due: {task.title}."):
                queued += 1
            else:
                skipped += 1
        except Exception as exc:
            failed += 1
            logger.error(f"[TaskEmail] due email for task #{task.id} not queued: {exc}", exc_info=True)
    logger.info(f"[TaskEmail] due reminders: {len(due)} due, {queued} queued, {skipped} skipped, {failed} failed")
    if failed:
        raise RuntimeError(f"{failed} task due email(s) could not be queued (see log); {queued} were queued")
    return {"due": len(due), "queued": queued, "skipped": skipped}
