"""Sub-vendor invoices, pay-when-paid and the P&L (CEO 2026-11-02: "unable to add a sub vendor invoice
which we need to do the payment ... make sure we got the payment from the client and then initiate the
payment to the sub vendor" / "make sure it is connected to the full P&L" / contractors "will still be
filling timesheet but only have limited access")."""
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnit
from app.models.client import Client
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.org_structure import OrgRole
from app.models.project import Project
from app.models.role_template import RoleTemplate
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.timesheet import Timesheet
from app.models.user import Jobs, Users
from app.services import invoice_service as invoices
from app.services import revenue_chain_service as chain
from app.services import vendor_invoice_service as vendors
from app.services.vendor_invoice_service import VendorInvoiceError
from tests.hiring_fixtures import finance_approver
from tests.scope_fixtures import ApiClient

BILL_RATE = 10_000  # $100/h to the client
VENDOR_RATE = 7_000  # $70/h to the vendor
SEPT = (date(2026, 9, 1), date(2026, 9, 30))


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
def w(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    finance = finance_approver(db)
    unit = BusinessUnit(tenant_id=1, name=f"axion-{_uid()}", display_name="Axion")
    db.add(unit)
    db.flush()
    client = Client(tenant_id=1, company_name="Builders Insurance", business_unit_id=unit.id, payment_terms_days=30)
    db.add(client)
    db.flush()
    job = Jobs(tenant_id=1, client_id=client.id, jobTitle="Guidewire Developer", jobDescription="d",
               jobSkills="Guidewire", jobExperience="5", jobLocation="Remote")
    project = Project(tenant_id=1, client_id=client.id, name="BillingCenter", delivery_engine="CORE")
    # the Contractor role startup creates (db_contract._initialize_contractor_role), else one like it
    role = db.query(OrgRole).filter_by(tenant_id=1, name="Contractor").first()
    if role is None:
        template = RoleTemplate(tenant_id=1, name=f"Contractor-{_uid()}", display_name="Contractor", hierarchy_level=1)
        db.add(template)
        db.flush()
        db.add(OrgRole(tenant_id=1, name="Contractor", hierarchy_level=1, role_template_id=template.id))
    else:
        template = db.get(RoleTemplate, role.role_template_id)
    wider = RoleTemplate(tenant_id=1, name=f"consultant-{_uid()}", display_name="Consultant", hierarchy_level=4)
    db.add(wider)
    db.flush()
    login = Users(UserID=f"C-{_uid()}", UserName="Ravi Contractor", UserEmail=f"ravi{_uid()}@x.com", UserPassword="h",
                  UserRole="Employee", tenant_id=1, job_title="Consultant",
                  role_template_id=wider.id)
    db.add_all([job, project, login])
    db.flush()
    worker = Employee(tenant_id=1, first_name="Ravi", last_name="Kumar", email=f"ravi{_uid()}@x.com",
                      joining_date=date(2025, 1, 1), status="ALLOCATED", bu_id=unit.id, wros_user_id=login.UserID)
    db.add(worker)
    db.flush()
    allocation = EmployeeAllocation(tenant_id=1, employee_id=worker.id, client_id=client.id, demand_id=job.jobID,
                                    project_id=project.id, billing_rate_usd_cents=BILL_RATE, status="ACTIVE",
                                    start_date=date(2025, 1, 1))
    db.add(allocation)
    db.flush()
    sheets = [Timesheet(tenant_id=1, employee_id=worker.id, allocation_id=allocation.id, week_starting_date=week,
                        total_hours=40, billable_hours=40, non_billable_hours=0, status="APPROVED")
              for week in (date(2026, 9, 7), date(2026, 9, 14))]
    db.add_all(sheets)
    db.commit()
    vendor = vendors.create_sub_vendor(db, finance, company_name=f"Nimbus Staffing {_uid()}",
                                       contact_email="ap@nimbus.example")
    vendors.set_contractor(db, finance, worker, sub_vendor_id=vendor.id, hourly_rate_usd_cents=VENDOR_RATE)
    db.commit()
    return SimpleNamespace(finance=finance, client=client, project=project, worker=worker, login=login,
                           vendor=vendor, sheets=sheets, template=template)


def _vendor_invoice(db, w, amount=2 * 40 * VENDOR_RATE, number="NIM-101", **kw):
    invoice = vendors.create_vendor_invoice(db, w.finance, sub_vendor_id=w.vendor.id, vendor_invoice_number=number,
                                            invoice_date=date(2026, 10, 2), period_start=SEPT[0], period_end=SEPT[1],
                                            amount_usd_cents=amount, **kw)
    db.commit()
    return invoice


def _client_invoice(db, w):
    invoice = invoices.generate_invoice(db, w.project, period_start=date(2026, 9, 7), period_end=date(2026, 9, 14),
                                        tenant_id=1)
    invoices.approve_invoice(db, invoice, approved_by=w.finance.UserID)
    invoices.mark_invoice_sent(db, invoice)
    db.commit()
    return invoice


def test_a_contractor_has_the_contractor_role_only(db, w):
    assert w.worker.employment_type == "CONTRACT" and w.worker.sub_vendor_id == w.vendor.id
    db.refresh(w.login)
    assert (w.login.job_title, w.login.role_template_id) == ("Contractor", w.template.id)


def test_the_vendor_invoice_takes_the_approved_timesheets_once(db, w):
    invoice = _vendor_invoice(db, w)
    item = vendors.to_item(db, invoice)
    assert item["expected_usd_cents"] == 2 * 40 * VENDOR_RATE and item["variance_usd_cents"] == 0
    assert len(item["lines"]) == 2
    with pytest.raises(VendorInvoiceError, match="already recorded"):
        _vendor_invoice(db, w)
    with pytest.raises(VendorInvoiceError, match="No approved, not yet invoiced timesheets"):
        _vendor_invoice(db, w, number="NIM-102")
    vendors.reject_vendor_invoice(db, w.finance, invoice, reason="wrong rate")
    db.commit()
    assert _vendor_invoice(db, w, number="NIM-103").status == "RECEIVED"  # rejected frees the weeks


def test_a_different_amount_needs_a_note_to_approve(db, w):
    invoice = _vendor_invoice(db, w, amount=2 * 40 * VENDOR_RATE + 5_000)
    with pytest.raises(VendorInvoiceError, match="add a note"):
        vendors.approve_vendor_invoice(db, w.finance, invoice)
    assert vendors.approve_vendor_invoice(db, w.finance, invoice, note="travel agreed").status == "APPROVED"


def test_the_vendor_is_paid_only_after_the_client_pays(db, w):
    invoice = _vendor_invoice(db, w)
    vendors.approve_vendor_invoice(db, w.finance, invoice)
    db.commit()
    with pytest.raises(VendorInvoiceError, match="not yet invoiced to the client"):
        vendors.pay_vendor_invoice(db, w.finance, invoice, paid_on=date(2026, 10, 20), reference="TRF-1")
    client_invoice = _client_invoice(db, w)
    with pytest.raises(VendorInvoiceError, match=r"not yet paid: .*\(sent\)"):
        vendors.pay_vendor_invoice(db, w.finance, invoice, paid_on=date(2026, 10, 20), reference="TRF-1")

    invoices.mark_invoice_paid(db, client_invoice)  # the client pays: Finance is told the vendor can be paid
    db.commit()
    task = db.query(Task).filter(Task.title.like(f"Pay {w.vendor.company_name} invoice NIM-101%")).one()
    assert task.assigned_to_user_id == w.finance.UserID and task.priority == "HIGH"
    paid = vendors.pay_vendor_invoice(db, w.finance, invoice, paid_on=date(2026, 10, 20), reference="TRF-1")
    assert (paid.status, paid.payment_reference) == ("PAID", "TRF-1")


def test_the_pnl_charges_the_vendor_cost_not_payroll(db, w):
    report = chain.pnl(db, start=SEPT[0], end=SEPT[1], tenant_id=1)
    org = report["org"] if "org" in report else report
    accrued = 2 * 40 * VENDOR_RATE
    assert org["vendor_cost_usd_cents"] == accrued  # before the vendor invoices: hours x vendor rate
    assert org["delivery_cost_usd_cents"] == accrued and org["bench_cost_usd_cents"] == 0
    assert org["cost_data_complete"] is True  # a contractor has no payroll and is not "missing"

    invoice = _vendor_invoice(db, w, amount=accrued + 5_000, note="agreed extra")
    vendors.approve_vendor_invoice(db, w.finance, invoice)
    client_invoice = _client_invoice(db, w)
    invoices.mark_invoice_paid(db, client_invoice)
    vendors.pay_vendor_invoice(db, w.finance, invoice, paid_on=date(2026, 10, 20), reference="TRF-2")
    db.commit()
    org = chain.pnl(db, start=SEPT[0], end=SEPT[1], tenant_id=1)
    org = org["org"] if "org" in org else org
    assert org["vendor_invoiced_usd_cents"] == accrued and org["vendor_paid_usd_cents"] == accrued
    assert org["margin_usd_cents"] == 2 * 40 * (BILL_RATE - VENDOR_RATE)


def test_the_api_records_and_refuses_with_the_reason(db, w):
    api = ApiClient(db)
    try:
        headers = ApiClient.headers(w.finance)
        response = api.client.post("/api/v1/vendor-invoices", headers=headers, json={
            "sub_vendor_id": w.vendor.id, "vendor_invoice_number": "NIM-200", "invoice_date": "2026-10-02",
            "period_start": "2026-09-01", "period_end": "2026-09-30", "amount_usd_cents": 2 * 40 * VENDOR_RATE})
        assert response.status_code == 201, response.text
        invoice_id = response.json()["id"]
        assert api.client.post(f"/api/v1/vendor-invoices/{invoice_id}/approve", headers=headers).status_code == 200
        refused = api.client.post(f"/api/v1/vendor-invoices/{invoice_id}/pay", headers=headers,
                                  json={"paid_on": "2026-10-20", "reference": "TRF-9"})
        assert refused.status_code == 409 and "client has not paid" in refused.json()["detail"]
        run = api.client.post("/api/v1/invoices/run-automation", headers=headers)  # invoicing is automatic
        assert run.status_code == 200 and {"awaiting", "waiting", "held"} <= set(run.json())
        listing = api.client.get("/api/v1/vendor-invoices", headers=headers).json()
        assert listing["owed_usd_cents"] == 2 * 40 * VENDOR_RATE and listing["payable_now_usd_cents"] == 0
    finally:
        api.close()
