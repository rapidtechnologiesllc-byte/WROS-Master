"""Projected vs actual revenue, anticipated vs actual expense (CEO 2026-10-11): a hire is
expense from day one, bench or not; deployment is projected revenue; only money paid into
the account is actual revenue."""
import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.models.bank_reconciliation import BankTransaction
from app.models.business_unit import BusinessUnit
from app.models.client import Client
from app.models.cost_rate_config import CostRateConfig
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.expense import ExpenseRecord
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.project import Project
from app.models.tenant import Tenant
from app.models.timesheet import Timesheet
from app.models.user import Jobs, Users
from app.services.financial_outlook_service import business_days, outlook
from tests.hiring_fixtures import full_access_role

RATE = 10_000          # $100/h
SALARY = 1_000_000     # $10,000/month, loaded x1.3 (10% statutory + 20% overhead)
LOADED = 1_300_000
SEPT = (date(2026, 9, 1), date(2026, 9, 30))


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def world(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    role = full_access_role(db)
    partner = Users(UserID=f"P-{_uid()}", UserName="Pat Partner", UserEmail=f"p{_uid()}@x.com", UserPassword="x",
                    UserRole="x", tenant_id=1, role_template_id=role.id)
    db.add(partner)
    db.flush()
    unit = BusinessUnit(name=f"bu-{_uid()}", display_name="BU", partner_user_id=partner.UserID)
    db.add(unit)
    db.flush()
    db.add(CostRateConfig(business_unit_id=unit.id, statutory_pct=10, overhead_pct=20))
    client = Client(tenant_id=1, company_name=f"Client {_uid()}", business_unit_id=unit.id, payment_terms_days=30)
    db.add(client)
    db.flush()
    project = Project(tenant_id=1, client_id=client.id, name=f"P {_uid()}", delivery_engine="CORE")
    db.add(project)
    db.flush()
    job = Jobs(tenant_id=1, client_id=client.id, project_id=project.id, jobTitle="Dev", jobDescription="d",
               jobSkills="x", jobExperience="5", jobLocation="Remote", billing_rate_usd_cents=RATE)
    deployed = Employee(tenant_id=1, first_name="Dee", last_name="Ployed", email=f"d{_uid()}@x.com",
                        joining_date=date(2025, 1, 1), status="ALLOCATED", bu_id=unit.id, base_salary_usd_cents=SALARY)
    bench = Employee(tenant_id=1, first_name="Ben", last_name="Ch", email=f"b{_uid()}@x.com",
                     joining_date=date(2025, 1, 1), status="BENCH", bu_id=unit.id, base_salary_usd_cents=SALARY)
    db.add_all([job, deployed, bench])
    db.flush()
    allocation = EmployeeAllocation(tenant_id=1, employee_id=deployed.id, client_id=client.id, demand_id=job.jobID,
                                    project_id=project.id, billing_rate_usd_cents=RATE, status="ACTIVE",
                                    start_date=date(2026, 1, 1))
    db.add(allocation)
    db.flush()
    sheet = Timesheet(tenant_id=1, employee_id=deployed.id, allocation_id=allocation.id,
                      week_starting_date=date(2026, 9, 7), total_hours=40, billable_hours=40, status="APPROVED")
    db.add(sheet)
    db.flush()
    invoice = Invoice(tenant_id=1, project_id=project.id, client_id=client.id, billing_period_start=SEPT[0],
                      billing_period_end=SEPT[1], currency="USD", total_usd_cents=40 * RATE, status="PAID")
    db.add(invoice)
    db.flush()
    db.add(InvoiceLineItem(invoice_id=invoice.id, employee_id=deployed.id, timesheet_id=sheet.id, hours=40,
                           rate_usd_cents=RATE, amount_usd_cents=40 * RATE))
    db.add(BankTransaction(tenant_id=1, transaction_date=date(2026, 9, 20), amount_usd_cents=40 * RATE,
                           description="UTR1", matched_invoice_id=invoice.id, reconciled=True))
    for status, payment, amount in (("APPROVED", "REIMBURSED", 50_000), ("PENDING", "PENDING", 20_000),
                                    ("REJECTED", "PENDING", 99_999)):
        db.add(ExpenseRecord(tenant_id=1, business_unit_id=unit.id, logged_by_user_id=partner.UserID,
                             purpose="CLIENT_CURRENT", client_id=client.id, expense_category="TRAVEL",
                             amount_usd_cents=amount, receipt_ref="r", expense_date=date(2026, 9, 10),
                             manager_approval_status=status, payment_status=payment))
    db.commit()
    return SimpleNamespace(unit=unit, partner=partner, client=client, job=job, deployed=deployed, bench=bench,
                           allocation=allocation, role=role)


def _bu(report, unit):
    return next(r for r in report["by_business_unit"] if r["key"] == unit.id)


def test_projected_vs_actual_revenue_and_anticipated_vs_actual_expense(db, world):
    report = _bu(outlook(db, start=SEPT[0], end=SEPT[1], today=date(2026, 9, 15)), world.unit)
    assert report["projected_revenue"] == business_days(*SEPT) * 8 * RATE   # deployed all month at 8h/day
    assert report["earned_revenue"] == 40 * RATE                            # approved time
    assert report["billed_revenue"] == 40 * RATE
    assert report["actual_revenue"] == 40 * RATE                            # cash received
    assert report["revenue_variance"] == 40 * RATE - business_days(*SEPT) * 8 * RATE

    assert report["anticipated_bench_cost"] == LOADED                       # bench: pure expense
    assert report["anticipated_deployed_cost"] == LOADED
    assert report["anticipated_other_expense"] == 50_000 + 20_000           # rejected never counts
    assert report["anticipated_expense"] == 2 * LOADED + 70_000
    assert report["actual_payroll"] == 2 * round(LOADED * 15 / 30)          # incurred to the 15th
    assert report["actual_other_expense"] == 50_000                         # reimbursed only
    assert report["actual_net"] == report["actual_revenue"] - report["actual_expense"]


def test_partner_and_org_rows_add_up_and_scope_limits_to_the_bu(db, world):
    org = outlook(db, start=SEPT[0], end=SEPT[1], today=date(2026, 9, 15))
    bu = _bu(org, world.unit)
    partner = next(r for r in org["by_partner"] if r["key"] == world.partner.UserID)
    assert partner["projected_revenue"] == bu["projected_revenue"] and partner["name"] == "Pat Partner"
    scoped = outlook(db, start=SEPT[0], end=SEPT[1], today=date(2026, 9, 15), business_unit_ids=[world.unit.id])
    assert [r["key"] for r in scoped["by_business_unit"]] == [world.unit.id]
    assert scoped["anticipated_expense"] == bu["anticipated_expense"]


def test_a_new_hire_on_the_bench_is_expense_and_unknown_inputs_are_listed(db, world):
    hire = Employee(tenant_id=1, first_name="New", last_name="Hire", email=f"n{_uid()}@x.com",
                    joining_date=date(2026, 9, 16), status="PRE_JOINING", bu_id=world.unit.id,
                    base_salary_usd_cents=SALARY)
    no_salary = Employee(tenant_id=1, first_name="No", last_name="Pay", email=f"x{_uid()}@x.com",
                         joining_date=date(2025, 1, 1), status="BENCH", bu_id=world.unit.id)
    db.add_all([hire, no_salary])
    db.flush()
    world.allocation.billing_rate_usd_cents = None
    db.commit()
    report = outlook(db, start=SEPT[0], end=SEPT[1], today=date(2026, 9, 15))
    assert _bu(report, world.unit)["anticipated_bench_cost"] == LOADED + round(LOADED * 15 / 30)  # joins on the 16th
    assert _bu(report, world.unit)["projected_revenue"] == 0
    assert world.allocation.id in report["gaps"]["allocations_without_bill_rate"]
    assert no_salary.id in report["gaps"]["employees_without_cost"] and not report["data_complete"]


def test_endpoint_scopes_by_role_template(db, world):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.main import app
    from app.models.role_template import RoleTemplate

    def headers(user):
        return {"Authorization": "Bearer " + create_access_token(
            {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}

    other_unit = BusinessUnit(name=f"bu-{_uid()}", display_name="Other")
    db.add(other_unit)
    db.flush()
    scoped_role = full_access_role(db)
    db.get(RoleTemplate, scoped_role.id).org_level_access = False  # all permissions, but BU-scoped
    world.partner.role_template_id = scoped_role.id                 # partner of world.unit
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        org_admin = Users(UserID=f"A-{_uid()}", UserName="Admin", UserEmail=f"a{_uid()}@x.com", UserPassword="x",
                          UserRole="x", tenant_id=1, role_template_id=world.role.id)
        db.add(org_admin)
        db.commit()
        org = client.get("/api/v1/finance/outlook?period=month&year=2026&month=9", headers=headers(org_admin))
        assert org.status_code == 200, org.text
        assert org.json()["scope"] == "org"
        mine = client.get("/api/v1/finance/outlook?period=year&year=2026&month=9", headers=headers(world.partner))
        assert mine.status_code == 200 and mine.json()["scope"] == "business_units"
        assert {r["key"] for r in mine.json()["by_business_unit"]} == {world.unit.id}
        forbidden = client.get(f"/api/v1/finance/outlook?business_unit_id={other_unit.id}", headers=headers(world.partner))
        assert forbidden.status_code == 403
    finally:
        app.dependency_overrides.clear()
