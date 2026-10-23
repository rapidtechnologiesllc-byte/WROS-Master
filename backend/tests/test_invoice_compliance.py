"""Invoice compliance and AR by terms, work orders / PO on invoice (CEO 2026-10-23, gaps 3 and 12):
a gapless number per issuing company stored at generation, the PO printed and stored, hours after a
PO's end refused, client-approval-required weeks refused, due date = sent + payment terms, AR chased
and aged by due date, PO expiry alerts to Finance, and the work order routes."""
import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnit
from app.models.client import Client, ClientContact
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.invoice import Invoice
from app.models.location import Location
from app.models.project import Project
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.user import Jobs
from app.models.work_order import WorkOrder
from app.services import invoice_service as invoices
from app.services.ar_followup_service import ar_aging, scan_overdue_invoices
from app.services.invoice_automation_service import run_auto_invoicing
from app.services.invoice_numbering import backfill, next_number
from app.services.message_handlers.send_invoice_email_handler import render_invoice_email
from app.services.work_order_service import run_po_expiry_alerts
from tests.hiring_fixtures import finance_approver, full_access_role
from tests.test_core_certification import _h, _user

RATE = 9000
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
def api(db):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True):
        yield TestClient(app)
    app.dependency_overrides.clear()


def _company(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    company = Location(tenant_id=1, name=f"BX-{_uid()}", company_seq=int(uuid.uuid4().int % 100000))
    db.add(company)
    db.flush()
    return company


def _setup(db, *, company=None, flagged=False, terms=30):
    """A client (optionally contracting through `company`) with one project, job and placement."""
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    unit = BusinessUnit(tenant_id=1, name=f"bu-{_uid()}", display_name="BU")
    db.add(unit)
    db.flush()
    client = Client(tenant_id=1, company_name=f"Client {_uid()}", business_unit_id=unit.id, payment_terms_days=terms,
                    contracting_company_id=company.id if company else None,
                    requires_client_timesheet_approval=flagged)
    db.add(client)
    db.flush()
    db.add(ClientContact(tenant_id=1, client_id=client.id, name="AP", email=f"ap{_uid()}@client.example",
                         role_type="ACCOUNTS", is_primary=True))
    job = Jobs(tenant_id=1, client_id=client.id, jobTitle="Dev", jobDescription="d", jobSkills="x", jobExperience="5",
               jobLocation="Remote")
    project = Project(tenant_id=1, client_id=client.id, name=f"Project {_uid()}", delivery_engine="CORE")
    db.add_all([job, project])
    db.flush()
    worker = Employee(tenant_id=1, first_name="Sam", last_name="Lee", email=f"s{_uid()}@x.com",
                      joining_date=date(2025, 1, 1), status="ALLOCATED", bu_id=unit.id)
    db.add(worker)
    db.flush()
    allocation = EmployeeAllocation(tenant_id=1, employee_id=worker.id, client_id=client.id, demand_id=job.jobID,
                                    project_id=project.id, billing_rate_usd_cents=RATE, status="ACTIVE",
                                    start_date=date(2025, 1, 1))
    db.add(allocation)
    db.flush()
    return SimpleNamespace(client=client, project=project, job=job, worker=worker, allocation=allocation, unit=unit)


def _week(db, s, monday, hours_per_day=8, status="APPROVED", client_status=None):
    sheet = Timesheet(tenant_id=1, employee_id=s.worker.id, allocation_id=s.allocation.id, week_starting_date=monday,
                      total_hours=5 * hours_per_day, billable_hours=5 * hours_per_day, non_billable_hours=0,
                      status=status, client_approval_status=client_status)
    db.add(sheet)
    db.flush()
    for i in range(5):
        db.add(TimesheetEntry(timesheet_id=sheet.id, entry_date=monday + timedelta(days=i), hours=hours_per_day,
                              entry_type="BILLABLE"))
    db.flush()
    return sheet


def _generate(db, s):
    return invoices.generate_invoice(db, s.project, period_start=SEPT[0], period_end=SEPT[1], tenant_id=1)


def _work_order(db, s, *, end, po="PO-4711", status="ACTIVE"):
    wo = WorkOrder(tenant_id=1, po_number=po, demand_id=s.job.jobID, client_id=s.client.id,
                   billing_rate_usd_cents=RATE, start_date=date(2026, 1, 1), end_date=end, status=status)
    db.add(wo)
    db.flush()
    return wo


# ------------------------------------------------------------------------------ numbering

def test_numbers_are_sequential_per_issuing_company_and_stored(db):
    bx_us, bx_in = _company(db), _company(db)
    a, b, c = _setup(db, company=bx_us), _setup(db, company=bx_us), _setup(db, company=bx_in)
    for s in (a, b, c):
        _week(db, s, date(2026, 9, 7))
    first, second, other = _generate(db, a), _generate(db, b), _generate(db, c)
    assert (first.issuing_company_id, second.issuing_company_id, other.issuing_company_id) == (bx_us.id, bx_us.id, bx_in.id)
    assert (first.invoice_seq, second.invoice_seq, other.invoice_seq) == (1, 2, 1)
    assert first.invoice_number == f"INV-{bx_us.company_code}-000001"
    assert second.invoice_number == f"INV-{bx_us.company_code}-000002"
    assert other.invoice_number == f"INV-{bx_in.company_code}-000001"


def test_a_tenant_issued_invoice_has_its_own_series(db):
    s = _setup(db)
    _week(db, s, date(2026, 9, 7))
    invoice = _generate(db, s)
    assert invoice.issuing_company_id is None and invoice.invoice_number.startswith("INV-T1-")


def test_the_series_is_locked_and_gapless(test_db_engine):
    """A second generation waits on the first one's series lock; a rolled-back number is reused."""
    key_tenant = None  # its own series ("tenant:None"), nothing else uses it
    first = Session(bind=test_db_engine.connect())
    second = Session(bind=test_db_engine.connect())
    try:
        assert next_number(first, key_tenant, None) >= 1
        taken = first.execute(text("SELECT last_number FROM app_schema.invoice_number_sequences "
                                   "WHERE issuer_key = 'tenant:None'")).scalar()
        second.execute(text("SET lock_timeout = '300ms'"))
        with pytest.raises(OperationalError):
            next_number(second, key_tenant, None)  # blocked by the first transaction's lock
        second.rollback()
        first.rollback()  # the first generation failed: its number goes back
        assert next_number(second, key_tenant, None) == taken
    finally:
        first.rollback()
        second.rollback()
        first.close()
        second.close()


def test_backfill_numbers_old_invoices_in_creation_order_and_dates_sent_ones(db):
    company = _company(db)
    s = _setup(db, company=company, terms=45)
    old = Invoice(tenant_id=1, project_id=s.project.id, client_id=s.client.id, billing_period_start=date(2026, 7, 1),
                  billing_period_end=date(2026, 7, 31), status="SENT", total_usd_cents=100,
                  created_at=datetime(2026, 8, 1), sent_at=datetime(2026, 8, 2, 10))
    newer = Invoice(tenant_id=1, project_id=s.project.id, client_id=s.client.id, billing_period_start=date(2026, 8, 1),
                    billing_period_end=date(2026, 8, 31), status="DRAFT", total_usd_cents=200,
                    created_at=datetime(2026, 9, 1))
    db.add_all([newer, old])
    db.flush()
    assert backfill(db) >= 2
    assert (old.invoice_seq, newer.invoice_seq) == (1, 2) and old.issuing_company_id == company.id
    assert old.due_date == date(2026, 9, 16) and newer.due_date is None
    assert backfill(db) == 0  # nothing left to number


# ------------------------------------------------------------------------------ PO on the invoice

def test_po_is_printed_and_stored_on_the_invoice(db):
    s = _setup(db, company=_company(db))
    s.allocation.work_order_id = _work_order(db, s, end=date(2026, 12, 31)).id
    _week(db, s, date(2026, 9, 7))
    invoice = _generate(db, s)
    assert invoice.po_numbers == "PO-4711"
    from app.models.invoice import InvoiceLineItem

    assert {li.po_number for li in db.query(InvoiceLineItem).filter_by(invoice_id=invoice.id)} == {"PO-4711"}
    approver = finance_approver(db)
    invoices.approve_invoice(db, invoice, approved_by=approver.UserID)
    email = render_invoice_email(db, invoice)
    assert invoice.invoice_number in email["subject"] and "PO-4711" in email["subject"]
    assert invoice.invoice_number in email["html"] and "PO-4711" in email["html"]
    assert invoice.id.split("-")[0].upper() not in email["subject"]


def test_hours_after_the_po_end_are_not_invoiced(db):
    s = _setup(db)
    s.allocation.work_order_id = _work_order(db, s, end=date(2026, 9, 9)).id  # ends on the Wednesday
    _week(db, s, date(2026, 9, 7))
    with pytest.raises(invoices.PurchaseOrderExpired) as exc:
        _generate(db, s)
    assert "PO-4711 ended 2026-09-09: 16h on 2026-09-10, 2026-09-11" in str(exc.value)


def test_auto_invoicing_holds_a_po_overrun_for_finance(db):
    finance_approver(db)
    s = _setup(db)
    s.allocation.work_order_id = _work_order(db, s, end=date(2026, 9, 9)).id
    _week(db, s, date(2026, 9, 7))
    db.commit()
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True):
        run_auto_invoicing(db, today=date(2026, 10, 3))
    task = db.query(Task).filter(Task.title == f"Invoice held: {s.project.name} Sep 2026").one()
    assert "PO-4711" in task.description
    assert db.query(Invoice).filter_by(project_id=s.project.id).count() == 0


# ------------------------------------------------------------------------------ client approval gate

def test_weeks_without_client_approval_are_refused_with_the_reason(db):
    s = _setup(db, flagged=True)
    _week(db, s, date(2026, 9, 7), client_status="CLIENT_APPROVED")
    _week(db, s, date(2026, 9, 14), client_status="CLIENT_PENDING")
    with pytest.raises(invoices.ClientApprovalMissing) as exc:
        _generate(db, s)
    assert "week of 2026-09-14 (pending" in str(exc.value) and "2026-09-07" not in str(exc.value)


def test_client_approved_weeks_invoice_and_unflagged_clients_are_unaffected(db):
    s = _setup(db, flagged=True)
    _week(db, s, date(2026, 9, 7), client_status="CLIENT_APPROVED")
    assert _generate(db, s).total_usd_cents == 40 * RATE
    plain = _setup(db)
    _week(db, plain, date(2026, 9, 7))
    assert _generate(db, plain).total_usd_cents == 40 * RATE


def test_auto_invoicing_waits_for_the_client_and_tells_finance_once(db):
    finance_approver(db)
    s = _setup(db, flagged=True)
    sheet = _week(db, s, date(2026, 9, 7), client_status="CLIENT_PENDING")
    db.commit()
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True):
        run_auto_invoicing(db, today=date(2026, 10, 3))
        run_auto_invoicing(db, today=date(2026, 10, 4))
    title = f"Waiting for client timesheet approval: {s.project.name} Sep 2026"
    waiting = db.query(Task).filter(Task.title == title).all()
    assert len(waiting) == 1 and sheet.id in waiting[0].description
    assert db.query(Invoice).filter_by(project_id=s.project.id).count() == 0

    sheet.client_approval_status = "CLIENT_APPROVED"
    db.commit()
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True):
        run_auto_invoicing(db, today=date(2026, 10, 5))
    assert db.query(Invoice).filter_by(project_id=s.project.id).count() == 1
    assert db.get(Task, waiting[0].id).status == "COMPLETED"


def test_generate_endpoint_surfaces_the_reason(api, db):
    s = _setup(db, flagged=True)
    _week(db, s, date(2026, 9, 7), client_status="CLIENT_PENDING")
    admin = _user(db, full_access_role(db), "Finance")
    db.commit()
    res = api.post("/api/v1/invoices/generate", headers=_h(admin),
                   json={"project_id": s.project.id, "period_start": "2026-09-01", "period_end": "2026-09-30"})
    assert res.status_code == 409 and "not client-approved" in res.json()["detail"]


# ------------------------------------------------------------------------------ due date and AR

def _sent(db, s, *, sent_days_ago, total=1000):
    invoice = Invoice(tenant_id=1, project_id=s.project.id, client_id=s.client.id,
                      billing_period_start=date(2026, 8, 1), billing_period_end=date(2026, 8, 31),
                      status="APPROVED", total_usd_cents=total, invoice_number=f"INV-T-{_uid()}")
    db.add(invoice)
    db.flush()
    invoices.mark_invoice_sent(db, invoice, sent_at=datetime.utcnow() - timedelta(days=sent_days_ago))
    db.flush()
    return invoice


def test_due_date_is_sent_date_plus_payment_terms(db):
    s = _setup(db, terms=45)
    invoice = _sent(db, s, sent_days_ago=0)
    assert invoice.due_date == datetime.utcnow().date() + timedelta(days=45)


def test_ar_chases_by_payment_terms_not_a_fixed_30_days(db):
    net60, net15 = _setup(db, terms=60), _setup(db, terms=15)
    not_due = _sent(db, net60, sent_days_ago=40)
    late = _sent(db, net15, sent_days_ago=20)
    rows = {r["invoice_id"]: r for r in scan_overdue_invoices(db)}
    assert not_due.id not in rows
    assert rows[late.id]["days_overdue"] == 5 and rows[late.id]["due_date"] == late.due_date


def test_ar_aging_buckets_by_client(db, api):
    s = _setup(db, terms=30)
    current = _sent(db, s, sent_days_ago=10, total=100)
    b1 = _sent(db, s, sent_days_ago=45, total=200)    # 15 days past due
    b3 = _sent(db, s, sent_days_ago=100, total=300)   # 70 days past due
    b4 = _sent(db, s, sent_days_ago=150, total=400)   # 120 days past due
    aging = ar_aging(db, [current, b1, b3, b4])
    assert aging["buckets"] == ["current", "1-30", "31-60", "61-90", "90+"]
    (row,) = aging["clients"]
    assert row["buckets"] == {"current": 100, "1-30": 200, "31-60": 0, "61-90": 300, "90+": 400}
    assert row["total_usd_cents"] == 1000 and aging["total_usd_cents"] == 1000
    admin = _user(db, full_access_role(db), "Finance")
    db.commit()
    res = api.get("/api/v1/invoices/ar/aging", headers=_h(admin))
    assert res.status_code == 200, res.text
    mine = [c for c in res.json()["clients"] if c["client_id"] == s.client.id]
    assert mine and mine[0]["buckets"]["90+"] == 400


# ------------------------------------------------------------------------------ work orders

def test_po_expiry_alert_gives_finance_one_task(db):
    finance_approver(db)
    s = _setup(db)
    soon = _work_order(db, s, end=date.today() + timedelta(days=10), po="PO-SOON")
    _work_order(db, s, end=date.today() + timedelta(days=200), po="PO-LATER")
    s.allocation.work_order_id = soon.id
    db.commit()
    run_po_expiry_alerts(db)
    run_po_expiry_alerts(db)
    tasks = db.query(Task).filter(Task.title.like("PO expiring:%")).all()
    titles = [t.title for t in tasks]
    assert sum("PO-SOON" in t for t in titles) == 1 and not any("PO-LATER" in t for t in titles)
    task = next(t for t in tasks if "PO-SOON" in t.title)
    assert task.category == "FINANCE" and "1 active placement" in task.description


def test_work_order_routes_and_placement_link(api, db):
    s = _setup(db)
    admin = _user(db, full_access_role(db), "Delivery")
    db.commit()
    res = api.post("/api/v1/work-orders", headers=_h(admin), json={
        "po_number": "PO-9", "demand_id": s.job.jobID, "client_id": s.client.id, "billing_rate_usd_cents": RATE,
        "start_date": "2026-01-01", "end_date": "2026-06-30"})
    assert res.status_code == 200, res.text
    wo = res.json()
    extended = api.patch(f"/api/v1/work-orders/{wo['id']}", headers=_h(admin), json={"end_date": "2026-12-31"})
    assert extended.status_code == 200 and extended.json()["end_date"] == "2026-12-31"
    assert api.post(f"/api/v1/work-orders/{wo['id']}/pause", headers=_h(admin)).json()["status"] == "PAUSED"
    assert api.post(f"/api/v1/work-orders/{wo['id']}/resume", headers=_h(admin)).json()["status"] == "ACTIVE"
    listed = api.get(f"/api/v1/work-orders?client_id={s.client.id}", headers=_h(admin)).json()["work_orders"]
    assert [w["id"] for w in listed] == [wo["id"]]

    link = api.put(f"/api/v1/allocations/{s.allocation.id}/client-billing", headers=_h(admin),
                   json={"work_order_id": wo["id"]})
    assert link.status_code == 200, link.text
    assert link.json()["po_number"] == "PO-9"
    assert api.get(f"/api/v1/work-orders/{wo['id']}", headers=_h(admin)).json()["placement_count"] == 1

    other = _setup(db)
    db.commit()
    foreign = api.put(f"/api/v1/allocations/{other.allocation.id}/client-billing", headers=_h(admin),
                      json={"work_order_id": wo["id"]})
    assert foreign.status_code == 422 and "different client" in foreign.json()["detail"]
    ended = api.post(f"/api/v1/work-orders/{wo['id']}/end", headers=_h(admin), json={})
    assert ended.json()["status"] == "ENDED"
    assert api.get("/api/v1/work-orders/does-not-exist", headers=_h(admin)).status_code == 404


def test_a_work_order_for_another_clients_job_is_refused(api, db):
    s, other = _setup(db), _setup(db)
    admin = _user(db, full_access_role(db), "Delivery")
    db.commit()
    res = api.post("/api/v1/work-orders", headers=_h(admin), json={
        "po_number": "PO-X", "demand_id": other.job.jobID, "client_id": s.client.id, "billing_rate_usd_cents": RATE,
        "start_date": "2026-01-01"})
    assert res.status_code == 400 and "different client" in res.json()["detail"]
