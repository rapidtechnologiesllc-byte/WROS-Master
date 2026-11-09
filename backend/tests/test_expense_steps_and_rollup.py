"""CEO 2026-11-06: the employee hears of every step of an expense, Finance hears when it is ready, a step
left waiting is escalated, and Finance sees the full history. And the end-to-end check: admin (Corporate)
cost, income and expenses, broken by business unit, location and company, add up to the group."""
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models.business_unit import BusinessUnit
from app.models.employee_org_history import EmployeeOrgHistory
from app.models.location import Location
from app.models.task import Task
from app.services import expense_service as service
from app.services import revenue_chain_service as chain
from app.services.expense_receipt_service import attach_receipts
from app.services.expense_service import run_expense_escalations
from tests.scope_fixtures import ApiClient, uid
from tests.test_billing_chain import _allocate, _week, _world
from tests.test_expense_review_and_pnl import PNG, _expense, _logger, _task, db, reads, w  # noqa: F401 -- fixtures


@pytest.fixture
def mail():
    """Every staff email queued and every email to the Finance inbox."""
    sent = []

    def queue(user, *, key, subject, paragraphs, **kw):
        sent.append({"to": user.UserID, "subject": subject, "text": " ".join(p for p in paragraphs if p)})
        return True

    def inbox(**kw):
        sent.append({"to": kw["to_email"], "subject": kw["heading"], "text": kw["message"]})

    with patch("app.services.staff_mail_service.queue_staff_email", side_effect=queue), \
            patch("app.services.email_service.EmailService.send_event_notification", side_effect=inbox):
        yield sent


def _subjects(mail, user):
    return [m["subject"] for m in mail if m["to"] == user.UserID]


def _with_manager(db, w):
    return _logger(db, w, manager=w.partner_a)


def test_the_employee_is_told_when_it_is_logged_with_what_the_check_found(db, w, mail):
    user = _with_manager(db, w)
    expense = _expense(db, user, cents=10_000)
    with reads({"total": 200.0, "date": "2026-09-10"}):
        attach_receipts(db, expense, [("a.png", "image/png", PNG)], user=user)
    logged = next(m for m in mail if m["to"] == user.UserID and "with your manager" in m["subject"])
    assert "200.00 vs entered 100.00" in logged["text"]


def test_approval_tells_the_employee_and_gives_finance_a_task_and_an_alert(db, w, mail):
    user = _with_manager(db, w)
    expense = _expense(db, user)
    mail.clear()
    service.approve_manager_step(db, expense, approved_by=w.partner_a.UserID)
    assert "Your expense was approved" in _subjects(mail, user)
    assert any(m["to"] == service.FINANCE_INBOX_EMAIL for m in mail)
    task = _task(db, expense)
    assert task.title.startswith("Approve expense for payment") and task.system_action == "OPEN_FINANCE"
    assert task.due_date is not None and task.link == "/pnl?view=operations"


def test_rejection_tells_the_employee_why(db, w, mail):
    user = _with_manager(db, w)
    expense = _expense(db, user)
    mail.clear()
    service.reject_manager_step(db, expense, rejected_by=w.partner_a.UserID, reason="Wrong client")
    rejected = next(m for m in mail if m["to"] == user.UserID)
    assert rejected["subject"] == "Your expense was rejected" and "Reason: Wrong client" in rejected["text"]
    assert _task(db, expense) is None and not any(m["to"] == service.FINANCE_INBOX_EMAIL for m in mail)


def test_matching_receipts_tell_the_employee_and_finance(db, w, mail):
    user = _with_manager(db, w)
    expense = _expense(db, user, cents=10_000)
    with reads({"total": 100.0, "date": "2026-09-10"}):
        attach_receipts(db, expense, [("a.png", "image/png", PNG)], user=user)
    assert "Your expense was approved: the receipts match" in _subjects(mail, user)
    assert any(m["to"] == service.FINANCE_INBOX_EMAIL for m in mail)
    assert _task(db, expense).system_action == "OPEN_FINANCE"


def test_a_correction_after_approval_tells_the_employee_and_recalls_the_finance_task(db, w, mail):
    user = _with_manager(db, w)
    expense = _expense(db, user)
    service.approve_manager_step(db, expense, approved_by=w.partner_a.UserID)
    mail.clear()
    service.update_expense(db, expense, user, purpose="OTHER", spend_for="INTERNAL", expense_category="MEALS",
                           amount_usd_cents=9_900, expense_date=expense.expense_date)
    assert "Your corrected expense is back with your manager" in _subjects(mail, user)
    assert _task(db, expense).system_action == "REVIEW_EXPENSE"


def test_the_whole_chain_tells_the_employee_and_is_in_the_history(db, w, mail):
    user = _with_manager(db, w)
    expense = _expense(db, user)
    service.approve_manager_step(db, expense, approved_by=w.partner_a.UserID)
    service.approve_expense(db, expense, approved_by=w.org_user.UserID)
    assert _task(db, expense).title.startswith("Mark expense as paid") and _task(db, expense).due_date is not None
    assert db.query(Task).filter(Task.expense_id == expense.id, Task.status != "COMPLETED").count() == 1
    service.mark_expense_paid(db, expense, paid_by=w.org_user.UserID)
    assert _task(db, expense) is None
    subjects = _subjects(mail, user)
    assert "Your expense was approved" in subjects and "Finance approved your expense for payment" in subjects
    assert "Your expense was paid" in subjects
    db.refresh(expense)
    history = [(e.summary.split(":")[0], e.changed_by_user_id) for e in expense.edits]
    assert history[0] == ("Logged", user.UserID)
    assert ("Approved by the manager", w.partner_a.UserID) in history
    assert ("Approved for payment by Finance", w.org_user.UserID) in history
    assert ("Marked paid by Finance", w.org_user.UserID) in history


def test_finance_sees_the_history_on_the_expense(db, w, mail):
    user = _with_manager(db, w)
    expense = _expense(db, user)
    service.reject_manager_step(db, expense, rejected_by=w.partner_a.UserID, reason="No")
    client = ApiClient(db)
    try:
        edits = client.get(w.org_user, f"/api/v1/expenses/{expense.id}").json()["edits"]
    finally:
        client.close()
    assert edits[-1]["summary"] == "Rejected by the manager: No" and edits[-1]["changed_by_name"]


def _overdue(db, expense):
    task = _task(db, expense)
    task.due_date = datetime.utcnow() - timedelta(hours=1)
    db.commit()
    return task


def test_an_overdue_review_goes_up_the_chain_once_and_the_employee_is_told(db, w, mail, monkeypatch):
    import app.services.task_assignment_service as assignments

    user = _with_manager(db, w)
    expense = _expense(db, user)
    task = _overdue(db, expense)
    monkeypatch.setattr(assignments, "resolve_reporting_manager", lambda session, user_id: w.org_user)
    mail.clear()
    assert run_expense_escalations(db)["escalated"] == 1
    assert any(s.startswith("Overdue: Approve expense") for s in _subjects(mail, w.org_user))
    assert "Your expense is taking longer than expected" in _subjects(mail, user)
    db.refresh(task)
    assert task.is_escalated and task.priority == "HIGH"
    db.refresh(expense)
    assert any(e.summary.startswith("Overdue and escalated") for e in expense.edits)
    mail.clear()
    assert run_expense_escalations(db)["escalated"] == 0 and mail == []


def test_a_task_not_yet_due_is_left_alone(db, w, mail):
    _expense(db, _with_manager(db, w))
    mail.clear()
    assert run_expense_escalations(db)["escalated"] == 0


def test_with_nobody_above_the_assignee_it_goes_to_finance(db, w, mail, monkeypatch):
    import app.services.invoice_service as invoices
    import app.services.task_assignment_service as assignments

    expense = _expense(db, _with_manager(db, w))
    _overdue(db, expense)
    monkeypatch.setattr(assignments, "resolve_reporting_manager", lambda session, user_id: None)
    monkeypatch.setattr(invoices, "invoice_approvers", lambda session, tenant_id: [w.org_user])
    mail.clear()
    run_expense_escalations(db)
    assert any(s.startswith("Overdue:") for s in _subjects(mail, w.org_user))


def test_a_finance_task_cant_be_marked_complete_without_doing_it(db, w, mail):
    expense = _expense(db, _with_manager(db, w))
    service.approve_manager_step(db, expense, approved_by=w.partner_a.UserID)
    client = ApiClient(db)
    try:
        res = client.post(w.org_user, f"/api/v1/tasks/{_task(db, expense).id}/complete")
    finally:
        client.close()
    assert res.status_code == 409


# ---- end to end: admin cost, income and expenses, by BU, location and company, up to the group
METRICS = ("revenue_usd_cents", "delivery_cost_usd_cents", "expense_cost_usd_cents", "total_cost_usd_cents",
           "pending_expense_usd_cents")
AUG = (date(2026, 8, 1), date(2026, 8, 31))
MONTHLY = 300_000


@pytest.fixture
def group(db, w, mail, monkeypatch):
    """BX-US and BX-IN; two earning BUs delivering across them; Corporate with an admin person in each
    company; real approved timesheets; expenses at every stage."""
    monkeypatch.setattr(chain.CostBook, "monthly", lambda self, employee, on=None: MONTHLY if employee else None)
    us = Location(tenant_id=1, name=f"US-{uid()}", country="United States")
    india = Location(tenant_id=1, name=f"IN-{uid()}", country="India")
    corp = BusinessUnit(tenant_id=1, name=f"CORP-{uid()}", display_name="Corporate", bu_code=uid()[:12], is_corporate=True)
    db.add_all([us, india, corp])
    db.flush()
    one, two = _world(db), _world(db)
    one.client.contracting_company_id, two.client.contracting_company_id = us.id, india.id
    one.worker.company_id, one.worker.is_billable = india.id, True  # India delivering for a US-contracted client
    two.worker.company_id, two.worker.is_billable = us.id, True
    db.flush()
    db.query(EmployeeOrgHistory).filter_by(employee_id=one.worker.id).update({"company_id": india.id, "country": "IN"})
    db.query(EmployeeOrgHistory).filter_by(employee_id=two.worker.id).update({"company_id": us.id, "country": "US"})
    for world, hours in ((one, 40), (two, 20)):
        allocation = _allocate(db, world)
        monday = date(2026, 8, 10)
        _week(db, allocation, monday, {monday + timedelta(days=i): hours / 5 for i in range(5)})
    admin_in = _logger(db, w, unit=corp, company=india, manager=w.partner_a)
    admin_us = _logger(db, w, unit=corp, company=us, manager=w.partner_a)
    spender = _logger(db, w, unit=one.unit, company=us, manager=w.partner_a)
    on = date(2026, 8, 12)
    approved = _expense(db, spender, cents=50_000, on=on)
    corporate_rent = _expense(db, admin_in, cents=120_000, on=on)
    rejected = _expense(db, spender, cents=70_000, on=on)
    _expense(db, spender, cents=9_000, on=on)  # left awaiting the manager
    for expense in (approved, corporate_rent):
        service.approve_manager_step(db, expense, approved_by=w.partner_a.UserID)
    service.reject_manager_step(db, rejected, rejected_by=w.partner_a.UserID)
    db.commit()
    return SimpleNamespace(us=us, india=india, corp=corp, one=one, two=two, admin_in=admin_in, admin_us=admin_us, spender=spender)


@pytest.mark.parametrize("metric", METRICS)
@pytest.mark.parametrize("view", ["by_company", "by_business_unit", "by_partner", "by_location", "by_cost_object"])
def test_every_view_adds_up_to_the_group(db, group, view, metric):
    report = chain.pnl(db, start=AUG[0], end=AUG[1], tenant_id=1)
    assert sum(row.get(metric, 0) for row in report[view]) == report[metric]


def test_income_and_delivery_land_where_they_belong(db, group):
    report = chain.pnl(db, start=AUG[0], end=AUG[1], tenant_id=1)
    assert report["revenue_usd_cents"] > 0
    companies = {r["key"]: r for r in report["by_company"]}
    # income on the company that contracts the client, delivery on the company that employs the person
    assert companies[group.us.id]["revenue_usd_cents"] > companies[group.india.id]["revenue_usd_cents"] > 0
    assert companies[group.india.id]["delivery_cost_usd_cents"] > companies[group.us.id]["delivery_cost_usd_cents"] > 0
    locations = {r["key"]: r for r in report["by_location"]}
    assert locations["IN"]["revenue_usd_cents"] > locations["US"]["revenue_usd_cents"] > 0


def test_admin_cost_is_shared_across_the_business_units_and_the_companies(db, group):
    report = chain.pnl(db, start=AUG[0], end=AUG[1], tenant_id=1)
    units = {r["key"]: r for r in report["by_business_unit"]}
    corporate = units.get(group.corp.id, {})
    assert corporate.get("overhead_cost_usd_cents", 0) == 0 and corporate.get("expense_cost_usd_cents", 0) == 0
    assert units[group.one.unit.id]["shared_cost_usd_cents"] > 0 and units[group.two.unit.id]["shared_cost_usd_cents"] > 0
    assert report["shared_cost_usd_cents"] == sum(r["shared_cost_usd_cents"] for r in report["by_business_unit"])
    # CEO 2026-11-09: a company carries Corporate for its own people too, not the company that paid for it
    companies = {r["key"]: r for r in report["by_company"]}
    assert companies[group.india.id]["shared_cost_usd_cents"] > 0 and companies[group.us.id]["shared_cost_usd_cents"] > 0
    assert sum(r["shared_cost_usd_cents"] for r in report["by_company"]) == report["shared_cost_usd_cents"]
    assert sum(r["overhead_cost_usd_cents"] for r in report["by_company"]) == report["overhead_cost_usd_cents"]


def test_rejected_never_counts_and_awaiting_shows_beside_the_cost(db, group):
    report = chain.pnl(db, start=AUG[0], end=AUG[1], tenant_id=1)
    assert report["expense_cost_usd_cents"] == 50_000 + 120_000  # not the 70,000 rejected, nor the 9,000 waiting
    assert report["pending_expense_usd_cents"] == 9_000
    companies = {r["key"]: r for r in report["by_company"]}
    # the spender's own company keeps its 50,000; the Corporate rent India paid is shared by each company's people
    us, india = companies[group.us.id]["expense_cost_usd_cents"], companies[group.india.id]["expense_cost_usd_cents"]
    assert us > 50_000 and india < 120_000 and us + india == 50_000 + 120_000
    locations = {r["key"]: r for r in report["by_location"]}
    assert locations["US"]["expense_cost_usd_cents"] == 50_000 and locations["IN"]["expense_cost_usd_cents"] == 120_000


def test_the_two_locations_add_up_to_the_group(db, group):
    whole = chain.pnl(db, start=AUG[0], end=AUG[1], tenant_id=1)
    only_us = chain.pnl(db, start=AUG[0], end=AUG[1], tenant_id=1, country="US")
    only_in = chain.pnl(db, start=AUG[0], end=AUG[1], tenant_id=1, country="IN")
    for metric in ("revenue_usd_cents", "expense_cost_usd_cents", "total_cost_usd_cents"):
        assert only_us[metric] + only_in[metric] == whole[metric]


def test_a_partner_sees_their_units_share_of_the_same_figures(db, group):
    unit = group.one.unit.id
    whole = {r["key"]: r for r in chain.pnl(db, start=AUG[0], end=AUG[1], tenant_id=1)["by_business_unit"]}[unit]
    scoped = chain.pnl(db, start=AUG[0], end=AUG[1], tenant_id=1, business_unit_ids={unit})
    for metric in ("revenue_usd_cents", "expense_cost_usd_cents", "shared_cost_usd_cents", "total_cost_usd_cents"):
        assert scoped[metric] == whole[metric]
