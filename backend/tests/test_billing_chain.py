"""The billing chain end to end: allocation -> timesheet -> project -> client -> invoice ->
payment -> revenue. Each link is checked for the defects found in the 2026-10-10 trace:
time logged where it cannot be billed, weeks straddling two months, double billing,
the wrong currency label, cross-tenant access, revenue nobody is credited for, and
billable time that silently never reaches an invoice."""
import uuid
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnit
from app.models.client import Client, ClientContact
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.invoice import Invoice
from app.models.invoice_automation import InvoiceAutomationDecision
from app.models.project import Project
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.timesheet import Timesheet
from app.models.user import Jobs
from app.services import invoice_service as invoices
from app.services import timesheet_service
from app.services.bank_reconciliation_service import BankReconciliationError, record_invoice_payment
from app.services.employee_allocation_service import AllocationNeedsClient, allocate_employee_to_project
from app.services.invoice_automation_service import run_auto_invoicing
from app.services.revenue_chain_service import recognize_revenue

RATE = 10_000  # $100/h


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
def queued():
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True):
        yield


def _world(db, *, partner=True, currency="USD", contact=True):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    unit = None
    if partner:
        unit = BusinessUnit(tenant_id=1, name=f"bu-{_uid()}", display_name="BU")
        db.add(unit)
        db.flush()
    client = Client(tenant_id=1, company_name=f"Client {_uid()}", business_unit_id=unit.id if unit else None,
                    payment_terms_days=30)
    db.add(client)
    db.flush()
    if contact:
        db.add(ClientContact(tenant_id=1, client_id=client.id, name="AP", email=f"ap{_uid()}@client.example",
                             role_type="ACCOUNTS", is_primary=True))
    project = Project(tenant_id=1, client_id=client.id, name=f"Project {_uid()}", delivery_engine="CORE",
                      currency=currency)
    db.add(project)
    db.flush()
    job = Jobs(tenant_id=1, client_id=client.id, project_id=project.id, jobTitle="Dev", jobDescription="d",
               jobSkills="x", jobExperience="5", jobLocation="Remote", billing_rate_usd_cents=RATE)
    worker = Employee(tenant_id=1, first_name="Sam", last_name="Lee", email=f"s{_uid()}@x.com",
                      joining_date=date(2025, 1, 1), status="BENCH", bu_id=unit.id if unit else None)
    db.add_all([job, worker])
    db.flush()
    return SimpleNamespace(unit=unit, client=client, project=project, job=job, worker=worker)


def _allocate(db, w, start=date(2026, 8, 1), end=None):
    allocation = allocate_employee_to_project(db, tenant_id=1, employee=w.worker, demand=w.job, start_date=start,
                                              end_date=end)
    db.flush()
    return allocation


def _week(db, allocation, monday, days, status="APPROVED"):
    """days: {date: hours} -- logged through the real service, then set to `status`."""
    ts = timesheet_service.create_weekly_draft(db, allocation, monday, tenant_id=1)
    db.flush()
    timesheet_service.upsert_entries(db, ts, [{"entry_date": d, "hours": h} for d, h in days.items()])
    ts.status = status
    db.commit()
    return ts


# ---- allocation -> project -------------------------------------------------------------

def test_allocation_takes_the_jobs_project_so_its_time_can_be_invoiced(db):
    w = _world(db)
    allocation = _allocate(db, w)
    assert allocation.project_id == w.project.id and allocation.client_id == w.project.client_id


def test_placement_on_a_job_without_a_client_is_refused(db):
    w = _world(db)
    w.job.client_id = None
    w.job.project_id = None
    db.flush()
    with pytest.raises(AllocationNeedsClient):
        _allocate(db, w)


# ---- timesheet entries -----------------------------------------------------------------

def test_hours_only_inside_the_week_and_the_allocation(db):
    w = _world(db)
    allocation = _allocate(db, w, start=date(2026, 9, 9), end=date(2026, 9, 10))
    ts = timesheet_service.create_weekly_draft(db, allocation, date(2026, 9, 7), tenant_id=1)
    db.flush()
    with pytest.raises(timesheet_service.InvalidTimesheetEntry, match="outside this timesheet's week"):
        timesheet_service.upsert_entries(db, ts, [{"entry_date": date(2026, 9, 14), "hours": 8}])
    with pytest.raises(timesheet_service.InvalidTimesheetEntry, match="outside the allocation"):
        timesheet_service.upsert_entries(db, ts, [{"entry_date": date(2026, 9, 8), "hours": 8}])
    with pytest.raises(timesheet_service.InvalidTimesheetEntry, match="outside the allocation"):
        timesheet_service.upsert_entries(db, ts, [{"entry_date": date(2026, 9, 11), "hours": 8}])
    timesheet_service.upsert_entries(db, ts, [{"entry_date": date(2026, 9, 9), "hours": 8},
                                              {"entry_date": date(2026, 9, 10), "hours": 8}])
    assert float(ts.billable_hours) == 16


def test_one_timesheet_per_week_whatever_tenant_the_caller_passes(db):
    w = _world(db)
    allocation = _allocate(db, w)
    first = timesheet_service.create_weekly_draft(db, allocation, date(2026, 9, 7), tenant_id=1)
    db.flush()
    assert timesheet_service.create_weekly_draft(db, allocation, date(2026, 9, 7), tenant_id=None) is first


# ---- timesheet -> invoice --------------------------------------------------------------

def test_a_week_straddling_two_months_is_split_by_day_and_never_billed_twice(db):
    w = _world(db)
    allocation = _allocate(db, w)
    _week(db, allocation, date(2026, 9, 28), {date(2026, 9, 28): 8, date(2026, 9, 29): 8, date(2026, 9, 30): 8,
                                              date(2026, 10, 1): 8, date(2026, 10, 2): 8})
    september = invoices.generate_invoice(db, w.project, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30))
    db.commit()
    assert september.total_usd_cents == 24 * RATE
    with pytest.raises(invoices.AlreadyInvoiced):
        invoices.generate_invoice(db, w.project, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30))
    db.rollback()
    october = invoices.generate_invoice(db, w.project, period_start=date(2026, 10, 1), period_end=date(2026, 10, 31))
    db.commit()
    assert october.total_usd_cents == 16 * RATE  # 40h in total, each hour once


def test_hours_already_invoiced_are_never_billed_again_under_another_period(db):
    """A week invoiced whole under an earlier rule must not have its days billed again."""
    w = _world(db)
    allocation = _allocate(db, w)
    ts = _week(db, allocation, date(2026, 9, 28), {date(2026, 9, 28): 8, date(2026, 10, 1): 8})
    old = Invoice(tenant_id=1, project_id=w.project.id, client_id=w.client.id, billing_period_start=date(2026, 9, 1),
                  billing_period_end=date(2026, 9, 30), currency="USD", total_usd_cents=16 * RATE)
    db.add(old)
    db.flush()
    db.add(invoices.InvoiceLineItem(invoice_id=old.id, employee_id=w.worker.id, timesheet_id=ts.id, hours=16,
                                    rate_usd_cents=RATE, amount_usd_cents=16 * RATE))
    db.commit()
    with pytest.raises(invoices.NothingToInvoice):
        invoices.generate_invoice(db, w.project, period_start=date(2026, 10, 1), period_end=date(2026, 10, 31))


def test_invoice_is_issued_in_usd_because_every_amount_is_usd(db):
    w = _world(db, currency="INR")
    allocation = _allocate(db, w)
    _week(db, allocation, date(2026, 9, 7), {date(2026, 9, 7): 8})
    invoice = invoices.generate_invoice(db, w.project, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30))
    assert invoice.currency == "USD" and invoice.total_usd_cents == 8 * RATE


def test_time_on_another_clients_allocation_is_never_billed_to_this_client(db):
    w = _world(db)
    allocation = _allocate(db, w)
    _week(db, allocation, date(2026, 9, 7), {date(2026, 9, 7): 8})
    other = Client(tenant_id=1, company_name=f"Other {_uid()}", payment_terms_days=30)
    db.add(other)
    db.flush()
    allocation.client_id = other.id  # corrupted after creation
    db.commit()
    with pytest.raises(ValueError, match="different client"):
        invoices.generate_invoice(db, w.project, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30))


def test_generate_endpoint_cannot_reach_another_tenants_project(db):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.main import app
    from tests.hiring_fixtures import finance_approver

    w = _world(db)
    if db.query(Tenant).filter_by(id=2).first() is None:
        db.add(Tenant(id=2, name="other-tenant"))
        db.flush()
    w.project.tenant_id = 2
    user = finance_approver(db)
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    try:
        response = TestClient(app).post("/api/v1/invoices/generate", headers={"Authorization": "Bearer " + create_access_token(
            {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})},
            json={"project_id": w.project.id, "period_start": "2026-09-01", "period_end": "2026-09-30"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404


# ---- invoice -> payment -> revenue -----------------------------------------------------

def _paid_invoice(db, w):
    allocation = _allocate(db, w)
    _week(db, allocation, date(2026, 9, 7), {date(2026, 9, 7): 8})
    invoice = invoices.generate_invoice(db, w.project, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30))
    invoice.status = "SENT"
    db.commit()
    record_invoice_payment(db, invoice, paid_on=date(2026, 10, 5), amount_usd_cents=invoice.total_usd_cents,
                           reference="UTR1", recorded_by=None)
    return invoice


def test_a_paid_invoice_cannot_be_paid_again(db):
    invoice = _paid_invoice(db, _world(db))
    assert invoice.status == "PAID"
    with pytest.raises(BankReconciliationError, match="already paid"):
        record_invoice_payment(db, invoice, paid_on=date(2026, 10, 6), amount_usd_cents=invoice.total_usd_cents,
                               reference="UTR2", recorded_by=None)


def test_revenue_with_no_partner_raises_a_finance_task(db):
    invoice = _paid_invoice(db, _world(db, partner=False))
    revenue = recognize_revenue(db, invoice)
    assert revenue.partner_id is None
    assert db.query(Task).filter(Task.title == f"Revenue without a partner: invoice {invoice.id[:8]}").count() == 1


# ---- auto-invoicing never loses time ---------------------------------------------------

def test_a_month_approved_late_is_still_invoiced(db, queued):
    w = _world(db)
    allocation = _allocate(db, w)
    _week(db, allocation, date(2026, 8, 10), {date(2026, 8, 10): 8})
    run_auto_invoicing(db, today=date(2026, 10, 3))  # August is two months back
    decision = db.query(InvoiceAutomationDecision).filter_by(project_id=w.project.id, period_start=date(2026, 8, 1)).one()
    assert decision.decision == "PENDING_REVIEW"


def test_the_oldest_month_still_waiting_is_handed_to_finance(db, queued):
    w = _world(db)
    allocation = _allocate(db, w, start=date(2026, 7, 1))
    _week(db, allocation, date(2026, 7, 6), {date(2026, 7, 6): 8}, status="SUBMITTED")
    run_auto_invoicing(db, today=date(2026, 10, 3))  # window: Jul, Aug, Sep
    decision = db.query(InvoiceAutomationDecision).filter_by(project_id=w.project.id, period_start=date(2026, 7, 1)).one()
    assert decision.decision == "HELD" and "not APPROVED" in decision.reasons[0]
    assert db.query(Task).filter(Task.title == f"Invoice overdue: {w.project.name} Jul 2026").count() == 1


def test_billable_time_without_a_project_is_flagged_once(db, queued):
    w = _world(db)
    allocation = EmployeeAllocation(tenant_id=1, employee_id=w.worker.id, client_id=w.client.id, demand_id=w.job.jobID,
                                    billing_rate_usd_cents=RATE, status="ACTIVE", start_date=date(2026, 8, 1))
    db.add(allocation)
    db.flush()
    db.add(Timesheet(tenant_id=1, employee_id=w.worker.id, allocation_id=allocation.id,
                     week_starting_date=date(2026, 9, 7), total_hours=8, billable_hours=8, status="APPROVED"))
    db.commit()
    assert run_auto_invoicing(db, today=date(2026, 10, 3))["unlinked"] >= 1
    run_auto_invoicing(db, today=date(2026, 10, 4))
    assert db.query(Task).filter(Task.title.like(f"Billable time not invoiceable:%{allocation.id[:8]}%")).count() == 1


def test_auto_invoicing_runs_until_approved_then_once(db, queued):
    w = _world(db)
    allocation = _allocate(db, w)
    _week(db, allocation, date(2026, 9, 7), {date(2026, 9, 7): 8})
    run_auto_invoicing(db, today=date(2026, 10, 3))
    run_auto_invoicing(db, today=date(2026, 10, 4))
    assert db.query(Invoice).filter_by(project_id=w.project.id).count() == 1


# ---- endpoints: job client change, self-service submit --------------------------------

@pytest.fixture
def api(db):
    """An internal user holding every resource permission (RBAC is not what these tests are about)."""
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.main import app
    from tests.hiring_fixtures import finance_approver

    user = finance_approver(db)
    db.commit()
    headers = {"Authorization": "Bearer " + create_access_token(
        {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}
    app.dependency_overrides[get_db] = lambda: db
    rbac = "app.services.role_template_permission_service.RoleTemplatePermissionService.has_permission"
    with patch(rbac, return_value=True):
        yield TestClient(app), headers, user
    app.dependency_overrides.clear()


def test_changing_a_jobs_client_rechecks_its_project(db, api):
    client, headers, _ = api
    w = _world(db)
    other = Client(tenant_id=1, company_name=f"Other {_uid()}", payment_terms_days=30)
    db.add(other)
    db.commit()
    response = client.put(f"/api/v1/jobs/update_job/{w.job.jobID}", headers=headers, json={"client_id": other.id})
    assert response.status_code == 400 and "project must belong" in response.json()["detail"]
    db.rollback()  # what the request's own session does when it raises
    assert db.get(Jobs, w.job.jobID).client_id == w.client.id


def test_self_service_submit_twice_is_a_409_not_a_500(db, api):
    client, headers, user = api
    w = _world(db)
    w.worker.wros_user_id = user.UserID
    allocation = _allocate(db, w)
    monday = date.today() - timedelta(days=date.today().weekday())  # submit refuses weeks > 4 weeks old
    ts = _week(db, allocation, monday, {monday: 8}, status="DRAFT")
    first = client.post(f"/api/v1/my/timesheet/{ts.id}/submit", headers=headers)
    assert first.status_code == 200, first.text
    again = client.post(f"/api/v1/my/timesheet/{ts.id}/submit", headers=headers)
    assert again.status_code == 409
