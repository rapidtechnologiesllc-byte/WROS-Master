"""
S-434 -- Overdue task escalation.

Confirmed 2026-08-04: crossing the due date while still open is a real
escalation event with two effects, not just a red label --
(1) notifies the assignee's reporting manager, (2) bumps the task's
stored Priority up one tier, capped at HIGH (never auto-reaches
URGENT -- Urgent stays a deliberate, Thunder-challenged human choice).
Both fire once per task (is_escalated guards re-firing on every scan).
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.task import PRIORITY_BUMP_CEILING, PRIORITY_ORDER, Task
from app.models.user import Users

OPEN_STATUSES = ("NEW", "IN_PROGRESS", "ON_HOLD")
_TIER_BY_ORDER = {v: k for k, v in PRIORITY_ORDER.items()}


def _bump_one_tier_capped(priority: str) -> str:
    if priority == "URGENT":
        return priority  # never touched -- stays whatever it already is
    current = PRIORITY_ORDER[priority]
    ceiling = PRIORITY_ORDER[PRIORITY_BUMP_CEILING]
    return _TIER_BY_ORDER[min(current + 1, ceiling)]


def escalate_overdue_tasks(db: Session, *, now: Optional[datetime] = None) -> List[Task]:
    from app.services.notification_service import send_notification

    now = now or datetime.utcnow()
    overdue = db.query(Task).filter(
        Task.status.in_(OPEN_STATUSES),
        Task.due_date.isnot(None),
        Task.due_date < now,
        Task.is_escalated.is_(False),
    ).all()

    escalated = []
    for task in overdue:
        task.is_escalated = True
        task.escalated_at = now
        task.priority = _bump_one_tier_capped(task.priority)
        db.add(task)

        if task.assigned_to_user_id:
            from app.services.task_assignment_service import resolve_reporting_manager

            assignee = db.query(Users).filter(Users.UserID == task.assigned_to_user_id).first()
            manager = resolve_reporting_manager(db, task.assigned_to_user_id) if assignee else None
            if manager:
                send_notification(
                    db, calling_context_tenant_id=manager.tenant_id, recipient=manager,
                    priority_tier="P1",
                    message=(
                        f"Task #{task.id} ({task.title}) assigned to "
                        f"{assignee.UserName or assignee.UserID} is overdue and has been "
                        f"escalated. Priority bumped to {task.priority}."
                    ),
                )
        escalated.append(task)

    db.commit()
    return escalated
