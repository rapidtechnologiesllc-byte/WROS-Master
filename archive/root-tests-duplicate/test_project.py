"""
Proves HRMS-0801 (Project Lifecycle, incl. auto-creation on Opportunity
WON), HRMS-0804 (Milestones, delay always computed), HRMS-0803
(overlapping-allocation capacity block, opt-in via allow_concurrent),
HRMS-0805 (unfilled-role gap detection), and HRMS-0806 (revenue/margin
estimate, incl. insufficient-data handling).

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
from app.models.resource_management import AllocationConflictLogEntry, BenchPeriod, BenchPoolEntry, EmployeeUtilizationMetric
from app.models.opportunity import Opportunity
from app.models.project import Project, ProjectMilestone

from app.services.opportunity_service import create_opportunity, transition_stage
from app.services.project_service import (
    create_project,
    create_project_from_won_opportunity,
    transition_project_status,
    create_milestone,
    complete_milestone,
    get_unfilled_project_roles,
    calculate_project_expected_revenue,
    InvalidProjectTransition,
    MilestoneValidationError,
)
from app.services.employee_allocation_service import (
    allocate_employee_to_project,
    end_allocation,
    EmployeeAlreadyAllocated,
    AllocationOverCapacity,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Client.__table__, Demand.__table__, DemandHistory.__table__,
        Employee.__table__, EmployeeEmploymentHistory.__table__,
        EmployeeAllocation.__table__, Opportunity.__table__, Project.__table__, ProjectMilestone.__table__,
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
def tenant_and_client(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    client = Client(tenant_id=tenant.id, company_name="Acme Insurance")
    db_session.add(client)
    db_session.commit()
    return tenant, client


def _make_demand(db, tenant, client, **overrides):
    defaults = dict(
        tenant_id=tenant.id, client_id=client.id, job_title="Sr. Guidewire Developer",
        required_skills='["Guidewire"]', min_experience_years=5.0,
        work_location="REMOTE", status="OPEN", billing_rate_usd_cents=15000, headcount=1,
    )
    defaults.update(overrides)
    demand = Demand(**defaults)
    db.add(demand)
    db.commit()
    return demand


def _make_employee(db, tenant, **overrides):
    defaults = dict(
        tenant_id=tenant.id, first_name="Sam", last_name="Lee", email="sam@blitzenx.com",
        joining_date=date(2025, 1, 1), status="BENCH",
    )
    defaults.update(overrides)
    emp = Employee(**defaults)
    db.add(emp)
    db.commit()
    return emp


# ---------------------------------------------------------------------------
# HRMS-0801: lifecycle + auto-creation on WON
# ---------------------------------------------------------------------------

def test_manual_project_creation(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = create_project(db_session, tenant_id=tenant.id, client_id=client.id, name="Direct Follow-on Work")
    db_session.commit()
    assert project.status == "ACTIVE"
    assert project.opportunity_id is None


def test_cannot_create_from_opportunity_not_won(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    opp = create_opportunity(db_session, tenant_id=tenant.id, client_id=client.id, revenue_value_usd_cents=100_00, probability_pct=50)
    db_session.commit()

    with pytest.raises(ValueError):
        create_project_from_won_opportunity(db_session, opp, name="x")


def test_transition_to_won_auto_creates_project_inheriting_client_and_currency(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    opp = create_opportunity(
        db_session, tenant_id=tenant.id, client_id=client.id,
        revenue_value_usd_cents=500_000_00, probability_pct=80, currency="INR",
    )
    db_session.commit()

    opportunity, project = transition_stage(db_session, opp, "WON", project_name="Acme Guidewire Rollout")
    db_session.commit()

    assert opportunity.stage == "WON"
    assert project.client_id == client.id
    assert project.currency == "INR"
    assert project.opportunity_id == opp.id
    assert project.name == "Acme Guidewire Rollout"


def test_project_status_transitions(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = create_project(db_session, tenant_id=tenant.id, client_id=client.id, name="P1")
    db_session.commit()

    transition_project_status(db_session, project, "ON_HOLD")
    db_session.commit()
    assert project.status == "ON_HOLD"


def test_project_status_rejects_invalid_transition(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = create_project(db_session, tenant_id=tenant.id, client_id=client.id, name="P1")
    project.status = "CLOSED"
    db_session.commit()

    with pytest.raises(InvalidProjectTransition):
        transition_project_status(db_session, project, "ACTIVE")


# ---------------------------------------------------------------------------
# HRMS-0804: milestones -- delay always computed
# ---------------------------------------------------------------------------

def test_milestone_completed_on_time_has_zero_delay(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = create_project(db_session, tenant_id=tenant.id, client_id=client.id, name="P1")
    db_session.commit()
    milestone = create_milestone(db_session, project, title="Kickoff", due_date=date(2026, 2, 1))
    db_session.commit()

    complete_milestone(db_session, milestone, completion_date=date(2026, 2, 1))
    db_session.commit()
    assert milestone.delay_days == 0


def test_milestone_completed_late_computes_delay(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = create_project(db_session, tenant_id=tenant.id, client_id=client.id, name="P1")
    db_session.commit()
    milestone = create_milestone(db_session, project, title="Kickoff", due_date=date(2026, 2, 1))
    db_session.commit()

    complete_milestone(db_session, milestone, completion_date=date(2026, 2, 4))
    db_session.commit()
    assert milestone.delay_days == 3
    assert milestone.is_complete == "COMPLETE"


def test_cannot_complete_already_complete_milestone(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = create_project(db_session, tenant_id=tenant.id, client_id=client.id, name="P1")
    db_session.commit()
    milestone = create_milestone(db_session, project, title="Kickoff", due_date=date(2026, 2, 1))
    db_session.commit()
    complete_milestone(db_session, milestone, completion_date=date(2026, 2, 1))
    db_session.commit()

    with pytest.raises(MilestoneValidationError):
        complete_milestone(db_session, milestone, completion_date=date(2026, 2, 2))


# ---------------------------------------------------------------------------
# HRMS-0803: overlapping-allocation capacity block
# ---------------------------------------------------------------------------

def test_default_behavior_unchanged_single_allocation_blocks_second(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    demand1 = _make_demand(db_session, tenant, client)
    demand2 = _make_demand(db_session, tenant, client, job_title="QA")
    employee = _make_employee(db_session, tenant)

    allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand1)
    db_session.commit()

    with pytest.raises(EmployeeAlreadyAllocated):
        allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand2)


def test_concurrent_allocations_allowed_within_100_percent(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    demand1 = _make_demand(db_session, tenant, client)
    demand2 = _make_demand(db_session, tenant, client, job_title="QA")
    employee = _make_employee(db_session, tenant)

    allocate_employee_to_project(
        db_session, tenant_id=tenant.id, employee=employee, demand=demand1,
        utilization_pct=60, allow_concurrent=True,
    )
    db_session.commit()

    second = allocate_employee_to_project(
        db_session, tenant_id=tenant.id, employee=employee, demand=demand2,
        utilization_pct=40, allow_concurrent=True,
    )
    db_session.commit()
    assert second.utilization_pct == 40


def test_concurrent_allocation_blocked_over_100_percent(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    demand1 = _make_demand(db_session, tenant, client)
    demand2 = _make_demand(db_session, tenant, client, job_title="QA")
    employee = _make_employee(db_session, tenant)

    allocate_employee_to_project(
        db_session, tenant_id=tenant.id, employee=employee, demand=demand1,
        utilization_pct=70, allow_concurrent=True,
    )
    db_session.commit()

    with pytest.raises(AllocationOverCapacity):
        allocate_employee_to_project(
            db_session, tenant_id=tenant.id, employee=employee, demand=demand2,
            utilization_pct=40, allow_concurrent=True,
        )


def test_ended_allocation_does_not_count_toward_capacity(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    demand1 = _make_demand(db_session, tenant, client)
    demand2 = _make_demand(db_session, tenant, client, job_title="QA")
    employee = _make_employee(db_session, tenant)

    first = allocate_employee_to_project(
        db_session, tenant_id=tenant.id, employee=employee, demand=demand1,
        utilization_pct=100, allow_concurrent=True,
    )
    db_session.commit()
    end_allocation(db_session, first, employee)
    db_session.commit()

    second = allocate_employee_to_project(
        db_session, tenant_id=tenant.id, employee=employee, demand=demand2,
        utilization_pct=100, allow_concurrent=True,
    )
    db_session.commit()
    assert second.utilization_pct == 100


# ---------------------------------------------------------------------------
# HRMS-0805: unfilled project roles
# ---------------------------------------------------------------------------

def test_unfilled_role_detected_when_no_allocation(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = create_project(db_session, tenant_id=tenant.id, client_id=client.id, name="P1")
    db_session.commit()
    demand = _make_demand(db_session, tenant, client, project_id=project.id, headcount=2)

    gaps = get_unfilled_project_roles(db_session, project)
    assert len(gaps) == 1
    assert gaps[0]["open_positions"] == 2
    assert gaps[0]["gap_status"] == "OPEN"


def test_gap_status_urgent_within_7_days(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = create_project(db_session, tenant_id=tenant.id, client_id=client.id, name="P1")
    db_session.commit()
    _make_demand(
        db_session, tenant, client, project_id=project.id,
        required_start_date=date.today() + timedelta(days=3),
    )

    gaps = get_unfilled_project_roles(db_session, project)
    assert gaps[0]["gap_status"] == "URGENT"


def test_gap_status_overdue_when_start_date_passed(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = create_project(db_session, tenant_id=tenant.id, client_id=client.id, name="P1")
    db_session.commit()
    _make_demand(
        db_session, tenant, client, project_id=project.id,
        required_start_date=date.today() - timedelta(days=1),
    )

    gaps = get_unfilled_project_roles(db_session, project)
    assert gaps[0]["gap_status"] == "OVERDUE"


def test_no_gap_when_headcount_fully_allocated(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = create_project(db_session, tenant_id=tenant.id, client_id=client.id, name="P1")
    db_session.commit()
    demand = _make_demand(db_session, tenant, client, project_id=project.id, headcount=1)
    employee = _make_employee(db_session, tenant)
    allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand, project=project)
    db_session.commit()

    gaps = get_unfilled_project_roles(db_session, project)
    assert gaps == []


# ---------------------------------------------------------------------------
# HRMS-0806: revenue/margin estimate
# ---------------------------------------------------------------------------

def test_revenue_estimate_insufficient_data_with_no_allocations(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = create_project(db_session, tenant_id=tenant.id, client_id=client.id, name="P1")
    db_session.commit()

    result = calculate_project_expected_revenue(db_session, project)
    assert result["margin_indicator"] == "INSUFFICIENT_DATA"
    assert "Estimate only" in result["note"]


def test_revenue_estimate_computed_with_full_data(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = create_project(db_session, tenant_id=tenant.id, client_id=client.id, name="P1")
    db_session.commit()
    demand = _make_demand(db_session, tenant, client, project_id=project.id, billing_rate_usd_cents=10000)
    employee = _make_employee(db_session, tenant, base_salary_usd_cents=500000)

    allocate_employee_to_project(
        db_session, tenant_id=tenant.id, employee=employee, demand=demand, project=project,
        end_date=date.today() + timedelta(days=30), utilization_pct=100,
    )
    db_session.commit()

    result = calculate_project_expected_revenue(db_session, project)
    assert result["expected_revenue_usd_cents"] is not None
    assert result["margin_indicator"] in ("HEALTHY", "TIGHT", "AT_RISK")
    assert "Estimate only" in result["note"]


def test_revenue_estimate_missing_end_date_is_insufficient(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = create_project(db_session, tenant_id=tenant.id, client_id=client.id, name="P1")
    db_session.commit()
    demand = _make_demand(db_session, tenant, client, project_id=project.id, billing_rate_usd_cents=10000)
    employee = _make_employee(db_session, tenant)

    allocate_employee_to_project(
        db_session, tenant_id=tenant.id, employee=employee, demand=demand, project=project,
    )  # no end_date
    db_session.commit()

    result = calculate_project_expected_revenue(db_session, project)
    assert result["margin_indicator"] == "INSUFFICIENT_DATA"
