"""Employee emails: a new employee, a new reporting manager, an employment change (notice, exit,
leave), marked on the bench, and an escalation raised or resolved. The people on an employee: the
employee (their login), their reporting manager and their BU head. An escalation is about the
employee, so it goes to their manager and BU head (and whoever raised it), not to the employee."""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_escalation import EmployeeEscalation
from app.models.user import Users
from app.services.action_emails.core import Team, add, after_commit, employee_team, name_of, send


def employee_path(employee: Employee) -> str:
    return f"/employees/{employee.id}"


def _name(employee: Employee) -> str:
    return f"{employee.first_name} {employee.last_name}".strip()


def _send(db: Session, employee: Employee, team: Team, *, actor: Users, key: str, subject: str, opening: str,
          details=None) -> int:
    return send(db, team, actor_id=actor.UserID, key=key, subject=subject, opening=opening, details=details,
                link_path=employee_path(employee), link_label="Open the employee")


@after_commit("employees")
def notify_employee_created(db: Session, employee: Employee, *, actor: Users) -> int:
    """To their manager and BU head; the employee themself gets the import path's activation email."""
    team = employee_team(db, employee)
    team.pop(employee.wros_user_id, None)
    return _send(db, employee, team, actor=actor, key=f"employee-created-{employee.id}",
                 subject=f"New employee: {_name(employee)}", opening=f"{name_of(actor)} added {_name(employee)} as an employee.",
                 details=[f"Status: {employee.status}."])


@after_commit("employees")
def notify_manager_changed(db: Session, employee: Employee, *, actor: Users, previous_manager: Optional[str]) -> int:
    team = employee_team(db, employee)
    add(team, previous_manager, "Previous Reporting Manager")
    manager = next((uid for uid, roles in team.items() if "Reporting Manager" in roles), None)
    if manager is None or manager == previous_manager:
        return 0
    return _send(db, employee, team, actor=actor, key=f"employee-manager-{employee.id}-{manager}",
                 subject=f"New reporting manager for {_name(employee)}",
                 opening=f"{name_of(actor)} set {_name(employee)} to report to {name_of(db.get(Users, manager)) or manager}.",
                 details=["Timesheet and expense approvals follow the new reporting line."])


@after_commit("employees")
def notify_employment_changed(db: Session, employee: Employee, action: str, *, actor: Users,
                              effective_date: Optional[date], reason: str) -> int:
    what = action.replace("_", " ").lower()
    when = f" effective {effective_date}" if effective_date else ""
    return _send(db, employee, employee_team(db, employee), actor=actor,
                 key=f"employee-employment-{employee.id}-{action}-{effective_date or 'now'}",
                 subject=f"Employment change ({what}): {_name(employee)}",
                 opening=f"{name_of(actor)} recorded {what} for {_name(employee)}{when}.",
                 details=[f"Reason: {reason}", f"Status now: {employee.status}."])


@after_commit("employees")
def notify_marked_bench(db: Session, employee: Employee, *, actor: Users, reason: str) -> int:
    return _send(db, employee, employee_team(db, employee), actor=actor,
                 key=f"employee-bench-{employee.id}-{date.today():%Y%m%d}",
                 subject=f"On the bench: {_name(employee)}", opening=f"{name_of(actor)} marked {_name(employee)} as on the bench.",
                 details=[f"Reason: {reason}"])


def _escalation_team(db: Session, employee: Employee, row: EmployeeEscalation) -> Team:
    team = employee_team(db, employee)
    team.pop(employee.wros_user_id, None)
    add(team, row.raised_by_user_id, "Raised the escalation")
    return team


@after_commit("employees")
def notify_escalation_raised(db: Session, row: EmployeeEscalation, *, actor: Users) -> int:
    employee = db.get(Employee, row.employee_id)
    return _send(db, employee, _escalation_team(db, employee, row), actor=actor, key=f"employee-escalation-{row.id}",
                 subject=f"Escalation ({row.severity}) on {_name(employee)}",
                 opening=f"{name_of(actor)} raised an escalation on {_name(employee)}.",
                 details=[f"Reason: {row.reason}",
                          "While it is open they cannot be submitted or deployed to a client; a Director resolves it."])


@after_commit("employees")
def notify_escalation_resolved(db: Session, row: EmployeeEscalation, *, actor: Users) -> int:
    employee = db.get(Employee, row.employee_id)
    return _send(db, employee, _escalation_team(db, employee, row), actor=actor,
                 key=f"employee-escalation-resolved-{row.id}", subject=f"Escalation resolved on {_name(employee)}",
                 opening=f"{name_of(actor)} resolved the escalation on {_name(employee)}.",
                 details=[f"Resolution: {row.resolution_note}"])
