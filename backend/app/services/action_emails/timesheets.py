"""Timesheet emails beside the approval loop's own (timesheet_approval_service.send_notices mails the
approver on submit and the employee on approve / reject): a timesheet reopened for editing, and a
dispute raised or resolved on an approved timesheet. The people on a timesheet: the employee, their
reporting manager and BU head, whoever approved it, and for a dispute the client's team."""
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.timesheet import Timesheet
from app.models.timesheet_dispute import TimesheetDispute
from app.models.user import Users
from app.services.action_emails.core import Team, add, after_commit, client_team, employee_team, merge, name_of, send

TIMESHEETS_PATH = "/timesheets"


def timesheet_team(db: Session, timesheet: Timesheet, *, with_client: bool = False) -> Team:
    employee = db.get(Employee, timesheet.employee_id)
    if employee is None:
        raise ValueError(f"Timesheet {timesheet.id} has unknown employee {timesheet.employee_id}")
    team = employee_team(db, employee)
    add(team, timesheet.approved_by, "Approved it")
    if with_client and timesheet.allocation_id:
        allocation = db.get(EmployeeAllocation, timesheet.allocation_id)
        if allocation is not None:
            merge(team, client_team(db, allocation.client_id))
    return team


def _label(db: Session, timesheet: Timesheet) -> str:
    employee = db.get(Employee, timesheet.employee_id)
    name = f"{employee.first_name} {employee.last_name}".strip() if employee is not None else timesheet.employee_id
    return f"{name}, week of {timesheet.week_starting_date}"


@after_commit("timesheets")
def notify_reopened(db: Session, timesheet: Timesheet, *, actor: Users) -> int:
    """Call after the commit and a refresh: the reopen's updated_at keys the email, so each reopen
    (one per rejection) mails once."""
    label = _label(db, timesheet)
    return send(db, timesheet_team(db, timesheet), actor_id=actor.UserID,
                key=f"timesheet-reopened-{timesheet.id}-{timesheet.updated_at:%Y%m%dT%H%M%S}",
                subject=f"Timesheet reopened: {label}",
                opening=f"{name_of(actor)} reopened the timesheet {label} for editing.",
                details=["Change the entries and submit it again for approval."],
                link_path="/my-timesheet", link_label="Open My Timesheet")


@after_commit("timesheets")
def notify_dispute_raised(db: Session, dispute: TimesheetDispute, *, actor: Users) -> int:
    timesheet = db.get(Timesheet, dispute.timesheet_id)
    label = _label(db, timesheet)
    hours = f" Disputed hours: {float(dispute.disputed_hours):g} (was {float(dispute.original_hours):g})." \
        if dispute.disputed_hours is not None else ""
    return send(db, timesheet_team(db, timesheet, with_client=True), actor_id=actor.UserID,
                key=f"timesheet-dispute-raised-{dispute.id}", subject=f"Timesheet disputed: {label}",
                opening=f"{name_of(actor)} raised a dispute ({dispute.raised_by.lower()}) on the timesheet {label}.",
                details=[f"Reason: {dispute.reason}.{hours}"], link_path=TIMESHEETS_PATH, link_label="Open Timesheets")


@after_commit("timesheets")
def notify_dispute_resolved(db: Session, dispute: TimesheetDispute, *, actor: Users) -> int:
    timesheet = db.get(Timesheet, dispute.timesheet_id)
    label = _label(db, timesheet)
    team = timesheet_team(db, timesheet, with_client=True)
    add(team, dispute.raised_by_user_id, "Raised the dispute")
    adjusted = f" Agreed hours: {float(dispute.adjusted_hours):g}." if dispute.adjusted_hours is not None else ""
    return send(db, team, actor_id=actor.UserID, key=f"timesheet-dispute-resolved-{dispute.id}",
                subject=f"Timesheet dispute {dispute.status.lower()}: {label}",
                opening=f"{name_of(actor)} resolved the dispute on the timesheet {label}: {dispute.status.lower()}.",
                details=[f"Notes: {dispute.resolution_notes}.{adjusted}" if dispute.resolution_notes else adjusted],
                link_path=TIMESHEETS_PATH, link_label="Open Timesheets")
