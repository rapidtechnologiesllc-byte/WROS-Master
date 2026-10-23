"""One definition of monthly revenue (CEO 2026-10-23): the P&L, Forecast vs Actual, the BU Head's
month-to-date figure and the client revenue dashboard all count EARNED revenue from the revenue
chain (billed or approved work, by timesheet week) -- never invoices by created_at, which
moved a month's work into whatever month Finance happened to raise the invoice."""
import uuid
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnit
from app.models.client import Client
from app.models.cost_rate_config import CostRateConfig
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.invoice import Invoice
from app.models.project import Project
from app.models.tenant import Tenant
from app.models.timesheet import Timesheet
from app.models.user import Jobs
from app.services import revenue_chain_service as chain
from app.services.bu_head_dashboard_service import BUHeadDashboardService
from app.services.client_revenue_dashboard_service import get_client_revenue_dashboard
from app.services.forecast_variance_service import get_forecast_vs_actual, get_monthly_actual_revenue

RATE = 10_000  # $100/h


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def world(db):
    """One client with September work: two approved weeks (one of them invoiced in October), one
    week still awaiting approval, and a stray invoice raised in September for August work."""
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    unit = BusinessUnit(tenant_id=1, name=f"bu-{_uid()}", display_name="BU")
    other_unit = BusinessUnit(tenant_id=1, name=f"bu-{_uid()}", display_name="Other BU")
    db.add_all([unit, other_unit])
    db.flush()
    db.add(CostRateConfig(business_unit_id=unit.id, statutory_pct=10, overhead_pct=20))
    client = Client(tenant_id=1, company_name=f"Insurer {_uid()}", business_unit_id=unit.id)
    other = Client(tenant_id=1, company_name=f"Other {_uid()}", business_unit_id=other_unit.id)
    db.add_all([client, other])
    db.flush()
    job = Jobs(tenant_id=1, client_id=client.id, jobTitle="Dev", jobDescription="d", jobSkills="x",
               jobExperience="5", jobLocation="Remote")
    project = Project(tenant_id=1, client_id=client.id, name=f"Upgrade {_uid()}", delivery_engine="CORE")
    db.add_all([job, project])
    db.flush()
    worker = Employee(tenant_id=1, first_name="Sam", last_name=_uid(), email=f"{_uid()}@x.test",
                      joining_date=date(2025, 1, 1), status="ALLOCATED", bu_id=unit.id,
                      base_salary_usd_cents=1_000_000)
    db.add(worker)
    db.flush()
    allocation = EmployeeAllocation(tenant_id=1, employee_id=worker.id, client_id=client.id, demand_id=job.jobID,
                                    project_id=project.id, billing_rate_usd_cents=RATE, status="ACTIVE",
                                    start_date=date(2025, 1, 1))
    db.add(allocation)
    db.flush()
    for week, status in ((date(2026, 9, 7), "APPROVED"), (date(2026, 9, 14), "APPROVED"),
                         (date(2026, 9, 21), "SUBMITTED")):
        db.add(Timesheet(tenant_id=1, employee_id=worker.id, allocation_id=allocation.id, week_starting_date=week,
                         total_hours=40, billable_hours=40, non_billable_hours=0, status=status))
    # raised in September for August work: invoice-by-created_at counted it as September revenue
    db.add(Invoice(tenant_id=1, project_id=project.id, client_id=client.id, status="SENT",
                   billing_period_start=date(2026, 8, 1), billing_period_end=date(2026, 8, 31),
                   total_usd_cents=999_999, created_at=datetime(2026, 9, 2)))
    db.commit()
    return SimpleNamespace(unit=unit, other_unit=other_unit, client=client, other=other, project=project)


EARNED_SEPT = 2 * 40 * RATE  # two approved weeks; the submitted week is pending, not revenue


def test_monthly_actual_is_the_pnl_earned_revenue(db, world):
    actual = get_monthly_actual_revenue(db, client_ids=[world.client.id], year=2026, month=9)
    pnl = chain.pnl(db, start=date(2026, 9, 1), end=date(2026, 9, 30), business_unit_ids={world.unit.id})
    assert actual == EARNED_SEPT == pnl["revenue_usd_cents"]
    assert get_monthly_actual_revenue(db, client_ids=[world.client.id], year=2026, month=8) == 0


def test_monthly_actual_respects_the_client_scope(db, world):
    assert get_monthly_actual_revenue(db, client_ids=[world.other.id], year=2026, month=9) == 0
    assert get_monthly_actual_revenue(db, client_ids=[], year=2026, month=9) == 0
    assert get_monthly_actual_revenue(db, client_ids=None, year=2026, month=9) >= EARNED_SEPT


def test_forecast_vs_actual_uses_earned_revenue(db, world):
    result = get_forecast_vs_actual(db, client_ids=[world.client.id], year=2026, month=9)
    assert result["actual_usd_cents"] == EARNED_SEPT
    assert result["status"] == "NO_FORECAST"


def test_bu_head_month_to_date_is_earned_revenue(db, world):
    sept = BUHeadDashboardService.get_bu_dashboard_data(db, world.unit.id, today=date(2026, 9, 30))
    assert sept["revenue"]["mtd_usd"] == EARNED_SEPT // 100
    # month to date: weeks starting after "today" are not counted yet
    mid = BUHeadDashboardService.get_bu_dashboard_data(db, world.unit.id, today=date(2026, 9, 10))
    assert mid["revenue"]["mtd_usd"] == 40 * RATE // 100
    other = BUHeadDashboardService.get_bu_dashboard_data(db, world.other_unit.id, today=date(2026, 9, 30))
    assert other["revenue"]["mtd_usd"] == 0


def test_client_dashboard_earned_is_revenue_chain_earned(db, world):
    dashboard = get_client_revenue_dashboard(db, world.client, today=date(2026, 10, 20))
    assert dashboard["earned_usd_cents"] == EARNED_SEPT  # not the stray 999_999 invoice


def test_revenue_chain_summary_by_project_matches_the_pnl(db, world):
    lines = chain.chain_lines(db, start=date(2026, 9, 1), end=date(2026, 9, 30),
                              business_unit_ids={world.unit.id})
    rows = chain.summarize(lines, "project")
    assert [(r["key"], r["earned_usd_cents"]) for r in rows] == [(world.project.id, EARNED_SEPT)]
