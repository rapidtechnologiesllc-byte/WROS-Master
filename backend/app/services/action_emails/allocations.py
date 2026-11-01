"""Allocation emails: an employee allocated, an allocation ended, an edit applied (end date, bill
rate, utilization, billable), and the decision on an edit that waited for margin approval. The
people on an allocation: the employee, their reporting manager and BU head, the project's manager,
the renewal owner and the client's team. The approver of a below-floor change already gets the
approval task's email (task_notification_service), so a pending change mails nobody here."""
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.employee import Employee
from app.models.employee_allocation import AllocationChange, EmployeeAllocation
from app.models.project import Project
from app.models.user import Users
from app.services.action_emails.core import Team, add, after_commit, client_team, employee_team, merge, name_of, send


def allocations_path(allocation: EmployeeAllocation) -> str:
    return f"/employees/{allocation.employee_id}"


def allocation_team(db: Session, allocation: EmployeeAllocation) -> Team:
    employee = db.get(Employee, allocation.employee_id)
    if employee is None:
        raise ValueError(f"Allocation {allocation.id} has unknown employee {allocation.employee_id}")
    team = employee_team(db, employee)
    project = db.get(Project, allocation.project_id) if allocation.project_id else None
    if project is not None:
        add(team, project.manager_user_id, "Project Manager")
    add(team, allocation.renewal_owner_user_id, "Renewal Owner")
    merge(team, client_team(db, allocation.client_id))
    return team


def _label(db: Session, allocation: EmployeeAllocation) -> str:
    employee = db.get(Employee, allocation.employee_id)
    name = f"{employee.first_name} {employee.last_name}".strip() if employee is not None else allocation.employee_id
    project = db.get(Project, allocation.project_id) if allocation.project_id else None
    client = db.get(Client, allocation.client_id)
    where = project.name if project is not None else (client.company_name if client is not None else allocation.client_id)
    return f"{name} on {where}"


def _facts(allocation: EmployeeAllocation) -> str:
    facts = [f"Status: {allocation.status}", f"From {allocation.start_date}"]
    if allocation.end_date:
        facts.append(f"to {allocation.end_date}")
    if allocation.role:
        facts.append(f"Role: {allocation.role}")
    if allocation.utilization_pct is not None:
        facts.append(f"Utilization: {float(allocation.utilization_pct):g}%")
    return ". ".join(facts) + "."


def _send(db: Session, allocation: EmployeeAllocation, *, actor: Users, key: str, subject: str, opening: str,
          extra=None) -> int:
    return send(db, allocation_team(db, allocation), actor_id=actor.UserID, key=key, subject=subject,
                opening=opening, details=[_facts(allocation), extra], link_path=allocations_path(allocation),
                link_label="Open the employee")


@after_commit("allocations")
def notify_allocated(db: Session, allocation: EmployeeAllocation, *, actor: Users) -> int:
    label = _label(db, allocation)
    return _send(db, allocation, actor=actor, key=f"allocation-created-{allocation.id}",
                 subject=f"Allocated: {label}", opening=f"{name_of(actor)} allocated {label}.")


@after_commit("allocations")
def notify_allocation_ended(db: Session, allocation: EmployeeAllocation, *, actor: Users) -> int:
    label = _label(db, allocation)
    return _send(db, allocation, actor=actor, key=f"allocation-ended-{allocation.id}",
                 subject=f"Allocation ended: {label}", opening=f"{name_of(actor)} ended the allocation of {label}.")


def _change_text(change: AllocationChange) -> str:
    old = change.old_values or {}
    parts = [f"{field.replace('_', ' ')}: {old.get(field, '-')} -> {value}" for field, value in (change.new_values or {}).items()]
    text = "; ".join(parts) or "no field changes"
    return f"Change: {text}. Reason: {change.reason}."


@after_commit("allocations")
def notify_allocation_changed(db: Session, allocation: EmployeeAllocation, change: AllocationChange, *,
                              actor: Users) -> int:
    """An applied edit; one waiting for margin approval mails nobody (its approver has the task)."""
    if change.status != "APPLIED":
        return 0
    label = _label(db, allocation)
    return _send(db, allocation, actor=actor, key=f"allocation-change-{change.id}",
                 subject=f"Allocation changed: {label}", opening=f"{name_of(actor)} changed the allocation of {label}.",
                 extra=_change_text(change))


@after_commit("allocations")
def notify_margin_decision(db: Session, change: AllocationChange, *, actor: Users) -> int:
    allocation = db.get(EmployeeAllocation, change.allocation_id)
    label = _label(db, allocation)
    decision = "approved" if change.status == "APPLIED" else "rejected"
    team = allocation_team(db, allocation)
    add(team, change.changed_by_user_id, "Asked for the change")
    return send(db, team, actor_id=actor.UserID, key=f"allocation-change-decided-{change.id}",
                subject=f"Margin exception {decision}: {label}",
                opening=f"{name_of(actor)} {decision} the below-floor change to the allocation of {label}.",
                details=[_change_text(change),
                         f"Decision note: {change.decision_reason}" if change.decision_reason else None],
                link_path=allocations_path(allocation), link_label="Open the employee")
