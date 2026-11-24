"""Expenses Accounts uploads for employees, and many receipts at once (CEO 2026-10-19):

1. an approved expense counts in the P&L of the employee's business unit, partner, company and
   the org -- also when the business unit is only on the employee record, not on their login;
2. Accounts may log an expense FOR an employee only with the expenses:create grant on a role
   template; the expense, its approvals and its P&L belong to the employee, the uploader is kept
   for audit and may not approve it;
3. bulk upload: one expense per receipt, read and checked by the same rules, a result per file
   (created / needs review with reasons / failed with the reason), never silent.
"""
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.expense import ExpenseRecord
from app.models.location import Location
from app.models.role_template import Resource, RoleTemplate, RoleTemplatePermission
from app.models.task import Task
from app.models.user import Users
from app.services import expense_service as service
from app.services.revenue_chain_service import pnl
from tests.scope_fixtures import ApiClient, two_bu_world, uid

PNG = b"\x89PNG\r\n"
ON = date(2026, 9, 10)
SEPT = (date(2026, 9, 1), date(2026, 9, 30))
EXPENSES = "/api/v1/expenses"


@pytest.fixture
def db(test_db_engine, tmp_path):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    with patch("app.core.config.settings.UPLOAD_DIR", str(tmp_path)):
        yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _self_service_role(db):
    """An employee's template: their own expenses only, no expenses:create."""
    template = RoleTemplate(tenant_id=1, name=f"emp-{uid()}", display_name="Employee", hierarchy_level=2,
                            org_level_access=False, enabled=True)
    db.add(template)
    db.flush()
    for name in ("my-expenses", "my-tasks"):
        resource = db.query(Resource).filter_by(tenant_id=1, name=name).one()
        db.add(RoleTemplatePermission(role_template_id=template.id, resource_id=resource.id, tenant_id=1,
                                      can_view=True, can_create=True))
    db.flush()
    return template


@pytest.fixture
def w(db):
    world = two_bu_world(db)
    world.bu_a.partner_user_id = world.partner_a.UserID
    world.us = Location(tenant_id=1, name=f"BX-US-{uid()}", country="USA")
    world.india = Location(tenant_id=1, name=f"BX-IN-{uid()}", country="India")
    db.add_all([world.us, world.india])
    db.flush()
    world.employee_role = _self_service_role(db)
    world.manager = world.partner_a

    def employee(name, unit, company, with_login=True):
        user = None
        if with_login:  # the login carries no BU: only the employee record has it
            user = Users(UserID=f"U-{uid()}", UserName=name, UserEmail=f"{uid()}@x.test", UserPassword="x",
                         UserRole="x", tenant_id=1, role_template_id=world.employee_role.id)
            db.add(user)
            db.flush()
        record = Employee(tenant_id=1, first_name=name, last_name=uid(), email=f"{uid()}@x.test",
                          joining_date=date(2025, 1, 1), status="ACTIVE", bu_id=unit.id, company_id=company.id,
                          is_billable=False, buddy_program_status="GRADUATED",
                          wros_user_id=user.UserID if user else None,
                          reporting_manager_user_id=world.manager.UserID)
        db.add(record)
        db.flush()
        return user, record

    world.sam_user, world.sam = employee("Sam", world.bu_a, world.us)
    world.other_user, world.other = employee("Other", world.bu_b, world.india)
    _, world.no_login = employee("Field", world.bu_a, world.india, with_login=False)
    world.accounts = world.org_user  # org-level template with expenses:create
    db.commit()
    return world


def body(**extra):
    return {"purpose": "OTHER", "spend_for": "INTERNAL", "expense_category": "MEALS", "amount_usd_cents": 10_000,
            "expense_date": ON.isoformat(), "receipt_ref": "r", **extra}


def reads(**receipt):
    return patch("app.services.expense_receipt_service.read_receipt",
                 return_value={"is_receipt": True, "currency": "USD", **receipt})


def row(rows, key):
    return next((r for r in rows if r["key"] == key), None)


def cost(rows, key):
    found = row(rows, key)
    return found["expense_cost_usd_cents"] if found else 0


# --- 1. the P&L follows the employee ---------------------------------------------------------------

def test_expense_of_an_employee_whose_bu_is_only_on_the_employee_record_reaches_every_pnl_level(db, w, api):
    created = api.post(w.sam_user, EXPENSES, json=body(amount_usd_cents=12_345))
    assert created.status_code == 201, created.text
    e = created.json()
    assert e["business_unit_id"] == w.bu_a.id  # from the employee record; the login has none
    assert cost(pnl(db, start=SEPT[0], end=SEPT[1], tenant_id=1)["by_business_unit"], w.bu_a.id) == 0  # pending

    with reads(total=123.45, date=ON.isoformat()):
        attached = api.post(w.sam_user, f"{EXPENSES}/{e['id']}/receipts", files={"files": ("r.png", PNG, "image/png")})
    assert attached.json()["manager_approval_status"] == "APPROVED", attached.text

    report = pnl(db, start=SEPT[0], end=SEPT[1], tenant_id=1)
    assert cost(report["by_business_unit"], w.bu_a.id) == 12_345
    assert cost(report["by_partner"], w.partner_a.UserID) >= 12_345
    assert cost(report["by_company"], w.us.id) == 12_345
    assert report["expense_cost_usd_cents"] >= 12_345
    # scoped like every other P&L line: partner A's view has it, partner B's doesn't
    assert cost(api.get(w.partner_a, f"/api/v1/revenue-chain/pnl?start={SEPT[0]}&end={SEPT[1]}").json()[
        "by_business_unit"], w.bu_a.id) == 12_345
    assert cost(api.get(w.partner_b, f"/api/v1/revenue-chain/pnl?start={SEPT[0]}&end={SEPT[1]}").json()[
        "by_business_unit"], w.bu_a.id) == 0


def test_an_older_expense_without_a_bu_falls_back_to_the_employee_record_in_the_pnl(db, w):
    legacy = service.log_expense(db, logged_by_user=w.sam_user, purpose="OTHER", spend_for="INTERNAL",
                                 expense_category="MEALS", amount_usd_cents=700, expense_date=ON, receipt_ref="r")
    legacy.business_unit_id = None  # as logged before the employee record was read
    db.commit()
    service.approve_manager_step(db, legacy, approved_by=w.manager.UserID)
    assert cost(pnl(db, start=SEPT[0], end=SEPT[1], tenant_id=1)["by_business_unit"], w.bu_a.id) == 700


# --- 2. an expense FOR an employee ------------------------------------------------------------------

def test_accounts_logs_an_expense_for_an_employee(db, w, api):
    created = api.post(w.accounts, EXPENSES, json=body(expense_for_employee_id=w.sam.id, amount_usd_cents=4_200))
    assert created.status_code == 201, created.text
    e = created.json()
    assert e["logged_by_user_id"] == w.sam_user.UserID and e["uploaded_by_user_id"] == w.accounts.UserID
    assert e["business_unit_id"] == w.bu_a.id

    # it is the employee's: in their list, not the uploader's
    assert e["id"] in {x["id"] for x in api.get(w.sam_user, f"{EXPENSES}/mine").json()["expenses"]}
    assert e["id"] not in {x["id"] for x in api.get(w.accounts, f"{EXPENSES}/mine").json()["expenses"]}

    # the employee's manager reviews it; neither the uploader nor the employee may
    task = db.query(Task).filter(Task.expense_id == e["id"], Task.status != "COMPLETED").one()
    assert task.assigned_to_user_id == w.manager.UserID
    assert api.post(w.accounts, f"{EXPENSES}/{e['id']}/manager-approve").status_code == 403
    assert api.post(w.sam_user, f"{EXPENSES}/{e['id']}/manager-approve").status_code in (403, 404)

    # the uploader can still attach the receipt; a match approves the manager step
    with reads(total=42.00, date=ON.isoformat()):
        attached = api.post(w.accounts, f"{EXPENSES}/{e['id']}/receipts", files={"files": ("r.png", PNG, "image/png")})
    assert attached.status_code == 200, attached.text
    assert attached.json()["manager_approval_status"] == "APPROVED"

    report = pnl(db, start=SEPT[0], end=SEPT[1], tenant_id=1)
    assert cost(report["by_business_unit"], w.bu_a.id) == 4_200
    assert cost(report["by_company"], w.us.id) == 4_200


def test_logging_for_someone_else_needs_the_role_template_grant(db, w, api):
    # their own employee id is fine without the grant; anyone else's is not
    assert api.post(w.sam_user, EXPENSES, json=body(expense_for_employee_id=w.sam.id)).status_code == 201
    assert api.post(w.sam_user, EXPENSES, json=body(expense_for_employee_id=w.other.id)).status_code == 403
    assert api.get(w.sam_user, f"{EXPENSES}/employees").status_code == 403
    # the same person, once their template grants it and reaches every BU (authority from the
    # template, never a name)
    w.employee_role.org_level_access = True
    resource = db.query(Resource).filter_by(tenant_id=1, name="expenses").one()
    db.add(RoleTemplatePermission(role_template_id=w.employee_role.id, resource_id=resource.id, tenant_id=1,
                                  can_view=True, can_create=True))
    db.commit()
    from app.services.role_template_permission_service import invalidate_permissions
    invalidate_permissions()
    assert api.post(w.sam_user, EXPENSES, json=body(expense_for_employee_id=w.other.id)).status_code == 201


def test_scope_and_logins_limit_who_accounts_can_log_for(db, w, api):
    # partner A's template has expenses:create but sees only BU A
    assert api.post(w.partner_a, EXPENSES, json=body(expense_for_employee_id=w.other.id)).status_code == 404
    picker = {e["id"] for e in api.get(w.partner_a, f"{EXPENSES}/employees").json()["employees"]}
    assert w.sam.id in picker and w.other.id not in picker
    everyone = {e["id"] for e in api.get(w.accounts, f"{EXPENSES}/employees").json()["employees"]}
    assert {w.sam.id, w.other.id} <= everyone and w.no_login.id not in everyone
    # an employee with no login can't own an expense yet: said plainly, nothing created
    res = api.post(w.accounts, EXPENSES, json=body(expense_for_employee_id=w.no_login.id))
    assert res.status_code == 400 and "no WROS login" in res.json()["detail"]


# --- 3. bulk upload, one receipt per call -----------------------------------------------------------

def upload(api, user, name, data, content_type="image/png", **fields):
    form = {"expense_for_employee_id": fields.pop("employee", None) or "", "spend_for": "INTERNAL", **fields}
    return api.post(user, f"{EXPENSES}/from-receipt", files={"file": (name, data, content_type)}, data=form)


def test_bulk_upload_creates_one_expense_per_receipt_with_a_result_for_each(db, w, api):
    receipts = {
        b"a": {"is_receipt": True, "currency": "USD", "total": 50.00, "date": ON.isoformat(), "merchant": "Cafe"},
        b"b": {"is_receipt": True, "currency": "USD", "total": 80.00, "date": ON.isoformat()},
        b"c": RuntimeError("timeout"),
        b"d": {"is_receipt": True, "currency": "EUR", "total": 20.00, "date": ON.isoformat()},
    }

    def read(data, content_type):
        answer = receipts[data[-1:]]
        if isinstance(answer, Exception):
            raise answer
        return dict(answer)

    with patch("app.services.expense_receipt_service.read_receipt", side_effect=read):
        a = upload(api, w.accounts, "a.png", PNG + b"a", employee=w.sam.id).json()      # read: $50, matches
        b = upload(api, w.accounts, "b.png", PNG + b"b", employee=w.other.id,           # typed $30 vs $80
                   amount_usd_cents="3000", expense_category="TRAVEL").json()
        c = upload(api, w.accounts, "c.png", PNG + b"c", employee=w.sam.id).json()      # unreadable, nothing typed
        d = upload(api, w.accounts, "d.png", PNG + b"d", employee=w.sam.id).json()      # EUR, nothing typed
        e = upload(api, w.accounts, "e.exe", b"MZ", "application/x-msdownload", employee=w.sam.id).json()
        f = upload(api, w.accounts, "f.png", PNG + b"a", employee=w.no_login.id).json()  # no login
        g = upload(api, w.sam_user, "g.png", PNG + b"a", employee=w.other.id)            # no grant

    assert a["status"] == "CREATED" and a["amount_usd_cents"] == 5_000 and a["expense_date"] == ON.isoformat()
    assert b["status"] == "NEEDS_REVIEW" and any("80.00" in r for r in b["reasons"])
    assert c["status"] == "FAILED" and any("couldn't be read" in r for r in c["reasons"])
    assert d["status"] == "FAILED" and any("EUR" in r for r in d["reasons"])
    assert e["status"] == "FAILED" and e["reasons"]
    assert f["status"] == "FAILED" and any("no WROS login" in r for r in f["reasons"])
    assert g.status_code == 403
    assert all(r["reasons"] for r in (b, c, d, e, f))

    made_a = db.get(ExpenseRecord, a["expense_id"])
    assert (made_a.logged_by_user_id, made_a.uploaded_by_user_id) == (w.sam_user.UserID, w.accounts.UserID)
    assert made_a.manager_approval_status == "APPROVED" and made_a.description == "Cafe"
    assert len(made_a.receipts) == 1
    made_b = db.get(ExpenseRecord, b["expense_id"])
    assert (made_b.amount_usd_cents, made_b.business_unit_id, made_b.manager_approval_status) == (
        3_000, w.bu_b.id, "PENDING")
    # nothing half-created for the failures
    assert db.query(ExpenseRecord).filter(ExpenseRecord.uploaded_by_user_id == w.accounts.UserID).count() == 2

    report = pnl(db, start=SEPT[0], end=SEPT[1], tenant_id=1)
    assert cost(report["by_business_unit"], w.bu_a.id) == 5_000
    assert cost(report["by_company"], w.us.id) == 5_000
    assert cost(report["by_business_unit"], w.bu_b.id) == 0  # waiting for its manager
    assert report["pending_expenses_usd_cents"] >= 3_000


def test_uploading_the_same_receipt_twice_needs_review_as_a_possible_duplicate(db, w, api):
    with reads(total=12.00, date=ON.isoformat()):
        first = upload(api, w.accounts, "r.png", PNG + b"z", employee=w.sam.id).json()
        again = upload(api, w.accounts, "r.png", PNG + b"z", employee=w.sam.id).json()
    assert first["status"] == "CREATED"
    assert again["status"] == "NEEDS_REVIEW" and any("Possible duplicate" in r for r in again["reasons"])
    assert db.get(ExpenseRecord, again["expense_id"]).manager_approval_status == "PENDING"


def test_a_bulk_receipt_without_saying_who_the_spend_is_on_fails_with_the_reason(db, w, api):
    with reads(total=12.00, date=ON.isoformat()):
        res = upload(api, w.accounts, "r.png", PNG + b"y", employee=w.sam.id, spend_for="").json()
    assert res["status"] == "FAILED" and any("who it is on" in r for r in res["reasons"])
