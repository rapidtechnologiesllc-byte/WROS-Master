"""
Proves HRMS-0904 (Timesheet Dispute Resolution -- BR-01 original
timesheet never mutated, BR-02 has_open_dispute hook) and HRMS-0905
(Timesheet Analytics & Compliance -- BR-01 on-time/late/missing
classification, BR-02 Phase 2 hours-based utilization).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.client import Client
from app.models.demand import Demand, DemandHistory
from app.models.employee import Employee, EmployeeEmploymentHistory
from app.models.employee_allocation import EmployeeAllocation
from app.models.resource_management import AllocationConflictLogEntry, BenchPoolEntry, EmployeeUtilizationMetric
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.timesheet_dispute import TimesheetDispute
from app.models.user import Users

from app.services.employee_allocation_service import allocate_employee_to_project
from app.services.timesheet_service import create_weekly_draft, upsert_entries, submit_timesheet, approve_timesheet
from app.services.timesheet_dispute_service import (
    raise_dispute,
    resolve_dispute,
    has_open_dispute,
    DisputeValidationError,
    InvalidDisputeTransition,
)
from app.services.timesheet_analytics_service import (
    classify_submission_timeliness,
    get_timesheet_compliance_report,
    calculate_utilization_pct_phase2,
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
        TimesheetDispute.__table__,
        BenchPoolEntry.__table__, EmployeeUtilizationMetric.__table__, AllocationConflictLogEntry.__table__,
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
def approved_timesheet(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    client = Client(tenant_id=tenant.id, company_name="Acme Insurance")
    db_session.add(client)
    db_session.commit()
    demand = Demand(
        tenant_id=tenant.id, client_id=client.id, job_title="Sr. Guidewire Developer",
        required_skills="[\"Guidewire\"]", min_experience_years=5.0,
        work_location="REMOTE", status="OPEN",
    )
    db_session.add(demand)
    db_session.commit()
    employee = Employee(
        tenant_id=tenant.id, first_name="Sam", last_name="Lee", email="sam@blitzenx.com",
        joining_date=date(2025, 1, 1), status="BENCH",
    )
    db_session.add(employee)
    db_session.commit()
    allocation = allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand)
    db_session.commit()

    monday = _monday_of(date.today()) - timedelta(days=7)
    ts = create_weekly_draft(db_session, allocation, monday, tenant_id=tenant.id)
    db_session.commit()
    upsert_entries(db_session, ts, [
        {"entry_date": monday + timedelta(days=i), "hours": 8, "entry_type": "BILLABLE"} for i in range(5)
    ])
    submit_timesheet(db_session, ts)
    approve_timesheet(db_session, ts, approved_by="U-RM")
    db_session.commit()

    return tenant, client, employee, ts


# ---------------------------------------------------------------------------
# HRMS-0904: raise_dispute
# ---------------------------------------------------------------------------

def test_raise_dispute_requires_approved_timesheet(db_session, approved_timesheet):
    tenant, client, employee, ts = approved_timesheet
    ts.status = "DRAFT"
    db_session.commit()

    with pytest.raises(DisputeValidationError):
        raise_dispute(db_session, ts, raised_by="CLIENT", reason="x" * 60)


def test_raise_dispute_requires_min_50_char_reason(db_session, approved_timesheet):
    tenant, client, employee, ts = approved_timesheet
    with pytest.raises(DisputeValidationError):
        raise_dispute(db_session, ts, raised_by="CLIENT", reason="too short")


def test_raise_dispute_snapshots_original_hours(db_session, approved_timesheet):
    tenant, client, employee, ts = approved_timesheet
    dispute = raise_dispute(
        db_session, ts, raised_by="CLIENT", reason="Client records show only 32 hours worked, not 40 as logged." + "x" * 20,
    )
    db_session.commit()

    assert dispute.status == "OPEN"
    assert float(dispute.original_hours) == float(ts.total_hours)


# ---------------------------------------------------------------------------
# HRMS-0904: resolve_dispute -- BR-01 never mutates original timesheet
# ---------------------------------------------------------------------------

def test_resolve_adjusted_requires_adjusted_hours(db_session, approved_timesheet):
    tenant, client, employee, ts = approved_timesheet
    dispute = raise_dispute(db_session, ts, raised_by="CLIENT", reason="x" * 60)
    db_session.commit()

    with pytest.raises(DisputeValidationError):
        resolve_dispute(db_session, dispute, resolution="ADJUSTED", resolved_by="U-RM", resolution_notes="ok")


def test_resolve_adjusted_never_mutates_original_timesheet(db_session, approved_timesheet):
    tenant, client, employee, ts = approved_timesheet
    original_total_hours = ts.total_hours
    dispute = raise_dispute(db_session, ts, raised_by="CLIENT", reason="x" * 60)
    db_session.commit()

    resolve_dispute(
        db_session, dispute, resolution="ADJUSTED", resolved_by="U-RM",
        resolution_notes="Confirmed with client -- 32 hours actually worked.", adjusted_hours=32,
    )
    db_session.commit()

    assert dispute.status == "RESOLVED_ADJUSTED"
    assert float(dispute.adjusted_hours) == 32
    # BR-01: original timesheet total_hours untouched.
    assert ts.total_hours == original_total_hours


def test_resolve_confirmed(db_session, approved_timesheet):
    tenant, client, employee, ts = approved_timesheet
    dispute = raise_dispute(db_session, ts, raised_by="RM", reason="x" * 60)
    db_session.commit()

    resolve_dispute(db_session, dispute, resolution="CONFIRMED", resolved_by="U-RM", resolution_notes="Hours confirmed correct as logged.")
    db_session.commit()

    assert dispute.status == "RESOLVED_CONFIRMED"
    assert dispute.adjusted_hours is None


def test_resolve_rejects_invalid_resolution(db_session, approved_timesheet):
    tenant, client, employee, ts = approved_timesheet
    dispute = raise_dispute(db_session, ts, raised_by="RM", reason="x" * 60)
    db_session.commit()

    with pytest.raises(ValueError):
        resolve_dispute(db_session, dispute, resolution="BOGUS", resolved_by="U-RM", resolution_notes="x")


def test_cannot_resolve_already_resolved_dispute(db_session, approved_timesheet):
    tenant, client, employee, ts = approved_timesheet
    dispute = raise_dispute(db_session, ts, raised_by="RM", reason="x" * 60)
    db_session.commit()
    resolve_dispute(db_session, dispute, resolution="CONFIRMED", resolved_by="U-RM", resolution_notes="ok" * 10)
    db_session.commit()

    with pytest.raises(InvalidDisputeTransition):
        resolve_dispute(db_session, dispute, resolution="CONFIRMED", resolved_by="U-RM", resolution_notes="again" * 10)


# ---------------------------------------------------------------------------
# HRMS-0904 BR-02: has_open_dispute hook
# ---------------------------------------------------------------------------

def test_has_open_dispute_true_when_open(db_session, approved_timesheet):
    tenant, client, employee, ts = approved_timesheet
    raise_dispute(db_session, ts, raised_by="RM", reason="x" * 60)
    db_session.commit()
    assert has_open_dispute(db_session, ts) is True


def test_has_open_dispute_false_once_resolved(db_session, approved_timesheet):
    tenant, client, employee, ts = approved_timesheet
    dispute = raise_dispute(db_session, ts, raised_by="RM", reason="x" * 60)
    db_session.commit()
    resolve_dispute(db_session, dispute, resolution="CONFIRMED", resolved_by="U-RM", resolution_notes="ok" * 10)
    db_session.commit()
    assert has_open_dispute(db_session, ts) is False


# ---------------------------------------------------------------------------
# HRMS-0905 BR-01: submission timeliness classification
# ---------------------------------------------------------------------------

def test_classify_on_time():
    ts = Timesheet(week_starting_date=date(2026, 1, 13), submitted_at=datetime(2026, 1, 20, 8, 0))
    assert classify_submission_timeliness(ts) == "ON_TIME"


def test_classify_late():
    ts = Timesheet(week_starting_date=date(2026, 1, 13), submitted_at=datetime(2026, 1, 20, 10, 0))
    assert classify_submission_timeliness(ts) == "LATE"


def test_classify_missing():
    ts = Timesheet(week_starting_date=date(2026, 1, 13), submitted_at=None)
    now = datetime(2026, 1, 23, 0, 0)  # after Jan 22 EOD
    assert classify_submission_timeliness(ts, now=now) == "MISSING"


def test_classify_not_yet_due():
    ts = Timesheet(week_starting_date=date(2026, 1, 13), submitted_at=None)
    now = datetime(2026, 1, 21, 0, 0)  # before Jan 22 EOD
    assert classify_submission_timeliness(ts, now=now) == "NOT_YET_DUE"


# ---------------------------------------------------------------------------
# HRMS-0905: compliance report + Phase 2 utilization
# ---------------------------------------------------------------------------

def test_compliance_report_counts_and_rates(db_session, approved_timesheet):
    tenant, client, employee, ts = approved_timesheet
    report = get_timesheet_compliance_report(
        db_session, tenant_id=tenant.id, date_from=date(2020, 1, 1), date_to=date(2030, 1, 1),
    )
    assert report["submission_rate_pct"] == 100.0
    assert employee.id in report["by_employee"]


def test_utilization_phase2_none_without_approved_timesheets(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    result = calculate_utilization_pct_phase2(db_session, "no-such-employee", date(2020, 1, 1), date(2030, 1, 1))
    assert result is None


def test_utilization_phase2_computed_from_billable_hours(db_session, approved_timesheet):
    tenant, client, employee, ts = approved_timesheet
    result = calculate_utilization_pct_phase2(db_session, employee.id, date(2020, 1, 1), date(2030, 1, 1))
    # 40 billable hours / (1 week * 40) * 100 = 100%
    assert result == 100.0
