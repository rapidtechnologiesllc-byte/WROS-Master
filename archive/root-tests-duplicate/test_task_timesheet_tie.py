"""
Task<->Timesheet tie backlog item, 2026-08-05
(wros_task_numbering_s434_backlog): allocation_id is now nullable on
Timesheet -- internal Task work (no client allocation) uses task_id
instead. Real architecture decision from Avinash: nullable
allocation_id + task_id, ck_timesheet_allocation_or_task enforces
exactly one of the two is always set. Throwaway SQLite -- never the
real database.
"""
import os
import tempfile
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.timesheet_anomaly import TimesheetAnomalyFlag
from app.models.user import Users

from app.services.timesheet_anomaly_service import scan_timesheet_anomalies
from app.services.timesheet_service import (
    InvalidTimesheetEntry,
    create_weekly_draft_for_task,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, Employee.__table__,
        EmployeeAllocation.__table__, Task.__table__,
        Timesheet.__table__, TimesheetEntry.__table__, TimesheetAnomalyFlag.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _make_employee(db, tenant_id, user_id="U-EMP", wros_user_id="U-EMP"):
    if wros_user_id:
        db.add(Users(UserID=wros_user_id, UserRole="employee", UserEmail=f"{wros_user_id}@blitzenx.com", UserPassword="h"))
        db.commit()
    employee = Employee(
        tenant_id=tenant_id, first_name="Sam", last_name="Lee", email="sam@blitzenx.com",
        joining_date=date(2025, 1, 1), status="ACTIVE", wros_user_id=wros_user_id,
    )
    db.add(employee)
    db.commit()
    return employee


def _make_task(db, assigned_to_user_id="U-EMP"):
    task = Task(title="Submit Q3 compliance report", priority="MEDIUM", assigned_to_user_id=assigned_to_user_id)
    db.add(task)
    db.commit()
    return task


def test_create_weekly_draft_for_task_sets_task_id_not_allocation_id(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    employee = _make_employee(db_session, tenant.id)
    task = _make_task(db_session)

    monday = _monday_of(date.today())
    ts = create_weekly_draft_for_task(db_session, task, employee.id, monday, tenant_id=tenant.id)
    db_session.commit()

    assert ts.task_id == task.id
    assert ts.allocation_id is None


def test_create_weekly_draft_for_task_is_idempotent(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    employee = _make_employee(db_session, tenant.id)
    task = _make_task(db_session)
    monday = _monday_of(date.today())

    first = create_weekly_draft_for_task(db_session, task, employee.id, monday, tenant_id=tenant.id)
    db_session.commit()
    second = create_weekly_draft_for_task(db_session, task, employee.id, monday, tenant_id=tenant.id)
    db_session.commit()

    assert first.id == second.id
    assert db_session.query(Timesheet).count() == 1


def test_create_weekly_draft_for_task_rejects_non_monday(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    employee = _make_employee(db_session, tenant.id)
    task = _make_task(db_session)

    not_monday = date.today() if date.today().weekday() != 0 else date.today() + timedelta(days=1)
    with pytest.raises(InvalidTimesheetEntry):
        create_weekly_draft_for_task(db_session, task, employee.id, not_monday, tenant_id=tenant.id)


def test_timesheet_requires_allocation_or_task(db_session):
    """ck_timesheet_allocation_or_task -- a real structural invariant,
    not just a service-layer suggestion."""
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    employee = _make_employee(db_session, tenant.id)

    orphan = Timesheet(
        tenant_id=tenant.id, employee_id=employee.id,
        week_starting_date=_monday_of(date.today()),
        total_hours=0, billable_hours=0, non_billable_hours=0,
    )
    db_session.add(orphan)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_scan_flags_unlinked_task_when_task_deleted(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    employee = _make_employee(db_session, tenant.id)
    task = _make_task(db_session)
    ts = create_weekly_draft_for_task(db_session, task, employee.id, _monday_of(date.today()), tenant_id=tenant.id)
    db_session.commit()
    db_session.add(TimesheetEntry(timesheet_id=ts.id, entry_date=date.today(), hours=8, entry_type="NON_BILLABLE"))
    db_session.commit()

    db_session.query(Task).filter(Task.id == task.id).delete()
    db_session.commit()

    flags = scan_timesheet_anomalies(db_session, ts)
    db_session.commit()
    assert any(f.anomaly_type == "UNLINKED_TASK" for f in flags)


def test_scan_flags_unlinked_task_when_assigned_to_someone_else(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    employee = _make_employee(db_session, tenant.id, wros_user_id="U-EMP")
    task = _make_task(db_session, assigned_to_user_id="U-SOMEONE-ELSE")
    ts = create_weekly_draft_for_task(db_session, task, employee.id, _monday_of(date.today()), tenant_id=tenant.id)
    db_session.commit()
    db_session.add(TimesheetEntry(timesheet_id=ts.id, entry_date=date.today(), hours=8, entry_type="NON_BILLABLE"))
    db_session.commit()

    flags = scan_timesheet_anomalies(db_session, ts)
    db_session.commit()
    assert any(f.anomaly_type == "UNLINKED_TASK" for f in flags)


def test_scan_does_not_flag_correctly_assigned_task(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    employee = _make_employee(db_session, tenant.id, wros_user_id="U-EMP")
    task = _make_task(db_session, assigned_to_user_id="U-EMP")
    ts = create_weekly_draft_for_task(db_session, task, employee.id, _monday_of(date.today()), tenant_id=tenant.id)
    db_session.commit()
    db_session.add(TimesheetEntry(timesheet_id=ts.id, entry_date=date.today(), hours=8, entry_type="NON_BILLABLE"))
    db_session.commit()

    flags = scan_timesheet_anomalies(db_session, ts)
    db_session.commit()
    assert not any(f.anomaly_type == "UNLINKED_TASK" for f in flags)


def test_scan_never_flags_unlinked_task_on_allocation_backed_timesheet(db_session):
    """The check is entirely out of scope for allocation-backed
    timesheets -- an allocation timesheet has no task_id at all."""
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    employee = _make_employee(db_session, tenant.id)

    allocation = EmployeeAllocation(
        tenant_id=tenant.id, employee_id=employee.id, demand_id="D-1", client_id="C-1",
        status="ACTIVE", start_date=date(2026, 1, 1),
    )
    db_session.add(allocation)
    db_session.commit()

    ts = Timesheet(
        tenant_id=tenant.id, employee_id=employee.id, allocation_id=allocation.id,
        week_starting_date=_monday_of(date.today()),
        total_hours=8, billable_hours=8, non_billable_hours=0,
    )
    db_session.add(ts)
    db_session.commit()
    db_session.add(TimesheetEntry(timesheet_id=ts.id, entry_date=date.today(), hours=8, entry_type="BILLABLE"))
    db_session.commit()

    flags = scan_timesheet_anomalies(db_session, ts)
    db_session.commit()
    assert not any(f.anomaly_type == "UNLINKED_TASK" for f in flags)
