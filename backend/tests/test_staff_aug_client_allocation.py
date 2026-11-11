"""Staff Aug is one person's time and materials at a client, not a project (CEO 2026-11-11): the
allocation names the client (required) and, optionally, one of that client's jobs. With no job --
an existing placement recorded after the fact -- it carries its own role and bill rate, and the
whole chain still runs: allocation -> timesheet -> invoice (billed to the client, no project) ->
payment -> revenue -> P&L."""
from datetime import date, datetime

import pytest

from app.models.client import Client
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.invoice_automation import InvoiceAutomationDecision
from app.models.revenue import Revenue
from app.services import invoice_service, timesheet_service
from app.services import revenue_chain_service as chain
from app.services.invoice_automation_service import run_auto_invoicing
from tests import factories
from tests.test_allocation_api import api, world  # noqa: F401 -- fixtures

SEPT = (date(2026, 9, 1), date(2026, 9, 30))


def _body(world, **overrides):
    body = {"employee_id": world.employee.id, "client_id": world.client.id, "role": "Guidewire Developer",
            "billing_rate_usd_cents": 9000, "start_date": "2026-09-01"}
    body.update(overrides)
    return body


def _staff_aug_client(db, world):
    """A Staff Aug client of the same business unit, with no job and no project."""
    client = Client(tenant_id=1, company_name=f"Staff Aug {factories.uid()}", business_unit_id=world.unit.id,
                    line_type="SPECIALITY", payment_terms_days=30)
    db.add(client)
    db.commit()
    return client


def test_staff_aug_needs_only_the_client(api, world, db):
    client = _staff_aug_client(db, world)
    response = api.post(world.admin, "/api/v1/allocations", json=_body(world, client_id=client.id))
    assert response.status_code == 200, response.text
    item = response.json()
    assert (item["client_id"], item["demand_id"], item["project_id"]) == (client.id, None, None)
    assert item["demand_job_title"] == "Guidewire Developer" and item["billing_rate_usd_cents"] == 9000
    assert item["status"] == "ACTIVE"
    db.expire_all()
    assert db.query(Employee).filter(Employee.id == world.employee.id).one().status == "ALLOCATED"
    listed = api.get(world.admin, f"/api/v1/allocations?client_id={client.id}").json()["allocations"]
    assert [a["id"] for a in listed] == [item["id"]]


def test_without_a_job_the_role_and_the_bill_rate_are_required(api, world, db):
    client = _staff_aug_client(db, world)
    assert api.post(world.admin, "/api/v1/allocations", json=_body(world, client_id=client.id, role=" ")).status_code == 422
    no_rate = api.post(world.admin, "/api/v1/allocations",
                       json=_body(world, client_id=client.id, billing_rate_usd_cents=None))
    assert no_rate.status_code == 422 and "bill rate" in no_rate.text
    assert api.post(world.admin, "/api/v1/allocations", json=_body(world, client_id="nope")).status_code == 404
    nothing = api.post(world.admin, "/api/v1/allocations", json=_body(world, client_id=None))
    assert nothing.status_code == 422


def test_a_job_of_another_client_is_refused(api, world, db):
    other = _staff_aug_client(db, world)
    response = api.post(world.admin, "/api/v1/allocations",
                        json=_body(world, client_id=other.id, demand_id=world.job.jobID))
    assert response.status_code == 422 and "different client" in response.text
    assert db.query(EmployeeAllocation).filter(EmployeeAllocation.employee_id == world.employee.id).count() == 0


def test_the_client_with_one_of_its_jobs_still_allocates_to_the_job(api, world):
    response = api.post(world.admin, "/api/v1/allocations",
                        json=_body(world, demand_id=world.job.jobID, role=None))
    assert response.status_code == 200, response.text
    assert response.json()["demand_id"] == world.job.jobID


def test_the_form_lists_clients_and_each_jobs_client(api, world, db):
    client = _staff_aug_client(db, world)
    dropdowns = api.get(world.admin, "/api/v1/allocations/dropdowns/for-create").json()
    assert {world.client.id, client.id} <= {c["id"] for c in dropdowns["clients"]}
    job = next(j for j in dropdowns["demands"] if j["id"] == world.job.jobID)
    assert job["client_id"] == world.client.id  # the form shows only the picked client's jobs


def test_margin_preview_for_the_client_alone(api, world, db):
    client = _staff_aug_client(db, world)
    response = api.post(world.admin, "/api/v1/allocations/margin-preview",
                        json={"employee_id": world.employee.id, "client_id": client.id, "role": "Dev",
                              "billing_rate_usd_cents": 9000})
    assert response.status_code == 200, response.text
    assert "margin_check" in response.json()


def test_a_client_only_allocation_can_be_edited_and_ended(api, world, db):
    client = _staff_aug_client(db, world)
    item = api.post(world.admin, "/api/v1/allocations", json=_body(world, client_id=client.id)).json()
    edited = api.patch(world.admin, f"/api/v1/allocations/{item['id']}",
                       json={"end_date": "2027-06-30", "reason": "Client extended the engagement"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["allocation"]["end_date"] == "2027-06-30"
    ended = api.post(world.admin, f"/api/v1/allocations/{item['id']}/end", json={"end_date": "2026-12-31"})
    assert ended.status_code == 200, ended.text
    assert ended.json()["status"] == "ENDED"


def _approved_week(db, allocation, monday, hours=8):
    sheet = timesheet_service.create_weekly_draft(db, allocation, monday, tenant_id=1)
    db.flush()
    timesheet_service.upsert_entries(db, sheet, [{"entry_date": monday, "hours": hours, "entry_type": "BILLABLE"}])
    sheet.status = "APPROVED"
    db.commit()
    return sheet


def test_client_only_allocation_runs_through_timesheet_invoice_payment_revenue_and_pnl(api, world, db):
    client = _staff_aug_client(db, world)
    item = api.post(world.admin, "/api/v1/allocations", json=_body(world, client_id=client.id)).json()
    allocation = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == item["id"]).one()
    assert allocation.project_id is None and allocation.demand_id is None

    # timesheet
    sheet = _approved_week(db, allocation, date(2026, 9, 7))
    lines = [line for line in chain.chain_lines(db, start=SEPT[0], end=SEPT[1], tenant_id=1)
             if line["timesheet_id"] == sheet.id]
    assert len(lines) == 1
    line = lines[0]
    assert (line["client_id"], line["job_id"], line["project_id"]) == (client.id, None, None)
    assert line["job_title"] == "Guidewire Developer"
    assert line["unbilled_usd_cents"] == 8 * 9000 and line["flags"] == [] or "NO_COST_DATA" in line["flags"]
    assert "NO_PROJECT_CANNOT_INVOICE" not in line["flags"]

    # invoice: billed to the client, no project
    response = api.post(world.admin, "/api/v1/invoices/generate",
                        json={"client_id": client.id, "period_start": "2026-09-01", "period_end": "2026-09-30"})
    assert response.status_code == 200, response.text
    drafted = response.json()
    assert drafted["project_id"] is None and drafted["client_id"] == client.id
    assert drafted["total_usd_cents"] == 8 * 9000 and drafted["invoice_number"]
    assert [li["timesheet_id"] for li in drafted["line_items"]] == [sheet.id]
    # never billed twice
    with pytest.raises(invoice_service.AlreadyInvoiced):
        invoice_service.generate_invoice(db, None, client=client, period_start=SEPT[0], period_end=SEPT[1])

    # payment -> revenue
    invoice = db.query(Invoice).filter(Invoice.id == drafted["id"]).one()
    invoice.status, invoice.sent_at = "SENT", datetime(2026, 10, 2)
    db.flush()
    invoice_service.mark_invoice_paid(db, invoice, paid_at=datetime(2026, 10, 20))
    db.commit()
    revenue = db.query(Revenue).filter(Revenue.invoice_id == invoice.id).one()
    assert revenue.revenue_usd_cents == 8 * 9000 and revenue.client_id == client.id and revenue.project_id is None
    assert revenue.business_type == "SPECIALITY"  # no project: the client's line

    # the chain and the P&L show the money
    line = next(l for l in chain.chain_lines(db, start=SEPT[0], end=SEPT[1], tenant_id=1)
                if l["timesheet_id"] == sheet.id)
    assert line["billed_usd_cents"] == 8 * 9000 and line["collected_usd_cents"] == 8 * 9000
    assert line["invoice_id"] == invoice.id and line["unbilled_usd_cents"] == 0
    report = chain.pnl(db, start=SEPT[0], end=SEPT[1], tenant_id=1)
    unit = next(r for r in report["by_business_unit"] if r["key"] == world.unit.id)
    assert unit["revenue_usd_cents"] >= 8 * 9000


def test_auto_invoicing_drafts_one_staff_aug_invoice_per_client_and_period(api, world, db):
    client = _staff_aug_client(db, world)
    item = api.post(world.admin, "/api/v1/allocations", json=_body(world, client_id=client.id)).json()
    allocation = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == item["id"]).one()
    sheet = _approved_week(db, allocation, date(2026, 9, 7))

    run_auto_invoicing(db, today=date(2026, 10, 3))
    run_auto_invoicing(db, today=date(2026, 10, 4))  # the next day: nothing new
    invoices = db.query(Invoice).filter(Invoice.client_id == client.id).all()
    assert len(invoices) == 1 and invoices[0].project_id is None and invoices[0].status == "DRAFT"
    assert invoices[0].total_usd_cents == 8 * 9000
    assert [li.timesheet_id for li in db.query(InvoiceLineItem).filter(
        InvoiceLineItem.invoice_id == invoices[0].id)] == [sheet.id]
    decisions = db.query(InvoiceAutomationDecision).filter(InvoiceAutomationDecision.client_id == client.id,
                                                           InvoiceAutomationDecision.project_id.is_(None)).all()
    assert [d.decision for d in decisions] == ["PENDING_REVIEW"]


def test_project_time_at_the_same_client_stays_on_the_project_invoice(api, world, db):
    """A client can have both: project work is invoiced per project, Staff Aug to the client."""
    db.query(Employee).filter(Employee.id == world.employee.id).update({Employee.core_certified: True})
    db.commit()
    on_project = api.post(world.admin, "/api/v1/allocations", json={
        "employee_id": world.employee.id, "project_id": world.project.id, "role": "Lead",
        "billing_rate_usd_cents": 12000, "start_date": "2026-09-01", "utilization_pct": 50})
    assert on_project.status_code == 200, on_project.text
    staff_aug = api.post(world.admin, "/api/v1/allocations",
                         json=_body(world, utilization_pct=50, allow_concurrent=True))
    assert staff_aug.status_code == 200, staff_aug.text
    rows = {a.id: a for a in db.query(EmployeeAllocation).filter(EmployeeAllocation.employee_id == world.employee.id)}
    _approved_week(db, rows[on_project.json()["id"]], date(2026, 9, 7), hours=4)
    _approved_week(db, rows[staff_aug.json()["id"]], date(2026, 9, 14), hours=4)

    project_invoice = invoice_service.generate_invoice(db, world.project, period_start=SEPT[0], period_end=SEPT[1])
    client_invoice = invoice_service.generate_invoice(db, None, client=world.client, period_start=SEPT[0],
                                                      period_end=SEPT[1])
    db.commit()
    assert project_invoice.total_usd_cents == 4 * 12000 and project_invoice.project_id == world.project.id
    assert client_invoice.total_usd_cents == 4 * 9000 and client_invoice.project_id is None


# --------------------------------------------------------------------------- bill rate and currency

def _india_client(db, world):
    client = Client(tenant_id=1, company_name=f"India Insurer {factories.uid()}", business_unit_id=world.unit.id,
                    line_type="SPECIALITY", country="India", payment_terms_days=30)
    db.add(client)
    db.commit()
    return client


def test_the_form_offers_the_clients_currency_and_the_rate_bases(api, world, db):
    india = _india_client(db, world)
    dropdowns = api.get(world.admin, "/api/v1/allocations/dropdowns/for-create").json()
    currency = {c["id"]: c["currency"] for c in dropdowns["clients"]}
    assert currency[india.id] == "INR" and currency[world.client.id] == "USD"  # by the client's location
    assert dropdowns["rate_bases"] == ["HOURLY", "MONTHLY", "ANNUAL"]
    assert {"USD", "INR"} <= set(dropdowns["rate_currencies"])


def test_an_inr_hourly_rate_is_invoiced_in_inr_and_valued_in_usd(api, world, db):
    from app.core.config import settings

    india = _india_client(db, world)
    item = api.post(world.admin, "/api/v1/allocations", json=_body(
        world, client_id=india.id, billing_rate_usd_cents=None,
        bill_rate_amount_cents=500_000, bill_rate_currency="INR", bill_rate_basis="HOURLY")).json()
    usd = round(500_000 / settings.FX_INR_PER_USD)
    assert item["billing_rate_usd_cents"] == usd  # what the margin guard and the P&L read
    assert (item["bill_rate_amount_cents"], item["bill_rate_currency"], item["bill_rate_basis"]) == (
        500_000, "INR", "HOURLY")
    allocation = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == item["id"]).one()
    _approved_week(db, allocation, date(2026, 9, 7))

    invoice = invoice_service.generate_invoice(db, None, client=india, period_start=SEPT[0], period_end=SEPT[1])
    db.commit()
    assert invoice.currency == "INR" and invoice.total_cents == 8 * 500_000  # exactly as agreed
    assert invoice.total_usd_cents == 8 * usd and float(invoice.fx_per_usd) == settings.FX_INR_PER_USD
    line = db.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id == invoice.id).one()
    assert (line.rate_cents, line.amount_cents, line.rate_usd_cents) == (500_000, 8 * 500_000, usd)
    shown = api.get(world.admin, f"/api/v1/invoices/{invoice.id}").json()
    assert (shown["currency"], shown["total_cents"], shown["total_usd_cents"]) == ("INR", 8 * 500_000, 8 * usd)

    from app.services.message_handlers.send_invoice_email_handler import render_invoice_email

    html = render_invoice_email(db, invoice)["html"]
    assert "INR 40,000.00" in html and "INR 5,000.00" in html


def test_a_monthly_or_annual_rate_is_billed_at_its_hourly_value(api, world, db):
    from app.core.config import settings
    from app.services import compensation

    india = _india_client(db, world)
    monthly = 34_666_000  # INR 3,46,660 a month
    item = api.post(world.admin, "/api/v1/allocations", json=_body(
        world, client_id=india.id, billing_rate_usd_cents=None,
        bill_rate_amount_cents=monthly, bill_rate_currency="INR", bill_rate_basis="MONTHLY")).json()
    hourly_inr = monthly / settings.STANDARD_MONTHLY_HOURS
    assert item["billing_rate_usd_cents"] == round(hourly_inr / settings.FX_INR_PER_USD)
    assert compensation.hourly_usd_cents(monthly * 12, "INR", "ANNUAL") == item["billing_rate_usd_cents"]
    allocation = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == item["id"]).one()
    _approved_week(db, allocation, date(2026, 9, 7))
    invoice = invoice_service.generate_invoice(db, None, client=india, period_start=SEPT[0], period_end=SEPT[1])
    assert invoice.currency == "INR" and invoice.total_cents == round(hourly_inr * 8)


def test_a_usd_rate_at_an_india_client_is_invoiced_in_inr_at_the_exchange_rate(api, world, db):
    from app.core.config import settings

    india = _india_client(db, world)
    item = api.post(world.admin, "/api/v1/allocations", json=_body(world, client_id=india.id)).json()  # USD 90 / hour
    allocation = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == item["id"]).one()
    _approved_week(db, allocation, date(2026, 9, 7))
    invoice = invoice_service.generate_invoice(db, None, client=india, period_start=SEPT[0], period_end=SEPT[1])
    assert invoice.currency == "INR" and invoice.total_usd_cents == 8 * 9000
    assert invoice.total_cents == round(9000 * settings.FX_INR_PER_USD * 8)


def test_a_us_client_invoice_is_unchanged_in_usd(api, world, db):
    item = api.post(world.admin, "/api/v1/allocations", json=_body(
        world, billing_rate_usd_cents=None,
        bill_rate_amount_cents=9000, bill_rate_currency="USD", bill_rate_basis="HOURLY")).json()
    assert item["billing_rate_usd_cents"] == 9000
    allocation = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == item["id"]).one()
    _approved_week(db, allocation, date(2026, 9, 7))
    invoice = invoice_service.generate_invoice(db, None, client=world.client, period_start=SEPT[0], period_end=SEPT[1])
    assert (invoice.currency, invoice.total_cents, invoice.total_usd_cents) == ("USD", 8 * 9000, 8 * 9000)


def test_a_rate_in_a_currency_with_no_exchange_rate_is_refused(api, world, db):
    client = _staff_aug_client(db, world)
    response = api.post(world.admin, "/api/v1/allocations", json=_body(
        world, client_id=client.id, billing_rate_usd_cents=None,
        bill_rate_amount_cents=8000, bill_rate_currency="GBP", bill_rate_basis="HOURLY"))
    assert response.status_code == 422 and "exchange rate" in response.text
    bad_basis = api.post(world.admin, "/api/v1/allocations", json=_body(
        world, client_id=client.id, bill_rate_amount_cents=8000, bill_rate_currency="USD", bill_rate_basis="WEEKLY"))
    assert bad_basis.status_code == 422


def test_margin_preview_values_the_agreed_rate_in_usd(api, world, db):
    from app.core.config import settings

    india = _india_client(db, world)
    response = api.post(world.admin, "/api/v1/allocations/margin-preview", json={
        "employee_id": world.employee.id, "client_id": india.id, "role": "Dev",
        "bill_rate_amount_cents": 500_000, "bill_rate_currency": "INR", "bill_rate_basis": "HOURLY"})
    assert response.status_code == 200, response.text
    assert response.json()["bill_rate_usd_cents"] == round(500_000 / settings.FX_INR_PER_USD)
