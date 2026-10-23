"""Candidate -> employee makes a working system user: the account has no usable password,
the employee is emailed a single-use set-password link (the link exists only in the email),
they set a password and can log in; links expire, can't be reused, and forgot-password
never reveals whether an email has an account."""
import re
import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.models.account_activation import AccountActivationToken
from app.models.business_unit import BusinessUnit
from app.models.candidate import Candidate
from app.models.employee import Employee
from app.models.role_template import Module, Resource, RoleTemplate
from app.models.tenant import Tenant
from app.models.user import Users
from app.services import account_activation_service as accounts
from app.services.message_handlers.send_account_email_handler import SendAccountEmailHandler
from tests.hiring_fixtures import clear_hiring, full_access_role


def _uid():
    return uuid.uuid4().hex[:8]


class FakeMailbox:
    def __init__(self):
        self.drafts, self.sent = {}, []

    def create_draft(self, to, subject, html, ref):
        mid = f"g-{_uid()}"
        self.drafts[mid] = {"to": to, "subject": subject, "html": html}
        return mid, None, None

    def is_draft(self, mid):
        return mid not in self.sent

    def send(self, mid):
        self.sent.append(mid)


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
    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    queued = []

    def enqueue_once(task_name, task_id, data, tenant_id, delay_seconds=0):
        queued.append((task_name, task_id, data))
        return True

    with patch("app.services.thunder_mail.cadence_service.enqueue_once", side_effect=enqueue_once):
        yield TestClient(app), queued
    app.dependency_overrides.clear()


@pytest.fixture
def world(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="BlitzenX"))
        db.flush()
    role = full_access_role(db)
    db.add(role)
    db.flush()
    # the resources the production Employee role is seeded with, then the role itself (same code as startup)
    from app.core.db_contract import LEADERSHIP_ROLES, ensure_role

    module = db.query(Module).filter_by(name="Personal", tenant_id=1).first() or \
        Module(name="Personal", display_name="Personal", tenant_id=1)
    db.add(module)
    db.flush()
    for name in LEADERSHIP_ROLES["Employee"]["permissions"]["vce"] + ["invoices", "revenue"]:
        if db.query(Resource).filter_by(name=name).first() is None:
            db.add(Resource(module_id=module.id, name=name, display_name=name, tenant_id=1))
    db.flush()
    ensure_role(db, "Employee", LEADERSHIP_ROLES["Employee"], 1)
    admin = Users(UserID=f"ADM-{_uid()}", UserName="HR Admin", UserEmail=f"hr{_uid()}@blitzenx.com",
                  UserPassword="x", UserRole="admin", tenant_id=1, role_template_id=role.id,
                  password_reset_required=False)
    unit = BusinessUnit(tenant_id=1, name=f"bu-{_uid()}", display_name="BU")
    candidate = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"jo{_uid()}@example.com",
                          candidatePassword="x", candidateFirstName="Jo", candidateLastName="Park", tenant_id=1, total_experience_months=72)
    db.add_all([admin, unit, candidate])
    db.commit()
    clear_hiring(db, candidate)  # interviews, offer, documents and BGV all passed
    return SimpleNamespace(admin=admin, unit=unit, candidate=candidate)


def _headers(user):
    return {"Authorization": "Bearer " + create_access_token({
        "sub": user.UserID, "type": "user", "tenant_id": user.tenant_id, "role_template_id": user.role_template_id})}


def _convert(client, world, email):
    return client.post("/api/v1/employees/convert-candidate", headers=_headers(world.admin), json={
        "candidate_id": world.candidate.candidateID, "employee_email": email,
        "joining_date": (date.today() - timedelta(days=1)).isoformat(), "business_unit_id": world.unit.id})


def _deliver(db, queued, mailbox):
    task_name, task_id, data = [q for q in queued if q[0] == "send_account_email"][-1]
    assert task_name == "send_account_email"
    return SendAccountEmailHandler.process(SimpleNamespace(id=task_id, payload=data), db, mailbox=mailbox)


def _link_token(mailbox):
    html = list(mailbox.drafts.values())[-1]["html"]
    return re.search(r"/activate\?token=([\w-]+)", html).group(1)


def test_converted_employee_gets_a_login_they_set_themselves(db, api, world):
    client, queued = api
    email = f"jo.park{_uid()}@blitzenx.com"
    response = _convert(client, world, email)
    assert response.status_code == 200, response.text
    user = db.query(Users).filter_by(UserEmail=email).one()
    employee = db.query(Employee).filter_by(wros_user_id=user.UserID).one()
    assert employee.candidate_id == world.candidate.candidateID and user.password_reset_required is True
    # nobody knows a password, and the queued message carries no link or token
    task_name, _, data = [q for q in queued if q[0] == "send_account_email"][-1]
    assert task_name == "send_account_email" and set(data) == {"user_id", "purpose"}

    mailbox = FakeMailbox()
    assert _deliver(db, queued, mailbox)["status"] == "sent"
    assert len(mailbox.sent) == 1 and list(mailbox.drafts.values())[0]["to"] == email
    token = _link_token(mailbox)
    stored = db.query(AccountActivationToken).filter_by(user_id=user.UserID).one()
    assert stored.token_hash != token and stored.emailed_at is not None  # only the hash is stored

    assert client.post("/api/v1/auth/activate", json={"token": token, "new_password": "short"}).status_code == 400
    ok = client.post("/api/v1/auth/activate", json={"token": token, "new_password": "Str0ng-Passw0rd!"})
    assert ok.status_code == 200 and ok.json()["email"] == email
    db.expire_all()
    assert verify_password("Str0ng-Passw0rd!", user.UserPassword) and user.password_reset_required is False
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Str0ng-Passw0rd!"})
    assert login.status_code == 200, login.text
    # an employee sees and does their own work, nothing else
    assert db.query(RoleTemplate).filter_by(id=user.role_template_id).one().name == "Employee"
    mine = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/my/allocations", headers=mine).status_code == 200
    assert client.get("/api/v1/expenses/mine", headers=mine).status_code == 200
    assert client.get("/api/v1/invoices", headers=mine).status_code == 403
    assert client.get("/api/v1/revenue-chain/pnl?start=2026-10-01&end=2026-10-31", headers=mine).status_code == 403
    # the link works once
    again = client.post("/api/v1/auth/activate", json={"token": token, "new_password": "An0ther-Passw0rd!"})
    assert again.status_code == 400


def test_retry_after_crash_resends_the_same_email_once(db, api, world):
    client, queued = api
    _convert(client, world, f"r{_uid()}@blitzenx.com")
    mailbox = FakeMailbox()
    with patch.object(FakeMailbox, "send", side_effect=RuntimeError("network")):
        with pytest.raises(RuntimeError):
            _deliver(db, queued, mailbox)
    db.rollback()
    _deliver(db, queued, mailbox)
    assert len(mailbox.drafts) == 1 and len(mailbox.sent) == 1


def test_expired_link_is_refused(db, world):
    user = Users(UserID=f"U-{_uid()}", UserEmail=f"e{_uid()}@blitzenx.com", UserPassword="x", UserRole="Employee",
                 tenant_id=1, role_template_id=db.query(RoleTemplate).filter_by(name="Employee").first().id)
    db.add(user)
    db.flush()
    _, token = accounts.issue_token(db, user, "ACTIVATE", now=datetime.utcnow() - timedelta(days=8))
    db.commit()
    with pytest.raises(accounts.ActivationError):
        accounts.activate(db, token, "Str0ng-Passw0rd!")


def test_forgot_password_never_reveals_accounts_and_is_rate_limited(db, api, world):
    client, queued = api
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@nowhere.example"})
    known = client.post("/api/v1/auth/forgot-password", json={"email": world.admin.UserEmail})
    assert unknown.status_code == known.status_code == 200 and unknown.json() == known.json()
    assert [q[2]["purpose"] for q in queued if q[0] == "send_account_email"] == ["RESET"]
    _deliver(db, queued, FakeMailbox())
    client.post("/api/v1/auth/forgot-password", json={"email": world.admin.UserEmail})
    assert len([q for q in queued if q[0] == "send_account_email"]) == 1  # one reset email per 10 minutes


def test_resend_activation_for_an_employee(db, api, world):
    client, queued = api
    email = f"s{_uid()}@blitzenx.com"
    _convert(client, world, email)
    employee = db.query(Employee).join(Users, Users.UserID == Employee.wros_user_id).filter(Users.UserEmail == email).one()
    response = client.post(f"/api/v1/employees/{employee.id}/resend-activation", headers=_headers(world.admin))
    assert response.status_code == 200 and [q for q in queued if q[0] == "send_account_email"][-1][2]["purpose"] == "ACTIVATE"
    assert employee.wros_user_id in {u.UserID for u in accounts.users_never_activated(db)}


def test_conversion_is_refused_before_the_candidate_clears_hiring(db, api, world):
    client, _ = api
    fresh = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"f{_uid()}@example.com", candidatePassword="x",
                      candidateFirstName="New", candidateLastName="Person", tenant_id=1, total_experience_months=72)
    db.add(fresh)
    db.commit()
    response = client.post("/api/v1/employees/convert-candidate", headers=_headers(world.admin), json={
        "candidate_id": fresh.candidateID, "employee_email": f"n{_uid()}@blitzenx.com",
        "joining_date": date.today().isoformat(), "business_unit_id": world.unit.id})
    assert response.status_code == 409 and response.json()["detail"]["stage"] == "SCREEN"
