"""
S-434 -- Task assignment: department + round-robin, capacity-aware,
manager-approved reassignment on unavailability.

Real decisions from Avinash, 2026-08-04 session:
- Task is the org-level object with its OWN native department +
  round-robin assignment mechanism -- ticketing (a future Task type)
  reuses this, it does not get its own separate routing logic.
- Round-robin must be capacity-aware: skip a user who's overloaded
  rather than mechanically cycling through the department regardless
  of load, and alert the manager (talk to them / hiring-gap signal)
  instead of silently piling on more work.
- Velocity/throughput is meant to come from real Task-effort-backed
  timesheet data (see wros_task_numbering_s434_backlog memory's
  "Hours source -- HYBRID" note). That Task<->Timesheet tie is a real
  architecture fork against the revenue-critical Timesheet model
  (Timesheet.allocation_id is NOT NULL, tied to client billing) and is
  deliberately NOT built in this pass -- flagged for Avinash's
  decision rather than guessed at. OPEN_TASK_WIP_CAP below is an
  honest v1 proxy (current open-task count) standing in for that
  richer signal, same "flag the real simplification, keep building"
  posture this codebase already uses elsewhere (e.g. S-069).
- Resource-unavailability reassignment is advisory only -- a
  TaskReassignmentRequest is raised, never auto-applied; a manager
  must approve, and retains full discretion on who it goes to
  (including themselves), not constrained to round-robin's own pick.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.task import Task, TaskCapacityAlert, TaskReassignmentRequest
from app.models.user import Users

OPEN_TASK_WIP_CAP = 8  # v1 proxy for "overloaded" -- see module docstring.
OPEN_STATUSES = ("NEW", "IN_PROGRESS", "ON_HOLD")


def resolve_reporting_manager(db: Session, user_id: str) -> Optional[Users]:
    """Users has no reporting-manager column of its own -- the real
    hierarchy lives on Employee (wros_user_id links an Employee record
    to its login Users account; reporting_manager_user_id is already a
    direct Users.UserID). Returns None if the user has no linked
    Employee record or no manager set -- never invents one."""
    employee = db.query(Employee).filter(Employee.wros_user_id == user_id).first()
    if not employee or not employee.reporting_manager_user_id:
        return None
    return db.query(Users).filter(Users.UserID == employee.reporting_manager_user_id).first()


def _open_task_counts_by_user(db: Session, user_ids: List[str]) -> dict:
    if not user_ids:
        return {}
    rows = (
        db.query(Task.assigned_to_user_id, func.count(Task.id))
        .filter(Task.assigned_to_user_id.in_(user_ids), Task.status.in_(OPEN_STATUSES))
        .group_by(Task.assigned_to_user_id)
        .all()
    )
    return {uid: count for uid, count in rows}


def raise_capacity_alert(db: Session, *, user: Users, open_count: int) -> TaskCapacityAlert:
    """Advisory-only -- notifies the user's reporting manager with a
    suggestion, never auto-reassigns existing work."""
    from app.services.notification_service import send_notification

    alert = TaskCapacityAlert(
        user_id=user.UserID, department_id=user.department_id, open_task_count=open_count,
        reason=(
            f"{user.UserName or user.UserID} has {open_count} open tasks, at or above the "
            f"{OPEN_TASK_WIP_CAP}-task working-capacity threshold. New tasks are being routed "
            f"to other department members. Consider a check-in, or -- if this is sustained "
            f"across the team -- a real hiring-gap signal."
        ),
    )
    db.add(alert)
    db.flush()

    manager = resolve_reporting_manager(db, user.UserID)
    if manager:
        send_notification(
            db, calling_context_tenant_id=manager.tenant_id, recipient=manager,
            priority_tier="P1", message=alert.reason,
        )
    return alert


def _eligible_department_users(db: Session, department_id: int) -> List[Users]:
    return db.query(Users).filter(Users.department_id == department_id).all()


def assign_task_round_robin(db: Session, task: Task) -> Optional[Task]:
    """Least-loaded active department member, skipping anyone at/over
    OPEN_TASK_WIP_CAP (capacity-aware v1). If every member is at
    capacity, assigns to the least-loaded anyway (a department can't be
    left with zero owner) but raises a capacity alert for each
    over-cap member encountered, same as the normal skip path."""
    if not task.department_id:
        return None

    members = _eligible_department_users(db, task.department_id)
    if not members:
        return None

    loads = _open_task_counts_by_user(db, [m.UserID for m in members])

    under_cap = []
    for m in members:
        count = loads.get(m.UserID, 0)
        if count >= OPEN_TASK_WIP_CAP:
            raise_capacity_alert(db, user=m, open_count=count)
        else:
            under_cap.append(m)

    pool = under_cap or members
    chosen = min(pool, key=lambda m: loads.get(m.UserID, 0))

    task.assigned_to_user_id = chosen.UserID
    db.add(task)
    return task


def request_reassignment(
    db: Session, *, task: Task, from_user_id: str, suggested_to_user_id: Optional[str] = None,
    reason: str = "ASSIGNEE_UNAVAILABLE",
) -> TaskReassignmentRequest:
    """Raises a PENDING request -- never applies the reassignment
    itself. suggested_to_user_id, if given, is only a suggestion (e.g.
    round-robin's own next pick); the approving manager can override
    it with anyone in the department, including themselves."""
    req = TaskReassignmentRequest(
        task_id=task.id, from_user_id=from_user_id,
        suggested_to_user_id=suggested_to_user_id, reason=reason,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def suggest_todays_reassignments(db: Session, *, unavailable_user_id: str, now: Optional[datetime] = None) -> List[TaskReassignmentRequest]:
    """Per Avinash's spec: only tasks due TODAY get reassigned when
    someone is unavailable -- tasks due later are left as-is (not yet
    confirmed whether that should change; see the memory note)."""
    from app.services.task_service import _start_of_today
    from datetime import timedelta

    now = now or datetime.utcnow()
    today_start = _start_of_today(now)
    tomorrow_start = today_start + timedelta(days=1)

    due_today = db.query(Task).filter(
        Task.assigned_to_user_id == unavailable_user_id,
        Task.status.in_(OPEN_STATUSES),
        Task.due_date.isnot(None),
        Task.due_date >= today_start,
        Task.due_date < tomorrow_start,
    ).all()

    requests = []
    for task in due_today:
        suggestion = None
        if task.department_id:
            members = [m for m in _eligible_department_users(db, task.department_id) if m.UserID != unavailable_user_id]
            if members:
                loads = _open_task_counts_by_user(db, [m.UserID for m in members])
                suggestion = min(members, key=lambda m: loads.get(m.UserID, 0)).UserID
        requests.append(request_reassignment(db, task=task, from_user_id=unavailable_user_id, suggested_to_user_id=suggestion))
    return requests


def approve_reassignment(db: Session, req: TaskReassignmentRequest, *, approved_by_user_id: str, final_to_user_id: str) -> TaskReassignmentRequest:
    """Manager's own explicit call -- final_to_user_id can be the
    manager themselves or anyone else in the department, not
    constrained to req.suggested_to_user_id."""
    task = db.query(Task).filter(Task.id == req.task_id).first()
    if task:
        task.assigned_to_user_id = final_to_user_id
        db.add(task)

    req.status = "APPROVED"
    req.approved_by_user_id = approved_by_user_id
    req.final_to_user_id = final_to_user_id
    req.resolved_at = datetime.utcnow()
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def reject_reassignment(db: Session, req: TaskReassignmentRequest, *, approved_by_user_id: str) -> TaskReassignmentRequest:
    req.status = "REJECTED"
    req.approved_by_user_id = approved_by_user_id
    req.resolved_at = datetime.utcnow()
    db.add(req)
    db.commit()
    db.refresh(req)
    return req
