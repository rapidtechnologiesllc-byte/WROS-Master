"""CEO 2026-11-05: users did not get a welcome to set up and connect Outlook; Add employee lacked what Add user asks;
HR, resource management, recruitment, finance and the CEO "broken at org level", BU non-billable at BU level."""
import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.account_activation import AccountActivationToken
from app.models.employee import Employee
from app.models.org_structure import Department
from app.models.user import Users
from app.services import account_activation_service as activation, revenue_chain_service as chain
from app.services.message_handlers.send_account_email_handler import COPY
from tests.scope_fixtures import ApiClient, person, scoped_role, two_bu_world


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
    return two_bu_world(db)


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


@pytest.fixture
def queued(monkeypatch):
    sent = []
    monkeypatch.setattr(activation, "queue_account_email", lambda user, purpose="ACTIVATE", once_key=None: sent.append((user.UserID, purpose, once_key)) or True)
    return sent


def test_the_welcome_says_password_then_outlook():
    subject, body = COPY["ACTIVATE"]
    assert "Welcome" in subject
    assert "{link}" in body and "Connect your Outlook" in body and body.index("Set your password") < body.index("Connect your Outlook")


def _token(db, user, days_ago, **fields):
    db.add(AccountActivationToken(user_id=user.UserID, token_hash=uuid.uuid4().hex, purpose="ACTIVATE", created_at=datetime.utcnow() - timedelta(days=days_ago),
                                  expires_at=datetime.utcnow() + timedelta(days=7), **fields))
    db.commit()


def test_nobody_is_left_without_a_working_link(db, w, queued):
    never, stale, recent, used = [person(db, scoped_role(db), f"P{i}") for i in range(4)]
    for user in (never, stale, recent, used):
        user.password_reset_required = True
    db.commit()
    _token(db, stale, 5)
    _token(db, recent, 1)
    _token(db, used, 5, used_at=datetime.utcnow())
    activation.run_welcome_followup_job(db)
    who = {u for u, _, _ in queued}
    assert never.UserID in who and stale.UserID in who
    assert recent.UserID not in who and used.UserID not in who


def test_the_welcome_stops_after_the_limit(db, w, queued):
    user = person(db, scoped_role(db), "P")
    user.password_reset_required = True
    db.commit()
    for _ in range(settings.WELCOME_MAX_SENDS):
        _token(db, user, 9)
    activation.run_welcome_followup_job(db)
    assert user.UserID not in {u for u, _, _ in queued}


def test_resend_is_available_and_scoped(api, db, w, queued):
    user = person(db, scoped_role(db), "P")
    user.password_reset_required = True
    db.commit()
    done = api.post(w.org_user, f"/api/v1/hr/users/{user.UserID}/resend-welcome")
    assert done.status_code == 200, done.text
    assert done.json()["email"] == user.UserEmail
    assert api.post(w.org_user, "/api/v1/hr/users/USER-nobody/resend-welcome").status_code == 404


def _body(db, w, department_id=None, **fields):
    from app.models.business_unit import BusinessUnitCompany
    from app.models.location import Location

    company = Location(tenant_id=1, name=f"BX-US-{uuid.uuid4().hex[:6]}", country="US")
    db.add(company)
    db.flush()
    db.add(BusinessUnitCompany(tenant_id=1, business_unit_id=w.bu_a.id, company_id=company.id))
    db.commit()
    return {"company_id": company.id, "first_name": "Asha", "last_name": "Rao", "email": f"asha{uuid.uuid4().hex[:8]}@example.com", "joining_date": "2026-01-05",
            "business_unit_id": w.bu_a.id, "billable": False, "pay_amount_cents": 12000000, "pay_currency": "USD", "pay_basis": "ANNUAL",
            "department_id": department_id, **fields}


def test_add_employee_sets_the_function_and_the_welcome_goes(api, db, w, monkeypatch):
    from app.services import employee_import_service

    sent = []
    monkeypatch.setattr(activation, "queue_account_email", lambda user, purpose="ACTIVATE", once_key=None: sent.append(user.UserEmail) or True)
    from app.models.role_template import RoleTemplate

    if not db.query(RoleTemplate).filter_by(tenant_id=1, name="Employee").first():
        db.add(RoleTemplate(tenant_id=1, name="Employee", display_name="Employee", hierarchy_level=2))
    department = Department(id=str(uuid.uuid4()), tenant_id=1, name=f"HR {uuid.uuid4().hex[:4]}", active=True)
    db.add(department)
    db.commit()
    body = _body(db, w, department.id, work_location="ONSITE")
    created = api.post(w.org_user, "/api/v1/employees", json=body)
    assert created.status_code in (200, 201), created.text
    db.expire_all()
    user = db.query(Users).filter(Users.UserEmail == body["email"]).one()
    assert user.department_id == department.id
    assert db.query(Employee).filter_by(wros_user_id=user.UserID).one().work_location == "ONSITE"
    assert body["email"] in sent
    assert employee_import_service is not None


def test_an_existing_login_that_never_signed_in_gets_the_welcome_when_added(api, db, w, monkeypatch):
    sent = []
    monkeypatch.setattr(activation, "queue_account_email", lambda user, purpose="ACTIVATE", once_key=None: sent.append(user.UserEmail) or True)
    login = person(db, scoped_role(db), "Existing")
    login.password_reset_required = True
    login.UserEmail = f"exist{uuid.uuid4().hex[:6]}@example.com"
    db.commit()
    created = api.post(w.org_user, "/api/v1/employees", json={**_body(db, w, None), "email": login.UserEmail})
    assert created.status_code in (200, 201), created.text
    assert login.UserEmail in sent


def _pnl(monkeypatch, db, w, *, lines, split=False):
    """HR person, a BU-level person, each with a cost of 100 000 cents; real P&L from fake lines and cost book."""
    tenant = 1
    department = Department(id=str(uuid.uuid4()), tenant_id=tenant, name="Finance", is_shared_service=True, active=True)
    db.add(department)
    db.flush()
    hr_user, bu_user = person(db, scoped_role(db), "HR"), person(db, scoped_role(db), "BU")
    hr_user.department_id = department.id
    make = lambda u, name: Employee(tenant_id=tenant, first_name=name, last_name="X", email=f"{uuid.uuid4().hex[:6]}@x.com", wros_user_id=u.UserID,  # noqa: E731
                                    employee_number=f"T-{uuid.uuid4().hex[:6]}", joining_date=date(2026, 1, 1), bu_id=w.bu_a.id, is_billable=False, status="ACTIVE")
    db.add_all([make(hr_user, "H"), make(bu_user, "B")])
    db.commit()

    class Book(chain.CostBook):
        def by_object(self, employee, start, end):
            return {(w.bu_a.id, "C1", "US"): 100_000} if employee.wros_user_id in (hr_user.UserID, bu_user.UserID) else {}

    monkeypatch.setattr(chain, "CostBook", Book)
    monkeypatch.setattr(chain, "chain_lines", lambda *a, **k: lines)
    monkeypatch.setattr(settings, "SHARED_COST_SPLIT_TO_BUS", split)
    return chain.pnl(db, start=date(2026, 11, 1), end=date(2026, 11, 30))


def test_org_staff_sit_in_an_org_level_row_and_bu_staff_in_their_bu(db, w, monkeypatch):
    report = _pnl(monkeypatch, db, w, lines=[])
    rows = {r["key"]: r for r in report["by_business_unit"]}
    assert rows[None]["name"] == "Org level" and rows[None]["shared_cost_usd_cents"] == 100_000
    assert rows[w.bu_a.id]["overhead_cost_usd_cents"] == 100_000 and rows[w.bu_a.id]["shared_cost_usd_cents"] == 0
    assert report["overhead_cost_usd_cents"] + report["shared_cost_usd_cents"] == 200_000, "the org total does not change"
    assert {"name": "Finance", "cost_usd_cents": 100_000} in report["org_staff_by_function"]


def test_a_person_with_org_wide_authority_is_org_level_without_a_function(db, w, monkeypatch):
    from app.core import authority

    monkeypatch.setattr(authority, "is_org_level", lambda session, user: True)
    employee = Employee(tenant_id=1, first_name="C", last_name="E", email=f"{uuid.uuid4().hex[:6]}@x.com", wros_user_id=w.org_user.UserID,
                        employee_number=f"T-{uuid.uuid4().hex[:6]}", joining_date=date(2026, 1, 1), bu_id=w.bu_b.id, is_billable=False, status="ACTIVE")
    db.add(employee)
    db.commit()
    monkeypatch.setattr(chain, "chain_lines", lambda *a, **k: [])
    book = SimpleNamespace(by_object=lambda e, s, n: {(w.bu_b.id, "C1", "US"): 5_000} if e.id == employee.id else {})
    pool, by_function, _ = chain.shared_service_moves(db, start=date(2026, 11, 1), end=date(2026, 11, 30), tenant_id=None, costs=book)
    assert pool[(w.bu_b.id, "US")] >= 5_000 and by_function["Leadership"] >= 5_000


def test_the_split_setting_moves_it_to_the_bus_by_their_weight(db, w, monkeypatch):
    monkeypatch.setattr(chain, "headcount_weights", lambda *a, **k: {w.bu_a.id: 1, w.bu_b.id: 1})
    lines = [{"business_unit_id": bu, "earned_usd_cents": 100, "employee_id": "x", "cost_usd_cents": 0, "cost_business_unit_id": bu,
              "cost_company_id": "C1", "country": "US", "partner_user_id": None, "partner_name": None, "client_id": None, "client_name": None,
              "billable_hours": 0, "billed_usd_cents": 0, "collected_usd_cents": 0, "unbilled_usd_cents": 0, "vendor_cost_usd_cents": 0,
              "vendor_invoiced_usd_cents": 0, "vendor_paid_usd_cents": 0, "pending_approval_usd_cents": 0, "cost_data_complete": True} for bu in (w.bu_a.id, w.bu_b.id)]
    report = _pnl(monkeypatch, db, w, lines=lines, split=True)
    rows = {r["key"]: r for r in report["by_business_unit"]}
    assert None not in rows or rows[None]["shared_cost_usd_cents"] == 0
    assert rows[w.bu_a.id]["shared_cost_usd_cents"] == 50_000 and rows[w.bu_b.id]["shared_cost_usd_cents"] == 50_000
