"""CEO 2026-11-06: a manager sees an expense's task, its receipts and the system's check; the person who
logged it can correct it, attach several receipts and give a date range; every expense shows in the P&L by
company, location, business unit and partner; HR and recruitment see every business unit."""
import json
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.location import Location
from app.models.org_structure import Department
from app.models.task import Task
from app.models.user import Users
from app.services import expense_receipt_reader as reader
from app.services import expense_service as service
from app.services.expense_receipt_service import ReceiptError, attach_receipts, recheck, remove_receipt
from app.services.revenue_chain_service import pnl
from app.services.task_service import get_daily_task_list
from tests.scope_fixtures import ApiClient, scoped_role, two_bu_world, uid

PNG = b"\x89PNG\r\n"
ON = date(2026, 9, 10)
SEPT = (date(2026, 9, 1), date(2026, 9, 30))
EXPENSES = "/api/v1/expenses"


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
def w(db):
    world = two_bu_world(db)
    db.commit()
    return world


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _logger(db, w, *, manager=None, unit=None, company=None):
    role_id = w.org_user.role_template_id
    user = Users(UserID=f"U-{uid()}", UserName="Logger", UserEmail=f"{uid()}@x.test", UserPassword="x", UserRole="x",
                 tenant_id=1, role_template_id=role_id, business_unit_id=(unit or w.bu_a).id)
    db.add(user)
    db.flush()
    db.add(Employee(tenant_id=1, first_name="L", last_name=uid(), email=f"{uid()}@x.test", joining_date=date(2025, 1, 1),
                    status="ACTIVE", bu_id=(unit or w.bu_a).id, company_id=company.id if company else None, is_billable=False,
                    wros_user_id=user.UserID, buddy_program_status="GRADUATED",
                    reporting_manager_user_id=manager.UserID if manager else None))
    db.flush()
    return user


def _expense(db, user, cents=12_345, on=ON, **kw):
    return service.log_expense(db, logged_by_user=user, purpose="OTHER", spend_for="INTERNAL", expense_category="MEALS",
                               amount_usd_cents=cents, expense_date=on, receipt_ref="r", **kw)


def reads(*readings):
    return patch("app.services.expense_receipt_service.read_receipt",
                 side_effect=[{"is_receipt": True, "currency": "USD", **r} for r in readings])


def _task(db, expense):
    return db.query(Task).filter(Task.expense_id == expense.id, Task.status != "COMPLETED").first()


# ---- the manager's task
def test_the_managers_task_is_on_their_list_even_with_no_due_date(db, w):
    expense = _expense(db, _logger(db, w, manager=w.partner_a))
    task = _task(db, expense)
    assert task.assigned_to_user_id == w.partner_a.UserID and task.system_action == "REVIEW_EXPENSE"
    assert task.id in [t.id for t in get_daily_task_list(db, assigned_to_user_id=w.partner_a.UserID)]
    task.due_date = None  # any task with no date is still its owner's work
    db.commit()
    assert task.id in [t.id for t in get_daily_task_list(db, assigned_to_user_id=w.partner_a.UserID)]


def test_my_day_gives_the_screen_the_expense_to_open(db, w, api):
    expense = _expense(db, _logger(db, w, manager=w.partner_a))
    rows = api.get(w.partner_a, "/api/v1/tasks/my-day").json()
    row = next(t for t in rows if t["id"] == _task(db, expense).id)
    assert row["expense_id"] == expense.id and row["system_action"] == "REVIEW_EXPENSE"


def test_with_no_manager_on_record_it_goes_to_the_bu_partner(db, w):
    w.bu_a.partner_user_id = w.partner_a.UserID
    db.commit()
    assert _task(db, _expense(db, _logger(db, w))).assigned_to_user_id == w.partner_a.UserID


def test_a_manager_without_finance_access_can_open_and_decide_their_task(db, w, api):
    expense = _expense(db, _logger(db, w, manager=w.partner_a))
    assert api.get(w.partner_a, f"{EXPENSES}/{expense.id}").status_code == 200
    res = api.post(w.partner_a, f"{EXPENSES}/{expense.id}/manager-reject", json={"reason": "Wrong client"})
    assert res.status_code == 200, res.text
    assert res.json()["manager_review_note"] == "Wrong client"
    assert _task(db, expense) is None


def test_mark_complete_does_not_close_a_review_task(db, w, api):
    expense = _expense(db, _logger(db, w, manager=w.partner_a))
    res = api.post(w.partner_a, f"/api/v1/tasks/{_task(db, expense).id}/complete")
    assert res.status_code == 409


def test_the_response_shows_the_receipts_and_the_check_notes(db, w, api):
    user = _logger(db, w, manager=w.partner_a)
    expense = _expense(db, user)
    with reads({"total": 200.0, "date": "2026-09-10", "merchant": "Cafe"}):
        attach_receipts(db, expense, [("a.png", "image/png", PNG)], user=user)
    body = api.get(w.partner_a, f"{EXPENSES}/{expense.id}").json()
    assert body["logged_by_name"] == "Logger" and [r["file_name"] for r in body["receipts"]] == ["a.png"]
    detail = json.loads(body["receipt_check_detail"])
    assert "200.00 vs entered 123.45" in detail["reasons"][0] and detail["receipts"][0]["merchant"] == "Cafe"
    file_url = f"{EXPENSES}/{expense.id}/receipts/{body['receipts'][0]['id']}"
    assert api.get(w.partner_a, file_url).status_code == 200


# ---- several receipts
def test_several_receipts_are_checked_together(db, w):
    user = _logger(db, w, manager=w.partner_a)
    expense = _expense(db, user, cents=30_000)
    with reads({"total": 100.0, "date": "2026-09-10"}, {"total": 200.0, "date": "2026-09-11"}):
        attach_receipts(db, expense, [("a.png", "image/png", PNG), ("b.png", "image/png", PNG)], user=user)
    assert len(expense.receipts) == 2 and expense.receipt_check_status == "MATCHED"
    assert expense.manager_approval_status == "APPROVED"


def test_one_bad_file_refuses_the_whole_batch(db, w):
    user = _logger(db, w)
    expense = _expense(db, user)
    with pytest.raises(ReceiptError):
        attach_receipts(db, expense, [("a.png", "image/png", PNG), ("b.exe", "application/x-msdownload", b"MZ")], user=user)
    db.refresh(expense)
    assert expense.receipts == []


def test_an_upload_can_hold_the_check_until_the_last_file(db, w):
    user = _logger(db, w)
    expense = _expense(db, user, cents=30_000)
    with reads({"total": 300.0, "date": "2026-09-10"}):
        attach_receipts(db, expense, [("a.png", "image/png", PNG)], user=user, check=False)
    assert expense.receipt_check_status == "NOT_ATTACHED" and expense.manager_approval_status == "PENDING"


def test_the_last_receipt_cant_be_removed(db, w):
    user = _logger(db, w)
    expense = _expense(db, user, cents=30_000)
    with reads({"total": 100.0, "date": "2026-09-10"}, {"total": 200.0, "date": "2026-09-10"}):
        attach_receipts(db, expense, [("a.png", "image/png", PNG), ("b.png", "image/png", PNG)], user=user)
    remove_receipt(db, expense, expense.receipts[0].id, user=user)
    assert len(expense.receipts) == 1 and expense.receipt_check_status == "MISMATCH"
    assert expense.manager_approval_status == "PENDING"  # went back to the manager
    with pytest.raises(ReceiptError):
        remove_receipt(db, expense, expense.receipts[0].id, user=user)


# ---- date range
def test_a_receipt_inside_the_date_range_matches(db, w, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "EXPENSE_RECEIPT_DATE_TOLERANCE_DAYS", 0)
    user = _logger(db, w)
    expense = _expense(db, user, cents=10_000, expense_end_date=date(2026, 9, 14))
    with reads({"total": 100.0, "date": "2026-09-13"}):
        attach_receipts(db, expense, [("a.png", "image/png", PNG)], user=user)
    assert expense.receipt_check_status == "MATCHED"


def test_the_last_day_cant_be_before_the_first(db, w):
    with pytest.raises(service.ExpenseValidationError):
        _expense(db, _logger(db, w), expense_end_date=ON - timedelta(days=1))


# ---- editing
def _edit(db, expense, user, **kw):
    body = dict(purpose="OTHER", spend_for="INTERNAL", expense_category="MEALS", amount_usd_cents=expense.amount_usd_cents,
                expense_date=expense.expense_date, description=expense.description)
    return service.update_expense(db, expense, user, **{**body, **kw})


def test_a_correction_goes_back_to_the_manager_and_is_recorded(db, w):
    user = _logger(db, w, manager=w.partner_a)
    expense = _expense(db, user)
    service.approve_manager_step(db, expense, approved_by=w.partner_a.UserID)
    _edit(db, expense, user, amount_usd_cents=20_000, expense_end_date=date(2026, 9, 12))
    assert expense.manager_approval_status == "PENDING" and expense.manager_approved_by is None
    assert expense.expense_end_date == date(2026, 9, 12)
    assert any("$123.45 -> $200.00" in edit.summary for edit in expense.edits)
    task = _task(db, expense)
    assert "$200.00" in task.title and "$123.45 -> $200.00" in task.description


def test_a_note_change_keeps_the_approval(db, w):
    user = _logger(db, w, manager=w.partner_a)
    expense = _expense(db, user)
    service.approve_manager_step(db, expense, approved_by=w.partner_a.UserID)
    before = len(expense.edits)
    _edit(db, expense, user, description="Lunch with the team")
    assert expense.manager_approval_status == "APPROVED" and len(expense.edits) == before + 1


def test_an_edit_with_no_change_records_nothing(db, w):
    user = _logger(db, w, manager=w.partner_a)
    expense = _expense(db, user)
    before = len(expense.edits)
    _edit(db, expense, user)
    assert len(expense.edits) == before


def test_a_rejected_expense_can_be_corrected_and_resubmitted(db, w):
    user = _logger(db, w, manager=w.partner_a)
    expense = _expense(db, user)
    service.reject_manager_step(db, expense, rejected_by=w.partner_a.UserID, reason="Wrong amount")
    _edit(db, expense, user, amount_usd_cents=20_000)
    assert expense.manager_approval_status == "PENDING" and expense.manager_review_note is None
    assert _task(db, expense) is not None


def test_only_the_logger_can_edit_and_only_until_finance_approves(db, w, api):
    user = _logger(db, w, manager=w.partner_a)
    expense = _expense(db, user)
    body = {"purpose": "OTHER", "spend_for": "INTERNAL", "expense_category": "MEALS", "amount_usd_cents": 500, "expense_date": str(ON)}
    assert api.put(w.partner_a, f"{EXPENSES}/{expense.id}", json=body).status_code == 404
    assert api.put(user, f"{EXPENSES}/{expense.id}", json=body).status_code == 200
    expense.payment_status = "APPROVED"
    db.commit()
    assert api.put(user, f"{EXPENSES}/{expense.id}", json=body).status_code == 409


def test_correcting_the_amount_rechecks_what_was_already_read(db, w):
    user = _logger(db, w, manager=w.partner_a)
    expense = _expense(db, user, cents=10_000)
    with reads({"total": 335.80, "date": "2026-09-10"}):
        attach_receipts(db, expense, [("a.png", "image/png", PNG)], user=user)
    assert expense.receipt_check_status == "MISMATCH"
    with patch("app.services.expense_receipt_service.read_receipt", side_effect=AssertionError("no second read")):
        _edit(db, expense, user, amount_usd_cents=33_580)
    assert expense.receipt_check_status == "MATCHED" and expense.manager_approval_status == "APPROVED"


def test_a_backfilled_check_can_leave_the_decision_to_the_manager(db, w):
    user = _logger(db, w, manager=w.partner_a)
    expense = _expense(db, user, cents=10_000)
    with reads({"total": 100.0, "date": "2026-09-10"}):
        attach_receipts(db, expense, [("a.png", "image/png", PNG)], user=user, check=False)
    recheck(db, expense, auto_approve=False)
    assert expense.receipt_check_status == "MATCHED" and expense.manager_approval_status == "PENDING"


# ---- the P&L
def _world_of_a_spend(db, w, country="USA"):
    company = Location(tenant_id=1, name=f"BX-US-{uid()}", country=country)
    db.add(company)
    db.flush()
    return _logger(db, w, manager=w.partner_a, company=company), company


def _row(rows, key):
    return next(r for r in rows if r["key"] == key)


def test_an_approved_expense_is_in_every_view(db, w):
    user, company = _world_of_a_spend(db, w)
    w.bu_a.partner_user_id = w.partner_a.UserID
    db.commit()
    expense = _expense(db, user, cents=10_000)
    service.approve_manager_step(db, expense, approved_by=w.partner_a.UserID)
    report = pnl(db, start=SEPT[0], end=SEPT[1], tenant_id=1)
    assert _row(report["by_company"], company.id)["expense_cost_usd_cents"] == 10_000
    assert _row(report["by_business_unit"], w.bu_a.id)["expense_cost_usd_cents"] >= 10_000
    assert _row(report["by_partner"], w.partner_a.UserID)["expense_cost_usd_cents"] >= 10_000
    assert _row(report["by_location"], "US")["expense_cost_usd_cents"] >= 10_000
    assert next(r for r in report["by_cost_object"] if r["key"] == f"{w.bu_a.id}:US")["expense_cost_usd_cents"] >= 10_000
    assert report["expense_cost_usd_cents"] >= 10_000
    only_us = pnl(db, start=SEPT[0], end=SEPT[1], tenant_id=1, country="US")
    assert only_us["expense_cost_usd_cents"] >= 10_000
    assert pnl(db, start=SEPT[0], end=SEPT[1], tenant_id=1, country="IN")["expense_cost_usd_cents"] == 0


def test_an_expense_awaiting_the_manager_shows_beside_the_cost_not_in_it(db, w):
    user, company = _world_of_a_spend(db, w)
    _expense(db, user, cents=10_000)
    report = pnl(db, start=SEPT[0], end=SEPT[1], tenant_id=1)
    company_row = _row(report["by_company"], company.id)
    assert company_row["pending_expense_usd_cents"] == 10_000 and company_row["expense_cost_usd_cents"] == 0
    assert _row(report["by_business_unit"], w.bu_a.id)["pending_expense_usd_cents"] >= 10_000
    assert _row(report["by_location"], "US")["pending_expense_usd_cents"] >= 10_000
    assert report["pending_expenses_usd_cents"] >= 10_000 and report["pending_expense_usd_cents"] >= 10_000


def test_a_client_with_no_contracting_company_leaves_it_with_the_spenders_company(db, w):
    user, company = _world_of_a_spend(db, w)
    w.client_a.contracting_company_id = None
    db.commit()
    expense = service.log_expense(db, logged_by_user=user, purpose="CLIENT_PROSPECT", expense_category="TRAVEL",
                                  amount_usd_cents=33_580, expense_date=ON, receipt_ref="r", spend_for="CLIENT",
                                  client_id=w.client_a.id)
    service.approve_manager_step(db, expense, approved_by=w.partner_a.UserID)
    rows = pnl(db, start=SEPT[0], end=SEPT[1], tenant_id=1)["by_company"]
    assert _row(rows, company.id)["expense_cost_usd_cents"] == 33_580


# ---- reading a receipt by rule
def test_rules_find_the_total_date_and_merchant():
    found = reader.parse("Acme Airlines\nInvoice date: 09/22/2026\nSubtotal 300.00\nTax 35.80\nTotal paid: $335.80\n")
    assert (found["total"], found["date"], found["currency"], found["merchant"]) == (335.80, "2026-09-22", "USD", "Acme Airlines")


@pytest.mark.parametrize("text,expected", [
    ("Sep 22, 2026", date(2026, 9, 22)), ("22 September 2026", date(2026, 9, 22)), ("2026-09-22", date(2026, 9, 22)),
    ("22/09/2026", date(2026, 9, 22)),
])
def test_rules_read_common_date_shapes(text, expected):
    assert reader.dates_in(text) == [expected]


def test_subtotal_is_not_the_total():
    assert reader.parse("Subtotal 100.00\nTotal 110.00\n")["total"] == 110.00
    assert reader.parse("Subtotal 100.00\n")["total"] is None


def test_an_amount_with_no_total_label_goes_to_the_manager(db, w):
    user = _logger(db, w, manager=w.partner_a)
    expense = _expense(db, user, cents=33_580)
    with reads({"total": None, "date": "2026-09-10", "amounts": [12.5, 335.80]}):
        attach_receipts(db, expense, [("a.png", "image/png", PNG)], user=user)
    assert expense.receipt_check_status == "MISMATCH" and expense.manager_approval_status == "PENDING"
    assert "nothing marks it as the total" in expense.receipt_check_detail


# ---- HR and recruitment
def test_a_function_can_see_every_business_unit_without_other_org_authority(db, w):
    from app.core import authority
    from app.core.visibility import scope_bu_ids

    user = _logger(db, w)
    user.role_template_id = scoped_role(db).id
    function = Department(id=uid(), tenant_id=1, name=f"HR-{uid()}", active=True)
    db.add(function)
    db.flush()
    user.department_id = function.id
    db.commit()
    assert scope_bu_ids(db, user) == {w.bu_a.id}
    function.sees_all_business_units = True
    db.commit()
    assert scope_bu_ids(db, user) is None
    assert authority.is_org_level(db, user) is False


def test_the_function_form_saves_it(db, w, api):
    res = api.post(w.org_user, "/api/v1/org/departments", json={"name": f"F-{uid()}", "sees_all_business_units": True})
    assert res.status_code in (200, 201), res.text
    assert res.json()["sees_all_business_units"] is True
