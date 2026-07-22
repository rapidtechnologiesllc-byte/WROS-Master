"""
Proves HRMS-0910 (AI Time Entry Anomaly Detection -- weekend, >12h/day,
completed-project, and duplicate-entry checks, BR-0910-01 advisory-only
never blocking submission, BR-0910-02 weekend flagging respects
Project.allow_weekend_billing) and HRMS-0909 (Client Revenue
Realization Dashboard -- earned-vs-planned, billable ratio, burn rate,
all pure aggregation, no new schema).

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
from app.models.opportunity import Opportunity
from app.models.project import Project, ProjectMilestone
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.timesheet_anomaly import TimesheetAnomalyFlag
from app.models.timesheet_dispute import TimesheetDispute
from app.models.invoice import Invoice, InvoiceLineItem

from app.services.employee_allocation_service import allocate_employee_to_project
from app.services.project_service import create_project
from app.services.timesheet_service import create_weekly_draft, upsert_entries, submit_timesheet, approve_timesheet
from app.services.invoice_service import generate_invoice, approve_invoice, send_invoice
from app.services.timesheet_anomaly_service import scan_timesheet_anomalies, get_anomaly_flags_for_timesheet
from app.services.client_revenue_dashboard_service import get_client_revenue_dashboard


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Client.__table__, Demand.__table__, DemandHistory.__table__,
        Employee.__table__, EmployeeEmploymentHistory.__table__,
        EmployeeAllocation.__table__, Opportunity.__table__, Project.__table__, ProjectMilestone.__table__,
        Timesheet.__table__, TimesheetEntry.__table__, TimesheetAnomalyFlag.__table__,
        TimesheetDispute.__table__, Invoice.__table__, InvoiceLineItem.__table__,
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


def _make_project(db, tenant, client, **overrides):
    project = create_project(db, tenant_id=tenant.id, client_id=client.id, name="P1", **overrides)
    db.commit()
    return project


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


def _make_demand(db, tenant, client, project=None, **overrides):
    defaults = dict(
        tenant_id=tenant.id, client_id=client.id, job_title="Sr. Guidewire Developer",
        required_skills='["Guidewire"]', min_experience_years=5.0,
        work_location="REMOTE", status="OPEN", billing_rate_usd_cents=10000,
    )
    if project:
        defaults["project_id"] = project.id
    defaults.update(overrides)
    demand = Demand(**defaults)
    db.add(demand)
    db.commit()
    return demand


def _saturday_on_or_after(d: date) -> date:
    days_ahead = (5 - d.weekday()) % 7
    return d + timedelta(days=days_ahead)


# ---------------------------------------------------------------------------
# HRMS-0910: anomaly detection
# ---------------------------------------------------------------------------

def test_weekend_entry_flagged_when_project_does_not_allow_it(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = _make_project(db_session, tenant, client)  # allow_weekend_billing defaults False
    demand = _make_demand(db_session, tenant, client, project=project)
    employee = _make_employee(db_session, tenant)
    allocation = allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand, project=project)
    db_session.commit()

    saturday = _saturday_on_or_after(date.today() - timedelta(days=14))
    monday = saturday - timedelta(days=5)
    ts = create_weekly_draft(db_session, allocation, monday, tenant_id=tenant.id)
    db_session.commit()
    upsert_entries(db_session, ts, [{"entry_date": saturday, "hours": 4, "entry_type": "BILLABLE"}])
    db_session.commit()

    flags = scan_timesheet_anomalies(db_session, ts)
    db_session.commit()
    assert any(f.anomaly_type == "WEEKEND" for f in flags)


def test_weekend_entry_not_flagged_when_project_allows_it(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = _make_project(db_session, tenant, client)
    project.allow_weekend_billing = True
    db_session.commit()
    demand = _make_demand(db_session, tenant, client, project=project)
    employee = _make_employee(db_session, tenant)
    allocation = allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand, project=project)
    db_session.commit()

    saturday = _saturday_on_or_after(date.today() - timedelta(days=14))
    monday = saturday - timedelta(days=5)
    ts = create_weekly_draft(db_session, allocation, monday, tenant_id=tenant.id)
    db_session.commit()
    upsert_entries(db_session, ts, [{"entry_date": saturday, "hours": 4, "entry_type": "BILLABLE"}])
    db_session.commit()

    flags = scan_timesheet_anomalies(db_session, ts)
    assert not any(f.anomaly_type == "WEEKEND" for f in flags)


def test_over_12h_day_flagged(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = _make_project(db_session, tenant, client)
    demand = _make_demand(db_session, tenant, client, project=project)
    employee = _make_employee(db_session, tenant)
    allocation = allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand, project=project)
    db_session.commit()

    monday = date.today() - timedelta(days=date.today().weekday()) - timedelta(days=14)
    ts = create_weekly_draft(db_session, allocation, monday, tenant_id=tenant.id)
    db_session.commit()
    upsert_entries(db_session, ts, [{"entry_date": monday, "hours": 13, "entry_type": "BILLABLE"}])
    db_session.commit()

    flags = scan_timesheet_anomalies(db_session, ts)
    assert any(f.anomaly_type == "OVER_12H" for f in flags)


def test_completed_project_entry_flagged(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = _make_project(db_session, tenant, client)
    demand = _make_demand(db_session, tenant, client, project=project)
    employee = _make_employee(db_session, tenant)
    allocation = allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand, project=project)
    db_session.commit()

    monday = date.today() - timedelta(days=date.today().weekday()) - timedelta(days=14)
    ts = create_weekly_draft(db_session, allocation, monday, tenant_id=tenant.id)
    db_session.commit()
    upsert_entries(db_session, ts, [{"entry_date": monday, "hours": 8, "entry_type": "BILLABLE"}])
    db_session.commit()

    project.status = "COMPLETED"
    db_session.commit()

    flags = scan_timesheet_anomalies(db_session, ts)
    assert any(f.anomaly_type == "COMPLETED_PROJECT" for f in flags)


def test_duplicate_entry_flagged_across_two_timesheets(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = _make_project(db_session, tenant, client)
    demand1 = _make_demand(db_session, tenant, client, project=project)
    demand2 = _make_demand(db_session, tenant, client, project=project, job_title="QA")
    employee = _make_employee(db_session, tenant)

    alloc1 = allocate_employee_to_project(
        db_session, tenant_id=tenant.id, employee=employee, demand=demand1, project=project,
        utilization_pct=60, allow_concurrent=True,
    )
    db_session.commit()
    alloc2 = allocate_employee_to_project(
        db_session, tenant_id=tenant.id, employee=employee, demand=demand2, project=project,
        utilization_pct=40, allow_concurrent=True,
    )
    db_session.commit()

    monday = date.today() - timedelta(days=date.today().weekday()) - timedelta(days=14)
    ts1 = create_weekly_draft(db_session, alloc1, monday, tenant_id=tenant.id)
    db_session.commit()
    upsert_entries(db_session, ts1, [{"entry_date": monday, "hours": 4, "entry_type": "BILLABLE"}])
    db_session.commit()

    ts2 = create_weekly_draft(db_session, alloc2, monday, tenant_id=tenant.id)
    db_session.commit()
    upsert_entries(db_session, ts2, [{"entry_date": monday, "hours": 4, "entry_type": "BILLABLE"}])
    db_session.commit()

    flags = scan_timesheet_anomalies(db_session, ts2)
    assert any(f.anomaly_type == "DUPLICATE" for f in flags)


def test_scan_does_not_block_submission_and_is_idempotent(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = _make_project(db_session, tenant, client)
    demand = _make_demand(db_session, tenant, client, project=project)
    employee = _make_employee(db_session, tenant)
    allocation = allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand, project=project)
    db_session.commit()

    monday = date.today() - timedelta(days=date.today().weekday()) - timedelta(days=14)
    ts = create_weekly_draft(db_session, allocation, monday, tenant_id=tenant.id)
    db_session.commit()
    upsert_entries(db_session, ts, [{"entry_date": monday, "hours": 13, "entry_type": "BILLABLE"}])
    db_session.commit()

    # BR-0910-01: scanning never touches submission -- submit works regardless.
    submit_timesheet(db_session, ts)
    db_session.commit()
    assert ts.status == "SUBMITTED"

    first_pass = scan_timesheet_anomalies(db_session, ts)
    db_session.commit()
    second_pass = scan_timesheet_anomalies(db_session, ts)
    db_session.commit()

    assert len(first_pass) == len(second_pass)
    assert {f.id for f in first_pass} == {f.id for f in second_pass}
    assert len(get_anomaly_flags_for_timesheet(db_session, ts)) == len(first_pass)


# ---------------------------------------------------------------------------
# HRMS-0909: client revenue dashboard
# ---------------------------------------------------------------------------

def test_dashboard_insufficient_data_with_no_projects(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    result = get_client_revenue_dashboard(db_session, client, tenant_id=tenant.id)
    assert result["earned_usd_cents"] is None
    assert "INSUFFICIENT_DATA" in result["note"]


def test_dashboard_billable_ratio_none_without_approved_timesheets(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = _make_project(db_session, tenant, client)
    result = get_client_revenue_dashboard(db_session, client, tenant_id=tenant.id)
    assert result["billable_ratio_pct"] is None
    assert result["earned_usd_cents"] == 0


def test_dashboard_earned_and_billable_ratio_computed(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    project = _make_project(db_session, tenant, client)
    demand = _make_demand(db_session, tenant, client, project=project)
    employee = _make_employee(db_session, tenant)
    allocation = allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand, project=project)
    db_session.commit()

    monday = date.today() - timedelta(days=date.today().weekday()) - timedelta(days=14)
    ts = create_weekly_draft(db_session, allocation, monday, tenant_id=tenant.id)
    db_session.commit()
    upsert_entries(db_session, ts, [
        {"entry_date": monday + timedelta(days=i), "hours": 8, "entry_type": "BILLABLE"} for i in range(4)
    ] + [{"entry_date": monday + timedelta(days=4), "hours": 8, "entry_type": "NON_BILLABLE"}])
    submit_timesheet(db_session, ts)
    approve_timesheet(db_session, ts, approved_by="U-RM")
    db_session.commit()

    invoice = generate_invoice(db_session, project, period_start=monday, period_end=monday + timedelta(days=6))
    approve_invoice(db_session, invoice, approved_by="U-FIN")
    send_invoice(db_session, invoice)
    db_session.commit()

    result = get_client_revenue_dashboard(db_session, client, tenant_id=tenant.id)
    # 32 billable hours * $100/hr = 320000 cents
    assert result["earned_usd_cents"] == 320000
    # 32 billable / 40 total = 80%
    assert result["billable_ratio_pct"] == 80.0


def test_dashboard_planned_revenue_from_won_opportunity(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    opp = Opportunity(
        tenant_id=tenant.id, client_id=client.id, stage="WON",
        revenue_value_usd_cents=1_000_000_00, probability_pct=100,
    )
    db_session.add(opp)
    db_session.commit()
    project = create_project(db_session, tenant_id=tenant.id, client_id=client.id, name="Won Deal")
    project.opportunity_id = opp.id
    db_session.commit()

    result = get_client_revenue_dashboard(db_session, client, tenant_id=tenant.id)
    assert result["planned_usd_cents"] == 1_000_000_00


def test_dashboard_burn_rate_none_for_non_fixed_bid(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    opp = Opportunity(
        tenant_id=tenant.id, client_id=client.id, stage="WON",
        revenue_value_usd_cents=1_000_000_00, probability_pct=100,
    )
    db_session.add(opp)
    db_session.commit()
    project = create_project(
        db_session, tenant_id=tenant.id, client_id=client.id, name="T&M Deal",
        billing_type="TIME_AND_MATERIALS",
    )
    project.opportunity_id = opp.id
    project.start_date = date.today() - timedelta(days=30)
    project.end_date = date.today() + timedelta(days=30)
    db_session.commit()

    result = get_client_revenue_dashboard(db_session, client, tenant_id=tenant.id)
    assert result["burn_rate_pct"] is None


def test_dashboard_burn_rate_computed_for_fixed_bid_with_dates(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    opp = Opportunity(
        tenant_id=tenant.id, client_id=client.id, stage="WON",
        revenue_value_usd_cents=100000_00, probability_pct=100,
    )
    db_session.add(opp)
    db_session.commit()
    project = create_project(
        db_session, tenant_id=tenant.id, client_id=client.id, name="Fixed Bid Deal",
        billing_type="FIXED_BID",
    )
    project.opportunity_id = opp.id
    project.start_date = date.today() - timedelta(days=50)
    project.end_date = date.today() + timedelta(days=50)  # 100-day span, 50 elapsed = 50%
    db_session.commit()

    demand = _make_demand(db_session, tenant, client, project=project)
    employee = _make_employee(db_session, tenant)
    allocation = allocate_employee_to_project(db_session, tenant_id=tenant.id, employee=employee, demand=demand, project=project)
    db_session.commit()
    monday = date.today() - timedelta(days=date.today().weekday()) - timedelta(days=14)
    ts = create_weekly_draft(db_session, allocation, monday, tenant_id=tenant.id)
    db_session.commit()
    upsert_entries(db_session, ts, [
        {"entry_date": monday + timedelta(days=i), "hours": 8, "entry_type": "BILLABLE"} for i in range(5)
    ])
    submit_timesheet(db_session, ts)
    approve_timesheet(db_session, ts, approved_by="U-RM")
    db_session.commit()
    invoice = generate_invoice(db_session, project, period_start=monday, period_end=monday + timedelta(days=6))
    approve_invoice(db_session, invoice, approved_by="U-FIN")
    send_invoice(db_session, invoice)
    db_session.commit()
    # earned = 40h * $100 = 400000 cents; expected spend at 50% elapsed = 5000000 cents
    # burn_rate = 400000/5000000*100 = 8.0
    result = get_client_revenue_dashboard(db_session, client, tenant_id=tenant.id)
    assert result["burn_rate_pct"] == 8.0
