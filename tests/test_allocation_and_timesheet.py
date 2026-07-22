"""
Proves HRMS-0507's minimal allocate/end-allocation slice and
HRMS-0901/0902's timesheet submission + approval workflow (BR-01
60-hour cap, BR-02 4-week stale-submission guard, BR-03 one-per-
employee-per-allocation-per-week via UNIQUE, BR-04 bench employees
never get a timesheet; 0902's BR-02 rejected-returns-to-draft and
BR-03 approved-is-immutable).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.client import Client
from app.models.demand import Demand, DemandHistory
from app.models.employee import Employee, EmployeeEmploymentHistory
from app.models.employee_allocation import EmployeeAllocation
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.user import Users

from app.services.employee_allocation_service import (
    allocate_employee_to_project,
    end_allocation,
    BuddyProgramNotGraduated,
    EmployeeAlreadyAllocated,
)
from app.services.timesheet_service import (
    create_weekly_draft,
    upsert_entries,
    submit_timesheet,
    approve_timesheet,
    reject_timesheet,
    reopen_for_editing,
    bulk_approve,
    AllocationNotActive,
    InvalidTimesheetEntry,
    TimesheetNotEditable,
    InvalidTimesheetTransition,
    StaleTimesheetSubmission,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Client.__table__, Demand.__table__, DemandHistory.__table__,
        Employee.__table__, EmployeeEmploymentHistory.__table__, Users.__table__,
        EmployeeAllocation.__table__, Timesheet.__table__, TimesheetEntry.__table__,
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


@pytest.fixture()
def base_fixtures(db_session):
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

    employee = Employee(
        tenant_id=tenant.id, first_name="Sam", last_name="Lee", email="sam@blitzenx.com",
        joining_date=date(2025, 1, 1), status="BENCH",
    )
    db_session.add(employee)
    db_session.commit()

    return tenant, client, demand, employee


def _make_active_allocation(db, tenant, demand, employee):
    allocation = allocate_employee_to_project(
        db, tenant_id=tenant.id, employee=employee, demand=demand,
        start_date=date(2026, 1, 5),
    )
    db.commit()
    return allocation


# ---------------------------------------------------------------------------
# EmployeeAllocation lifecycle (HRMS-0507)
# ---------------------------------------------------------------------------

def test_allocate_moves_employee_to_allocated(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand)
    db_session.commit()
    assert employee.status == "ALLOCATED"


def test_allocate_already_allocated_raises(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    _make_active_allocation(db_session, tenant, demand, employee)

    with pytest.raises(EmployeeAlreadyAllocated):
        allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand)


# ---------------------------------------------------------------------------
# S-365/HRMS-0521 -- no client deployment while actively mid-Buddy-Program
# ---------------------------------------------------------------------------

def test_allocation_blocked_while_buddy_program_in_progress(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    employee.buddy_program_status = "IN_PROGRESS"
    db_session.add(employee)
    db_session.commit()

    with pytest.raises(BuddyProgramNotGraduated):
        allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand)


def test_allocation_blocked_while_buddy_program_extended(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    employee.buddy_program_status = "EXTENDED"
    db_session.add(employee)
    db_session.commit()

    with pytest.raises(BuddyProgramNotGraduated):
        allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand)


def test_allocation_allowed_once_graduated(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    employee.buddy_program_status = "GRADUATED"
    db_session.add(employee)
    db_session.commit()

    allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand)
    db_session.commit()
    assert employee.status == "ALLOCATED"


def test_allocation_allowed_when_never_enrolled_in_buddy_program(db_session, base_fixtures):
    """Scoping decision: NOT_STARTED (the model default) does not block --
    only IN_PROGRESS/EXTENDED do. See employee_allocation_service's own
    module-level note on why this isn't a blanket gate."""
    tenant, client, demand, employee = base_fixtures
    assert employee.buddy_program_status == "NOT_STARTED"

    allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand)
    db_session.commit()
    assert employee.status == "ALLOCATED"


def test_end_allocation_returns_employee_to_bench(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    allocation = _make_active_allocation(db_session, tenant, demand, employee)

    end_allocation(db_session, allocation, employee)
    db_session.commit()

    assert allocation.status == "ENDED"
    assert employee.status == "BENCH"


# ---------------------------------------------------------------------------
# create_weekly_draft (BR-04: bench employees don't get timesheets)
# ---------------------------------------------------------------------------

def test_create_weekly_draft_requires_active_allocation(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    allocation = _make_active_allocation(db_session, tenant, demand, employee)
    end_allocation(db_session, allocation, employee)
    db_session.commit()

    with pytest.raises(AllocationNotActive):
        create_weekly_draft(db_session, allocation, _monday_of(date(2026, 2, 2)), tenant_id=tenant.id)


def test_create_weekly_draft_requires_monday(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    allocation = _make_active_allocation(db_session, tenant, demand, employee)

    with pytest.raises(InvalidTimesheetEntry):
        create_weekly_draft(db_session, allocation, date(2026, 2, 3), tenant_id=tenant.id)  # a Tuesday


def test_create_weekly_draft_is_idempotent(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    allocation = _make_active_allocation(db_session, tenant, demand, employee)
    monday = _monday_of(date(2026, 2, 2))

    ts1 = create_weekly_draft(db_session, allocation, monday, tenant_id=tenant.id)
    db_session.commit()
    ts2 = create_weekly_draft(db_session, allocation, monday, tenant_id=tenant.id)
    db_session.commit()

    assert ts1.id == ts2.id


# ---------------------------------------------------------------------------
# upsert_entries (BR-01 60h cap, no future dates, BR-03 immutable once approved)
# ---------------------------------------------------------------------------

def _fresh_timesheet(db, tenant, demand, employee, week_offset_days=0):
    allocation = _make_active_allocation(db, tenant, demand, employee)
    monday = _monday_of(date.today()) - timedelta(days=week_offset_days)
    ts = create_weekly_draft(db, allocation, monday, tenant_id=tenant.id)
    db.commit()
    return ts


def test_upsert_entries_computes_totals(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    ts = _fresh_timesheet(db_session, tenant, demand, employee, week_offset_days=7)
    monday = ts.week_starting_date

    upsert_entries(db_session, ts, [
        {"entry_date": monday, "hours": 8, "entry_type": "BILLABLE"},
        {"entry_date": monday + timedelta(days=1), "hours": 8, "entry_type": "BILLABLE"},
        {"entry_date": monday + timedelta(days=2), "hours": 8, "entry_type": "NON_BILLABLE"},
    ])
    db_session.commit()

    assert float(ts.total_hours) == 24
    assert float(ts.billable_hours) == 16
    assert float(ts.non_billable_hours) == 8


def test_upsert_entries_rejects_future_date(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    ts = _fresh_timesheet(db_session, tenant, demand, employee)
    future = date.today() + timedelta(days=5)

    with pytest.raises(InvalidTimesheetEntry):
        upsert_entries(db_session, ts, [{"entry_date": future, "hours": 8, "entry_type": "BILLABLE"}])


def test_upsert_entries_rejects_over_60_hour_cap(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    ts = _fresh_timesheet(db_session, tenant, demand, employee, week_offset_days=7)
    monday = ts.week_starting_date

    entries = [{"entry_date": monday + timedelta(days=i), "hours": 13, "entry_type": "BILLABLE"} for i in range(5)]
    with pytest.raises(InvalidTimesheetEntry):
        upsert_entries(db_session, ts, entries)  # 65 hours


def test_upsert_entries_blocked_once_approved(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    ts = _fresh_timesheet(db_session, tenant, demand, employee, week_offset_days=7)
    monday = ts.week_starting_date
    upsert_entries(db_session, ts, [{"entry_date": monday, "hours": 8, "entry_type": "BILLABLE"}])
    submit_timesheet(db_session, ts)
    approve_timesheet(db_session, ts, approved_by="U-RM")
    db_session.commit()

    with pytest.raises(TimesheetNotEditable):
        upsert_entries(db_session, ts, [{"entry_date": monday, "hours": 4, "entry_type": "BILLABLE"}])


# ---------------------------------------------------------------------------
# submit_timesheet (BR-02 4-week lookback)
# ---------------------------------------------------------------------------

def test_submit_requires_at_least_one_entry(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    ts = _fresh_timesheet(db_session, tenant, demand, employee, week_offset_days=7)

    with pytest.raises(InvalidTimesheetEntry):
        submit_timesheet(db_session, ts)


def test_submit_stale_timesheet_rejected(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    ts = _fresh_timesheet(db_session, tenant, demand, employee, week_offset_days=42)  # 6 weeks back
    upsert_entries(db_session, ts, [{"entry_date": ts.week_starting_date, "hours": 8, "entry_type": "BILLABLE"}])

    with pytest.raises(StaleTimesheetSubmission):
        submit_timesheet(db_session, ts)


def test_submit_success(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    ts = _fresh_timesheet(db_session, tenant, demand, employee, week_offset_days=7)
    upsert_entries(db_session, ts, [{"entry_date": ts.week_starting_date, "hours": 8, "entry_type": "BILLABLE"}])

    submit_timesheet(db_session, ts)
    db_session.commit()

    assert ts.status == "SUBMITTED"
    assert ts.submitted_at is not None


def test_cannot_submit_twice(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    ts = _fresh_timesheet(db_session, tenant, demand, employee, week_offset_days=7)
    upsert_entries(db_session, ts, [{"entry_date": ts.week_starting_date, "hours": 8, "entry_type": "BILLABLE"}])
    submit_timesheet(db_session, ts)
    db_session.commit()

    with pytest.raises(InvalidTimesheetTransition):
        submit_timesheet(db_session, ts)


# ---------------------------------------------------------------------------
# Approval workflow (HRMS-0902)
# ---------------------------------------------------------------------------

def _submitted_timesheet(db, tenant, demand, employee):
    ts = _fresh_timesheet(db, tenant, demand, employee, week_offset_days=7)
    upsert_entries(db, ts, [{"entry_date": ts.week_starting_date, "hours": 8, "entry_type": "BILLABLE"}])
    submit_timesheet(db, ts)
    db.commit()
    return ts


def test_approve_requires_submitted_status(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    ts = _fresh_timesheet(db_session, tenant, demand, employee, week_offset_days=7)  # still DRAFT

    with pytest.raises(InvalidTimesheetTransition):
        approve_timesheet(db_session, ts, approved_by="U-RM")


def test_approve_success(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    ts = _submitted_timesheet(db_session, tenant, demand, employee)

    approve_timesheet(db_session, ts, approved_by="U-RM")
    db_session.commit()

    assert ts.status == "APPROVED"
    assert ts.approved_by == "U-RM"
    assert ts.approved_at is not None


def test_reject_requires_min_20_char_reason(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    ts = _submitted_timesheet(db_session, tenant, demand, employee)

    with pytest.raises(InvalidTimesheetEntry):
        reject_timesheet(db_session, ts, "too short")


def test_reject_and_reopen_for_editing(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    ts = _submitted_timesheet(db_session, tenant, demand, employee)

    reject_timesheet(db_session, ts, "Hours on Friday exceed the allocation's expected weekly hours.")
    db_session.commit()
    assert ts.status == "REJECTED"
    assert ts.rejection_reason is not None

    reopen_for_editing(db_session, ts)
    db_session.commit()
    assert ts.status == "DRAFT"
    assert ts.rejection_reason is not None  # preserved, not cleared


def test_reopen_requires_rejected_status(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    ts = _submitted_timesheet(db_session, tenant, demand, employee)

    with pytest.raises(InvalidTimesheetTransition):
        reopen_for_editing(db_session, ts)


def test_bulk_approve_mixed_results(db_session, base_fixtures):
    tenant, client, demand, employee = base_fixtures
    ts1 = _submitted_timesheet(db_session, tenant, demand, employee)

    employee2 = Employee(
        tenant_id=tenant.id, first_name="Ann", last_name="Ng", email="ann@blitzenx.com",
        joining_date=date(2025, 1, 1), status="BENCH",
    )
    db_session.add(employee2)
    db_session.commit()
    ts2 = _fresh_timesheet(db_session, tenant, demand, employee2, week_offset_days=7)  # left in DRAFT

    result = bulk_approve(db_session, [ts1, ts2], approved_by="U-RM")
    db_session.commit()

    assert result["approved"] == 1
    assert len(result["failed"]) == 1
    assert result["failed"][0]["id"] == ts2.id
    assert ts1.status == "APPROVED"
    assert ts2.status == "DRAFT"
