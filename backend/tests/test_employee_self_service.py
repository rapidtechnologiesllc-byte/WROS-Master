"""
Employee self-service timesheet -- real ownership boundary the
existing HR-operated timesheet engine never had.

Proves: every function resolves the CALLER's own Employee record and
only ever touches THEIR OWN allocations/timesheets -- another
employee's allocation_id/timesheet_id is rejected, not silently
served. No linked Employee record is a real, honest 404, not a crash.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.client import Client
from app.models.demand import Demand, DemandHistory
from app.models.employee import Employee, EmployeeEmploymentHistory
from app.models.employee_allocation import EmployeeAllocation
from app.models.resource_management import (
    AllocationConflictLogEntry, BenchPeriod, BenchPoolEntry, EmployeeUtilizationMetric,
)
from app.models.tenant import Tenant
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.user import Users

import app.services.employee_self_service as svc
from app.services.employee_allocation_service import allocate_employee_to_project


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Client.__table__, Demand.__table__, DemandHistory.__table__,
        Employee.__table__, EmployeeEmploymentHistory.__table__, Users.__table__,
        EmployeeAllocation.__table__, Timesheet.__table__, TimesheetEntry.__table__,
        BenchPoolEntry.__table__, BenchPeriod.__table__, EmployeeUtilizationMetric.__table__, AllocationConflictLogEntry.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def seeded(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    client = Client(tenant_id=tenant.id, company_name="Acme Insurance")
    db_session.add(client)
    db_session.commit()

    demand = Demand(
        tenant_id=tenant.id, client_id=client.id, job_title="Sr. Guidewire Developer",
        required_skills="[\"Guidewire\"]", min_experience_years=5.0,
        work_location="REMOTE", status="OPEN", billing_rate_usd_cents=15000,
    )
    db_session.add(demand)
    db_session.commit()

    user = Users(UserID="U-EMP1", UserRole="Employee", UserName="Sam", UserEmail="sam@blitzenx.com", UserPassword="h")
    other_user = Users(UserID="U-EMP2", UserRole="Employee", UserName="Other", UserEmail="other@blitzenx.com", UserPassword="h")
    db_session.add_all([user, other_user])
    db_session.commit()

    employee = Employee(
        tenant_id=tenant.id, first_name="Sam", last_name="Lee", email="sam@blitzenx.com",
        joining_date=date(2025, 1, 1), status="BENCH", wros_user_id="U-EMP1",
    )
    other_employee = Employee(
        tenant_id=tenant.id, first_name="Other", last_name="Person", email="other@blitzenx.com",
        joining_date=date(2025, 1, 1), status="BENCH", wros_user_id="U-EMP2",
    )
    db_session.add_all([employee, other_employee])
    db_session.commit()

    allocation = allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand, start_date=date(2026, 1, 5))
    db_session.commit()

    return {"tenant": tenant, "user": user, "other_user": other_user, "employee": employee, "other_employee": other_employee, "allocation": allocation}


def test_resolve_current_employee_finds_own_record(db_session, seeded):
    employee = svc.resolve_current_employee(db_session, seeded["user"])
    assert employee.id == seeded["employee"].id


def test_resolve_current_employee_raises_when_unlinked(db_session, seeded):
    unlinked = Users(UserID="U-NOBODY", UserRole="Employee", UserName="Nobody", UserEmail="nobody@blitzenx.com", UserPassword="h")
    db_session.add(unlinked)
    db_session.commit()

    with pytest.raises(svc.NoLinkedEmployeeRecord):
        svc.resolve_current_employee(db_session, unlinked)


def test_get_my_active_allocations_returns_only_own(db_session, seeded):
    allocations = svc.get_my_active_allocations(db_session, seeded["employee"])
    assert len(allocations) == 1
    assert allocations[0].id == seeded["allocation"].id

    other_allocations = svc.get_my_active_allocations(db_session, seeded["other_employee"])
    assert other_allocations == []


def test_start_current_week_timesheet_is_idempotent(db_session, seeded):
    fixed_today = date(2026, 8, 4)  # a Tuesday
    t1 = svc.get_or_start_my_current_week_timesheet(db_session, seeded["employee"], seeded["allocation"].id, today=fixed_today)
    t2 = svc.get_or_start_my_current_week_timesheet(db_session, seeded["employee"], seeded["allocation"].id, today=fixed_today)
    assert t1.id == t2.id
    assert t1.week_starting_date == date(2026, 8, 3)  # the Monday of that week


def test_cannot_start_timesheet_for_someone_elses_allocation(db_session, seeded):
    with pytest.raises(svc.NotYourAllocation):
        svc.get_or_start_my_current_week_timesheet(db_session, seeded["other_employee"], seeded["allocation"].id)


def test_submit_my_entries_logs_real_hours(db_session, seeded):
    fixed_today = date(2026, 8, 4)
    timesheet = svc.get_or_start_my_current_week_timesheet(db_session, seeded["employee"], seeded["allocation"].id, today=fixed_today)

    updated = svc.submit_my_entries(db_session, seeded["employee"], timesheet.id, [
        {"entry_date": date(2026, 8, 3), "hours": 8, "entry_type": "BILLABLE"},
        {"entry_date": date(2026, 8, 4), "hours": 7.5, "entry_type": "BILLABLE"},
    ])
    assert float(updated.total_hours) == 15.5


def test_cannot_log_hours_against_someone_elses_timesheet(db_session, seeded):
    fixed_today = date(2026, 8, 4)
    timesheet = svc.get_or_start_my_current_week_timesheet(db_session, seeded["employee"], seeded["allocation"].id, today=fixed_today)

    with pytest.raises(svc.NotYourTimesheet):
        svc.submit_my_entries(db_session, seeded["other_employee"], timesheet.id, [
            {"entry_date": date(2026, 8, 3), "hours": 8},
        ])


def test_submit_my_timesheet_transitions_to_submitted(db_session, seeded):
    fixed_today = date(2026, 8, 4)
    timesheet = svc.get_or_start_my_current_week_timesheet(db_session, seeded["employee"], seeded["allocation"].id, today=fixed_today)
    svc.submit_my_entries(db_session, seeded["employee"], timesheet.id, [{"entry_date": date(2026, 8, 3), "hours": 8}])

    submitted = svc.submit_my_timesheet(db_session, seeded["employee"], timesheet.id)
    assert submitted.status == "SUBMITTED"


def test_my_timesheet_history_returns_only_own(db_session, seeded):
    fixed_today = date(2026, 8, 4)
    svc.get_or_start_my_current_week_timesheet(db_session, seeded["employee"], seeded["allocation"].id, today=fixed_today)

    history = svc.get_my_timesheet_history(db_session, seeded["employee"])
    assert len(history) == 1

    other_history = svc.get_my_timesheet_history(db_session, seeded["other_employee"])
    assert other_history == []
