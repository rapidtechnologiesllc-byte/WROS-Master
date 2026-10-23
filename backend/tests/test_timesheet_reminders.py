"""Missing-timesheet reminders (CEO 2026-10-22): a DRAFT or no timesheet on any allocation that
covered last week -> the employee is emailed (send_staff_email) and told in Flash; still missing
after TIMESHEET_NAG_ESCALATION_DAYS -> the approver; once per level, never silent."""
from datetime import datetime, timedelta

from app.models.employee import Employee
from app.models.timesheet_nag import TimesheetNagLog
from app.services import timesheet_nag_service as nag
from tests.test_core_certification import db, org  # noqa: F401 -- fixtures
from tests.test_timesheet_approval import LAST_MONDAY, emails, loop  # noqa: F401 -- fixtures


def test_missing_timesheet_reminds_the_employee_then_escalates_once(db, loop, emails):
    week = LAST_MONDAY
    assert loop.employee.id in {e.id for e in nag.scan_missing_timesheets(db, week_starting_date=week)}  # a DRAFT
    nag.trigger_timesheet_nag(db, loop.employee, week_starting_date=week)
    nag.trigger_timesheet_nag(db, loop.employee, week_starting_date=week)  # same day: nothing new
    to_employee = [e for e in emails if e["user_id"] == loop.login.UserID]
    assert len(to_employee) == 1 and "Timesheet missing" in to_employee[0]["subject"]
    later = datetime.utcnow() + timedelta(days=4)
    nag.trigger_timesheet_nag(db, loop.employee, week_starting_date=week, now=later)
    nag.trigger_timesheet_nag(db, loop.employee, week_starting_date=week, now=later + timedelta(days=1))
    to_manager = [e for e in emails if e["user_id"] == loop.manager.UserID]
    assert len(to_manager) == 1 and "still missing" in to_manager[0]["subject"].lower()
    assert db.query(TimesheetNagLog).filter_by(employee_id=loop.employee.id).one().escalation_level == 2


def test_an_ended_allocation_still_owes_its_last_week_and_a_submitted_week_is_resolved(db, loop, emails):
    loop.allocation.status, loop.allocation.end_date = "ENDED", LAST_MONDAY + timedelta(days=2)
    db.commit()
    assert loop.employee.id in {e.id for e in nag.scan_missing_timesheets(db, week_starting_date=LAST_MONDAY)}
    nag.trigger_timesheet_nag(db, loop.employee, week_starting_date=LAST_MONDAY)
    loop.sheet.status = "SUBMITTED"
    db.commit()
    assert nag.trigger_timesheet_nag(db, loop.employee, week_starting_date=LAST_MONDAY) is None
    assert db.query(TimesheetNagLog).filter_by(employee_id=loop.employee.id).one().resolved


def test_an_employee_without_a_login_goes_straight_to_the_approver(db, loop, emails):
    db.query(Employee).filter_by(id=loop.employee.id).update({"wros_user_id": None})
    db.commit()
    db.refresh(loop.employee)
    nag.trigger_timesheet_nag(db, loop.employee, week_starting_date=LAST_MONDAY)
    assert [e["user_id"] for e in emails] == [loop.manager.UserID]

