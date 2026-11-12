"""Timesheet rules (CEO 2026-11-11):
- only the employee enters and submits their own week; everyone else reviews, the approver decides
- each timesheet says where the time is logged (Staff Aug, project, bench work item) and where it
  stands on the way to the reporting manager, Finance and the invoice
- bench time is logged against a work item a BU leader approved (accelerator, certification, ...)
"""
from datetime import date, timedelta

import pytest

from app.models.bench_work_item import BenchWorkItem
from app.models.demand import Demand
from app.models.employee_allocation import EmployeeAllocation
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.task import Task
from app.models.timesheet import Timesheet, TimesheetEntry
from tests.test_core_certification import _employee, _h, _user, api, db, org  # noqa: F401 -- fixtures


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


LAST_WEEK = _monday(date.today()) - timedelta(weeks=1)


@pytest.fixture
def worker(db, org):
    """An allocated employee with a login, placed at a Staff Aug client since six weeks ago."""
    login = _user(db, org.role, "Worker")
    employee = _employee(db, org, login=login.UserID)
    job = Demand(tenant_id=1, client_id=org.staff_aug.id, job_title="Guidewire Dev", work_location="REMOTE",
                 status="OPEN")
    db.add(job)
    db.flush()
    allocation = EmployeeAllocation(tenant_id=1, employee_id=employee.id, demand_id=job.id, role="Guidewire Dev",
                                    client_id=org.staff_aug.id, start_date=date.today() - timedelta(weeks=6),
                                    status="ACTIVE", billing_rate_usd_cents=9000)
    db.add(allocation)
    db.commit()
    return type("Worker", (), dict(login=login, employee=employee, allocation=allocation))


def _draft(api, worker, week=LAST_WEEK):
    res = api.get(f"/api/v1/my/timesheet/current?allocation_id={worker.allocation.id}&week_starting={week}",
                  headers=_h(worker.login))
    assert res.status_code == 200, res.text
    return res.json()


def _entries(week=LAST_WEEK, hours=8, days=5):
    return {"entries": [{"entry_date": str(week + timedelta(days=i)), "hours": hours, "entry_type": "BILLABLE"}
                        for i in range(days)]}


# --------------------------------------------------------------------------- only your own time

def test_nobody_fills_or_submits_someone_elses_week(api, db, org, worker):
    sheet = _draft(api, worker)
    admin = _user(db, org.role, "Admin")
    db.commit()
    listed = api.get("/api/v1/timesheets", headers=_h(admin)).json()["timesheets"]
    mine = next(t for t in listed if t["id"] == sheet["id"])
    assert mine["is_own"] is False  # the admin sees it, read-only

    save = api.put(f"/api/v1/timesheets/{sheet['id']}/entries", headers=_h(admin), json=_entries())
    assert save.status_code == 403 and "Only" in save.json()["detail"]
    submit = api.post(f"/api/v1/timesheets/{sheet['id']}/submit", headers=_h(admin))
    assert submit.status_code == 403
    start = api.post("/api/v1/timesheets/weekly-draft", headers=_h(admin),
                     json={"allocation_id": worker.allocation.id, "week_starting_date": str(LAST_WEEK)})
    assert start.status_code == 403
    db.expire_all()
    assert db.query(TimesheetEntry).filter(TimesheetEntry.timesheet_id == sheet["id"]).count() == 0
    assert db.get(Timesheet, sheet["id"]).status == "DRAFT"


def test_the_employee_fills_and_submits_their_own_week_on_either_screen(api, db, org, worker):
    sheet = _draft(api, worker)
    assert sheet["is_own"] is True
    save = api.put(f"/api/v1/timesheets/{sheet['id']}/entries", headers=_h(worker.login), json=_entries())
    assert save.status_code == 200, save.text
    submit = api.post(f"/api/v1/timesheets/{sheet['id']}/submit", headers=_h(worker.login))
    assert submit.status_code == 200, submit.text
    assert submit.json()["status"] == "SUBMITTED"


def test_the_picker_offers_only_my_own_allocations(api, db, org, worker):
    admin = _user(db, org.role, "Admin")
    db.commit()
    assert api.get("/api/v1/timesheets/allocations", headers=_h(admin)).json()["employees"] == []
    own = api.get("/api/v1/timesheets/allocations", headers=_h(worker.login)).json()["employees"]
    assert [e["employee_id"] for e in own] == [worker.employee.id]


# --------------------------------------------------------------------------- where it is logged, where it stands

def test_a_timesheet_says_where_the_time_is_logged_and_its_week(api, org, worker):
    sheet = _draft(api, worker)
    assert sheet["work_type"] == "STAFF_AUG" and sheet["work_group"] == "Staff Aug"
    assert org.staff_aug.company_name in sheet["work_label"] and "Guidewire Dev" in sheet["work_label"]
    assert sheet["week_ending_date"] == str(LAST_WEEK + timedelta(days=6))


def test_the_pipeline_runs_manager_then_finance_then_invoice(api, db, org, worker):
    sheet = _draft(api, worker)
    assert "reporting manager" in sheet["pipeline"]["text"] and sheet["pipeline"]["stage"] == "DRAFT"
    api.put(f"/api/v1/my/timesheet/{sheet['id']}/entries", headers=_h(worker.login), json=_entries())
    submitted = api.post(f"/api/v1/my/timesheet/{sheet['id']}/submit", headers=_h(worker.login)).json()
    # routed to the approver (here the BU head: nobody above the worker in the org chart) with a task
    assert submitted["pipeline"]["stage"] == "WITH_MANAGER"
    assert submitted["pipeline"]["approver_user_id"] == org.head.UserID
    assert org.head.UserName in submitted["pipeline"]["text"]
    task = db.query(Task).filter(Task.category == "TIMESHEET_APPROVAL", Task.assigned_to_user_id == org.head.UserID).one()
    assert sheet["id"] in task.link

    # the employee cannot approve their own week (their role may edit timesheets); the approver can
    from app.services import timesheet_approval_service as approvals

    review = approvals.latest_review(db, db.get(Timesheet, sheet["id"]))
    assert approvals.may_decide(db, review, worker.login) is False
    assert approvals.may_decide(db, review, org.head) is True
    approved = api.post(f"/api/v1/timesheets/{sheet['id']}/approve", headers=_h(org.head)).json()
    assert approved["status"] == "APPROVED"
    assert approved["pipeline"]["stage"] == "FOR_FINANCE" and "Finance" in approved["pipeline"]["text"]

    # Finance: the draft invoice, then sent
    timesheet = db.get(Timesheet, sheet["id"])
    invoice = Invoice(tenant_id=1, client_id=org.staff_aug.id, billing_period_start=LAST_WEEK,
                      billing_period_end=LAST_WEEK + timedelta(days=6), currency="USD", invoice_number="INV-TEST-1",
                      total_usd_cents=40 * 9000)
    db.add(invoice)
    db.flush()
    db.add(InvoiceLineItem(invoice_id=invoice.id, employee_id=worker.employee.id, timesheet_id=timesheet.id,
                           hours=40, rate_usd_cents=9000, amount_usd_cents=40 * 9000))
    db.commit()
    shown = api.get(f"/api/v1/timesheets/{sheet['id']}", headers=_h(org.head)).json()["pipeline"]
    assert shown["stage"] == "WITH_FINANCE" and shown["invoice_number"] == "INV-TEST-1"
    invoice.status = "SENT"
    db.commit()
    assert api.get(f"/api/v1/timesheets/{sheet['id']}", headers=_h(org.head)).json()["pipeline"]["stage"] == "INVOICED"


# --------------------------------------------------------------------------- bench work items

def _bench_employee(db, org):
    login = _user(db, org.role, "Bench")
    employee = _employee(db, org, login=login.UserID)
    employee.status = "BENCH"
    db.commit()
    return login, employee


def _add_item(api, org, **overrides):
    body = {"name": "Claims intake accelerator", "category": "ACCELERATOR", "business_unit_id": org.unit.id}
    body.update(overrides)
    return api.post("/api/v1/timesheets/work-items", headers=_h(org.head), json=body)


def test_a_bu_head_adds_a_work_item_and_adding_is_the_approval(api, db, org):
    created = _add_item(api, org)
    assert created.status_code == 200, created.text
    item = created.json()
    assert item["category_label"] == "Accelerator" and item["status"] == "ACTIVE"
    assert item["approved_by_name"] == org.head.UserName and item["approved_at"]
    assert _add_item(api, org).status_code == 409  # the same active item twice
    assert _add_item(api, org, name="X1", category="HOBBY").status_code == 422
    listing = api.get("/api/v1/timesheets/work-items", headers=_h(org.head)).json()
    assert [i["id"] for i in listing["work_items"]] == [item["id"]] and listing["can_manage"] is True
    assert set(listing["categories"]) == {"ACCELERATOR", "CERTIFICATION", "APPROVED_WORK"}


def test_someone_who_leads_no_business_unit_cannot_add_a_work_item(api, db, org, monkeypatch):
    from app.core import authority

    login, _ = _bench_employee(db, org)
    monkeypatch.setattr(authority, "is_bu_leader", lambda db, user: False)
    monkeypatch.setattr(authority, "is_org_level", lambda db, user: False)
    res = api.post("/api/v1/timesheets/work-items", headers=_h(login),
                   json={"name": "My own idea", "category": "APPROVED_WORK"})
    assert res.status_code == 403 and "BU head" in res.json()["detail"]
    assert db.query(BenchWorkItem).count() == 0


def test_bench_time_is_logged_against_a_work_item_and_goes_to_the_manager(api, db, org):
    login, employee = _bench_employee(db, org)
    item = _add_item(api, org, name="Guidewire ACE certification", category="CERTIFICATION").json()
    mine = api.get("/api/v1/my/work-items", headers=_h(login)).json()["work_items"]
    assert [(i["id"], i["category_label"]) for i in mine] == [(item["id"], "Certification")]

    sheet = api.get(f"/api/v1/my/timesheet/current?work_item_id={item['id']}&week_starting={LAST_WEEK}",
                    headers=_h(login))
    assert sheet.status_code == 200, sheet.text
    sheet = sheet.json()
    assert (sheet["work_type"], sheet["work_group"], sheet["work_label"]) == (
        "BENCH", "Certification", "Guidewire ACE certification")
    assert sheet["allocation_id"] is None and sheet["work_item_id"] == item["id"]
    again = api.get(f"/api/v1/my/timesheet/current?work_item_id={item['id']}&week_starting={LAST_WEEK}",
                    headers=_h(login)).json()
    assert again["id"] == sheet["id"]  # one timesheet per work item and week

    saved = api.put(f"/api/v1/my/timesheet/{sheet['id']}/entries", headers=_h(login), json=_entries(hours=6)).json()
    assert saved["total_hours"] == 30 and saved["billable_hours"] == 0  # bench work is never billable
    submitted = api.post(f"/api/v1/my/timesheet/{sheet['id']}/submit", headers=_h(login)).json()
    assert submitted["pipeline"]["stage"] == "WITH_MANAGER"
    approved = api.post(f"/api/v1/timesheets/{sheet['id']}/approve", headers=_h(org.head)).json()
    assert approved["pipeline"]["stage"] == "APPROVED_NON_BILLABLE" and "not invoiced" in approved["pipeline"]["text"]


def test_a_work_item_of_another_business_unit_or_a_closed_one_takes_no_time(api, db, org):
    from app.models.business_unit import BusinessUnit

    login, employee = _bench_employee(db, org)
    other = BusinessUnit(tenant_id=1, name="other-bu-bench", display_name="Other BU")
    db.add(other)
    db.flush()
    foreign = BenchWorkItem(tenant_id=1, business_unit_id=other.id, name="Their accelerator", category="ACCELERATOR")
    db.add(foreign)
    db.commit()
    assert api.get("/api/v1/my/work-items", headers=_h(login)).json()["work_items"] == []
    res = api.get(f"/api/v1/my/timesheet/current?work_item_id={foreign.id}&week_starting={LAST_WEEK}", headers=_h(login))
    assert res.status_code == 403

    item = _add_item(api, org).json()
    closed = api.post(f"/api/v1/timesheets/work-items/{item['id']}/close", headers=_h(org.head))
    assert closed.status_code == 200 and closed.json()["status"] == "CLOSED"
    assert api.get("/api/v1/my/work-items", headers=_h(login)).json()["work_items"] == []
    assert api.get(f"/api/v1/my/timesheet/current?work_item_id={item['id']}&week_starting={LAST_WEEK}",
                   headers=_h(login)).status_code == 403


def test_my_timesheet_needs_a_source(api, db, org, worker):
    res = api.get(f"/api/v1/my/timesheet/current?week_starting={LAST_WEEK}", headers=_h(worker.login))
    assert res.status_code == 422


# --------------------------------------------------------------------------- edit allocation = add allocation

def test_an_allocation_edit_takes_the_rate_as_agreed_and_the_role(api, db, org, worker):
    from app.core.config import settings

    res = api.patch(f"/api/v1/allocations/{worker.allocation.id}", headers=_h(org.head), json={
        "bill_rate_amount_cents": 600_000, "bill_rate_currency": "INR", "bill_rate_basis": "HOURLY",
        "role": "Guidewire Business Analyst", "reason": "Client agreed a new INR rate and role"})
    assert res.status_code == 200, res.text
    allocation = res.json()["allocation"]
    assert (allocation["bill_rate_amount_cents"], allocation["bill_rate_currency"], allocation["bill_rate_basis"]) == (
        600_000, "INR", "HOURLY")
    assert allocation["billing_rate_usd_cents"] == round(600_000 / settings.FX_INR_PER_USD)
    assert allocation["role"] == "Guidewire Business Analyst"

    usd = api.patch(f"/api/v1/allocations/{worker.allocation.id}", headers=_h(org.head), json={
        "billing_rate_usd_cents": 9500, "reason": "Back to a USD hourly rate"})
    assert usd.status_code == 200, usd.text
    back = usd.json()["allocation"]
    assert (back["bill_rate_amount_cents"], back["bill_rate_currency"], back["bill_rate_basis"]) == (9500, "USD", "HOURLY")

    bad = api.patch(f"/api/v1/allocations/{worker.allocation.id}", headers=_h(org.head), json={
        "bill_rate_amount_cents": 5000, "bill_rate_currency": "GBP", "bill_rate_basis": "HOURLY",
        "reason": "A currency with no exchange rate"})
    assert bad.status_code == 422 and "exchange rate" in bad.text


def test_the_weeks_time_card_lists_every_row_of_the_week(api, db, org, worker):
    """One weekly card: a row per placement and per bench work item of that week."""
    item = _add_item(api, org).json()
    placement = _draft(api, worker)
    bench = api.get(f"/api/v1/my/timesheet/current?work_item_id={item['id']}&week_starting={LAST_WEEK}",
                    headers=_h(worker.login)).json()
    other_week = _draft(api, worker, week=LAST_WEEK - timedelta(weeks=1))
    card = api.get(f"/api/v1/my/timesheet/history?week_starting={LAST_WEEK}", headers=_h(worker.login)).json()["timesheets"]
    assert {t["id"] for t in card} == {placement["id"], bench["id"]} and other_week["id"] not in {t["id"] for t in card}
    assert {t["work_type"] for t in card} == {"STAFF_AUG", "BENCH"}
