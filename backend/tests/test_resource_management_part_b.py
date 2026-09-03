"""
Phase 4 Part B -- bench_pool lifecycle, utilization metrics, the
import logging
allocation-conflict audit log, and the Staffing Eligibility Engine.

Throwaway SQLite -- never the real database.
"""
import json
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
    AllocationConflictLogEntry,
    BenchPeriod,
    BenchPoolEntry,
    EmployeeUtilizationMetric,
)
from app.models.tenant import Tenant
from app.models.timesheet import Timesheet, TimesheetEntry

from app.services.employee_allocation_service import (
    AllocationOverCapacity,
    allocate_employee_to_project,
    end_allocation,
)
from app.services.resource_management_service import (
    check_bench_aging_alerts,
    get_bench_duration_days,
    get_bench_period_history,
    get_current_bench_pool,
    is_staffing_eligible,
    log_allocation_conflict,
    mark_employee_on_bench,
    record_weekly_utilization_metric,
    remove_employee_from_bench,
)

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Client.__table__, Demand.__table__, DemandHistory.__table__,
        Employee.__table__, EmployeeEmploymentHistory.__table__,
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
def fixtures(db_session):
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
        joining_date=date(2025, 1, 1), status="BENCH", base_salary_usd_cents=900000,
        current_skills='["Guidewire", "PolicyCenter"]',
    )
    db_session.add(employee)
    db_session.commit()

    return tenant, client, demand, employee

# ---------------------------------------------------------------------------
# Bench pool lifecycle -- wired through allocate/end_allocation
# ---------------------------------------------------------------------------

def test_mark_employee_on_bench_is_idempotent(db_session, fixtures):
    _, _, _, employee = fixtures
    first = mark_employee_on_bench(db_session, employee)
    db_session.commit()
    second = mark_employee_on_bench(db_session, employee)

    assert first.id == second.id
    assert db_session.query(BenchPoolEntry).count() == 1

def test_mark_employee_on_bench_captures_skills_and_cost(db_session, fixtures):
    _, _, _, employee = fixtures
    entry = mark_employee_on_bench(db_session, employee)

    assert entry.skill_tags == '["Guidewire", "PolicyCenter"]'
    assert entry.bench_cost_usd_cents == round(900000 / 30)

def test_end_allocation_creates_bench_pool_entry(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    allocation = allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand)
    db_session.commit()
    assert db_session.query(BenchPoolEntry).count() == 0  # removed on allocation

    end_allocation(db_session, allocation, employee)
    db_session.commit()

    assert db_session.query(BenchPoolEntry).filter(BenchPoolEntry.employee_id == employee.id).count() == 1

def test_mark_employee_on_bench_opens_one_history_period(db_session, fixtures):
    _, _, _, employee = fixtures
    mark_employee_on_bench(db_session, employee, reason="NEWLY_JOINED")
    db_session.commit()
    mark_employee_on_bench(db_session, employee, reason="NEWLY_JOINED")  # idempotent, no second period
    db_session.commit()

    periods = get_bench_period_history(db_session, employee.id)
    assert len(periods) == 1
    assert periods[0].bench_end_date is None
    assert periods[0].reason_for_bench == "NEWLY_JOINED"

def test_mark_employee_on_bench_rejects_invalid_reason(db_session, fixtures):
    _, _, _, employee = fixtures
    with pytest.raises(ValueError):
        mark_employee_on_bench(db_session, employee, reason="NOT_A_REAL_REASON")

def test_remove_from_bench_closes_the_open_period_and_computes_cost(db_session, fixtures):
    _, _, _, employee = fixtures
    mark_employee_on_bench(db_session, employee)
    db_session.commit()

    period = get_bench_period_history(db_session, employee.id)[0]
    period.bench_start_date = date.today() - timedelta(days=10)
    db_session.commit()

    remove_employee_from_bench(db_session, employee)
    db_session.commit()

    periods = get_bench_period_history(db_session, employee.id)
    assert len(periods) == 1
    assert periods[0].bench_end_date == date.today()
    assert periods[0].bench_cost_usd_cents == round(900000 / 30 * 10)

def test_bench_period_history_survives_multiple_stints(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    mark_employee_on_bench(db_session, employee, reason="NEWLY_JOINED")
    db_session.commit()
    remove_employee_from_bench(db_session, employee)
    db_session.commit()

    mark_employee_on_bench(db_session, employee, reason="PROJECT_ENDED")
    db_session.commit()

    periods = get_bench_period_history(db_session, employee.id)
    assert len(periods) == 2
    closed = [p for p in periods if p.bench_end_date is not None]
    open_ = [p for p in periods if p.bench_end_date is None]
    assert len(closed) == 1 and len(open_) == 1
    assert open_[0].reason_for_bench == "PROJECT_ENDED"

def test_bench_aging_alerts_fire_at_30_60_90_days(db_session, fixtures):
    _, _, _, employee = fixtures
    entry = mark_employee_on_bench(db_session, employee)
    db_session.commit()

    entry.available_from = date.today() - timedelta(days=30)
    db_session.commit()
    alerts = check_bench_aging_alerts(db_session, tenant_id=employee.tenant_id)
    assert len(alerts) == 1
    assert alerts[0]["days_on_bench"] == 30
    assert alerts[0]["employee_id"] == employee.id

def test_bench_aging_alerts_silent_between_milestones(db_session, fixtures):
    _, _, _, employee = fixtures
    entry = mark_employee_on_bench(db_session, employee)
    db_session.commit()

    entry.available_from = date.today() - timedelta(days=45)
    db_session.commit()
    assert check_bench_aging_alerts(db_session, tenant_id=employee.tenant_id) == []

def test_allocate_removes_bench_pool_entry(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    mark_employee_on_bench(db_session, employee)
    db_session.commit()
    assert db_session.query(BenchPoolEntry).count() == 1

    allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand)
    db_session.commit()

    assert db_session.query(BenchPoolEntry).count() == 0

def test_ending_one_of_several_concurrent_allocations_does_not_bench(db_session, fixtures):
    """allow_concurrent=True lets an employee hold 2 allocations; ending
    just one shouldn't bench them while the other is still ACTIVE."""
    tenant, client, demand, employee = fixtures
    a1 = allocate_employee_to_project(
        db_session, tenant_id=tenant.id, employee=employee, demand=demand,
        utilization_pct=50, allow_concurrent=True,
    )
    db_session.commit()
    a2 = allocate_employee_to_project(
        db_session, tenant_id=tenant.id, employee=employee, demand=demand,
        utilization_pct=50, allow_concurrent=True,
    )
    db_session.commit()

    end_allocation(db_session, a1, employee)
    db_session.commit()

    assert employee.status == "ALLOCATED"
    assert db_session.query(BenchPoolEntry).count() == 0

def test_get_bench_duration_days_computed_from_available_from(db_session, fixtures):
    _, _, _, employee = fixtures
    entry = mark_employee_on_bench(db_session, employee)
    entry.available_from = date.today() - timedelta(days=10)
    db_session.add(entry)
    db_session.commit()

    assert get_bench_duration_days(entry) == 10

def test_get_current_bench_pool_scoped_by_tenant(db_session, fixtures):
    tenant, _, _, employee = fixtures
    mark_employee_on_bench(db_session, employee)
    db_session.commit()

    pool = get_current_bench_pool(db_session, tenant_id=tenant.id)
    assert len(pool) == 1
    assert pool[0].employee_id == employee.id

    other_tenant_pool = get_current_bench_pool(db_session, tenant_id=999999)
    assert other_tenant_pool == []

# ---------------------------------------------------------------------------
# Allocation conflict log
# ---------------------------------------------------------------------------

def test_over_capacity_allocation_logs_conflict(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    allocate_employee_to_project(
        db_session, tenant_id=tenant.id, employee=employee, demand=demand,
        utilization_pct=70, allow_concurrent=True,
    )
    db_session.commit()

    with pytest.raises(AllocationOverCapacity):
        allocate_employee_to_project(
            db_session, tenant_id=tenant.id, employee=employee, demand=demand,
            utilization_pct=50, allow_concurrent=True,
        )

    entries = db_session.query(AllocationConflictLogEntry).filter(
        AllocationConflictLogEntry.employee_id == employee.id
    ).all()
    assert len(entries) == 1
    assert json.loads(entries[0].conflicting_allocation_ids_json)
    assert float(entries[0].existing_utilization_pct) == 70
    assert float(entries[0].attempted_utilization_pct) == 50

# ---------------------------------------------------------------------------
# Utilization metrics
# ---------------------------------------------------------------------------

def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())

def test_record_weekly_utilization_metric_from_approved_timesheet(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    allocation = allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand)
    db_session.commit()

    week = _monday_of(date.today())
    timesheet = Timesheet(
        tenant_id=tenant.id, employee_id=employee.id, allocation_id=allocation.id,
        week_starting_date=week, total_hours=32, billable_hours=32, status="APPROVED",
    )
    db_session.add(timesheet)
    db_session.commit()

    metric = record_weekly_utilization_metric(db_session, employee, week)
    db_session.commit()

    assert float(metric.billable_hours) == 32
    assert float(metric.bench_hours) == 8
    assert float(metric.utilization_pct) == 80

def test_record_weekly_utilization_metric_zero_when_no_approved_timesheet(db_session, fixtures):
    _, _, _, employee = fixtures
    week = _monday_of(date.today())

    metric = record_weekly_utilization_metric(db_session, employee, week)

    assert float(metric.billable_hours) == 0
    assert float(metric.bench_hours) == 40
    assert float(metric.utilization_pct) == 0

def test_record_weekly_utilization_metric_is_upserted_not_duplicated(db_session, fixtures):
    _, _, _, employee = fixtures
    week = _monday_of(date.today())

    record_weekly_utilization_metric(db_session, employee, week)
    db_session.commit()
    record_weekly_utilization_metric(db_session, employee, week)
    db_session.commit()

    assert db_session.query(EmployeeUtilizationMetric).filter(
        EmployeeUtilizationMetric.employee_id == employee.id
    ).count() == 1

# ---------------------------------------------------------------------------
# Staffing Eligibility Engine
# ---------------------------------------------------------------------------

def test_staffing_eligible_by_default(db_session, fixtures):
    _, _, _, employee = fixtures
    eligible, reason = is_staffing_eligible(employee, "SPECIALITY")
    assert eligible is True
    assert reason is None

def test_staffing_ineligible_mid_buddy_program(db_session, fixtures):
    _, _, _, employee = fixtures
    employee.buddy_program_status = "IN_PROGRESS"

    eligible, reason = is_staffing_eligible(employee, "SPECIALITY")
    assert eligible is False
    assert "Buddy Program" in reason

def test_staffing_ineligible_for_core_without_certification(db_session, fixtures):
    _, _, _, employee = fixtures
    assert employee.core_certified is False

    eligible, reason = is_staffing_eligible(employee, "CORE")
    assert eligible is False
    assert "Core-certified" in reason

def test_staffing_eligible_for_core_when_certified(db_session, fixtures):
    _, _, _, employee = fixtures
    employee.core_certified = True
    employee.delivery_engine = "CORE"

    eligible, reason = is_staffing_eligible(employee, "CORE")
    assert eligible is True
    assert reason is None
