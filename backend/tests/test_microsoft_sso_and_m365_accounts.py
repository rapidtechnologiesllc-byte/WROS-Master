"""Sign in with Microsoft, the super-user-only Outlook skip, and Microsoft 365 accounts for new employees
(CEO 2026-11-27)."""
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.core.security import create_access_token
from app.models.role_template import RoleTemplate
from app.models.task import Task
from app.models.user import Users
from app.services import m365_account_service as m365


def _template(db, name, *, level=5):
    from tests.factories import tenant

    tenant(db)
    template = RoleTemplate(name=name, display_name=name, tenant_id=1, enabled=True, hierarchy_level=level)
    db.add(template)
    db.flush()
    return template


def _user(db, email, template, **fields):
    user = Users(UserID=f"u-{email.split('@')[0]}", UserName=fields.pop("name", "Asha Rao"), UserEmail=email,
                 UserPassword="!", UserRole=template.name, role_template_id=template.id, tenant_id=1, **fields)
    db.add(user)
    db.flush()
    return user


class FakeGraph:
    def __init__(self, existing=None, create_error=None):
        self.accounts = dict(existing or {})
        self.create_error = create_error
        self.created = []

    def get_user(self, upn):
        return self.accounts.get(upn.lower())

    def create_user(self, body):
        if self.create_error:
            raise self.create_error
        self.created.append(body)
        account = {"id": "oid-1", "userPrincipalName": body["userPrincipalName"], "assignedLicenses": []}
        self.accounts[body["userPrincipalName"]] = account
        return account


@pytest.fixture
def company_domain(monkeypatch):
    monkeypatch.setattr(m365.settings, "OUTLOOK_REQUIRED_DOMAINS", "blitzenx.com")


# --------------------------------------------------------------------------- Outlook skip

def test_only_the_ceo_may_skip_connect_outlook(db, company_domain):
    from app.api.v1.endpoints.msgraph import _requirement
    from app.core.config import settings

    admin = _user(db, "admin1@blitzenx.com", _template(db, "Users Admin T", level=settings.CEO_LEVEL - 1))
    ceo = _user(db, "ceo1@blitzenx.com", _template(db, "CEO T", level=settings.CEO_LEVEL))
    assert _requirement(db, admin) == {"required": True, "can_defer": False}
    assert _requirement(db, ceo) == {"required": True, "can_defer": True}


def test_outlook_not_required_outside_company_domains(db, company_domain):
    from app.api.v1.endpoints.msgraph import _requirement

    contractor = _user(db, "pat@vendor.example", _template(db, "Vendor T"))
    assert _requirement(db, contractor)["required"] is False


# --------------------------------------------------------------------------- Microsoft sign-in

def test_exchange_code_signs_in_without_the_email_code(db, client, monkeypatch):
    from app.api.v1.endpoints import auth as auth_endpoint

    user = _user(db, "sso1@blitzenx.com", _template(db, "SSO T"), password_reset_required=True)
    db.commit()
    monkeypatch.setattr(auth_endpoint.RoleTemplatePermissionService, "get_user_permissions",
                        lambda *a, **k: {"my-tasks": ["view"]})
    monkeypatch.setattr(auth_endpoint, "email_otp_enforcement_enabled", lambda: True)
    monkeypatch.setattr(auth_endpoint, "mfa_enforcement_enabled", lambda: False)
    code = create_access_token({"sub": user.UserID, "msgraph_sso_exchange": True}, timedelta(minutes=2))

    response = client.post("/api/v1/auth/microsoft/exchange", json={"code": code})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["entity_type"] == "user" and body["refresh_token"]
    assert not body.get("email_otp_required") and not body.get("force_password_reset")


def test_exchange_refuses_any_other_token(db, client):
    user = _user(db, "sso2@blitzenx.com", _template(db, "SSO T2"))
    db.commit()
    session_token = create_access_token({"sub": user.UserID, "type": "user", "tenant_id": 1,
                                          "role_template_id": user.role_template_id})
    assert client.post("/api/v1/auth/microsoft/exchange", json={"code": session_token}).status_code == 401
    assert client.post("/api/v1/auth/microsoft/exchange", json={"code": "garbage"}).status_code == 401


def test_sign_in_codes_never_work_as_a_session():
    from fastapi import HTTPException

    from app.core.dependencies import _reject_if_mfa_pending

    for claim in ("msgraph_sso", "msgraph_sso_exchange", "msgraph_link"):
        with pytest.raises(HTTPException):
            _reject_if_mfa_pending({"sub": "x", "type": "user", claim: True})


def test_sign_in_button_explains_when_microsoft_is_not_set_up(monkeypatch):
    from app.api.v1.endpoints import msgraph

    monkeypatch.setattr(msgraph, "graph_oauth_settings", lambda: {"configured": False})
    response = msgraph.signin()
    assert "sso_error=" in response.headers["location"]
    assert "None" not in response.headers["location"]


def test_callback_refuses_a_browser_that_did_not_start_the_sign_in(db):
    from app.api.v1.endpoints import msgraph

    request = SimpleNamespace(cookies={})
    response = msgraph._sso_callback(request, None, db, {"msgraph_sso": True, "nonce": "abc"}, "code")
    assert "sso_error=" in response.headers["location"]


# --------------------------------------------------------------------------- Microsoft 365 accounts

def test_new_employee_gets_an_account_and_it_admin_a_license_task(db, company_domain):
    user = _user(db, "new.joiner@blitzenx.com", _template(db, "Emp T"), name="New Joiner", job_title="Developer")
    graph = FakeGraph()

    result = m365.provision(db, user, graph)

    assert result == {"status": "license_task", "created": True}
    body = graph.created[0]
    assert body["userPrincipalName"] == "new.joiner@blitzenx.com" and body["mailNickname"] == "new.joiner"
    assert body["passwordProfile"]["forceChangePasswordNextSignIn"] is True
    tasks = db.query(Task).filter(Task.subcategory == user.UserID).all()
    assert [t.category for t in tasks] == [m365.LICENSE_TASK_CATEGORY]
    assert tasks[0].link.startswith("/") and body["passwordProfile"]["password"] not in tasks[0].description
    assert m365.mailbox_pending(db, user.UserID) is True

    # run again (re-sent welcome, scheduled check): still one task, no second account
    m365.provision(db, user, graph)
    assert len(graph.created) == 1
    assert db.query(Task).filter(Task.subcategory == user.UserID).count() == 1

    # IT Admin assigns the license: the check closes the task itself
    graph.accounts["new.joiner@blitzenx.com"]["assignedLicenses"] = [{"skuId": "sku"}]
    assert m365.provision(db, user, graph)["status"] == "licensed"
    db.expire_all()
    assert db.query(Task).filter(Task.subcategory == user.UserID).one().status == "COMPLETED"
    assert m365.mailbox_pending(db, user.UserID) is False


def test_existing_licensed_account_is_left_alone(db, company_domain):
    user = _user(db, "already@blitzenx.com", _template(db, "Emp T2"))
    graph = FakeGraph({"already@blitzenx.com": {"id": "x", "assignedLicenses": [{"skuId": "s"}]}})
    assert m365.provision(db, user, graph) == {"status": "licensed", "created": False}
    assert graph.created == []
    assert db.query(Task).filter(Task.subcategory == user.UserID).count() == 0


def test_without_permission_it_admin_creates_the_account(db, company_domain):
    user = _user(db, "noperm@blitzenx.com", _template(db, "Emp T3"))
    graph = FakeGraph(create_error=m365.GraphError(403, "Insufficient privileges"))
    assert m365.provision(db, user, graph)["status"] == "account_task"
    task = db.query(Task).filter(Task.subcategory == user.UserID).one()
    assert task.category == m365.ACCOUNT_TASK_CATEGORY and "User.ReadWrite.All" in task.description


def test_microsoft_outage_is_retried_not_tasked(db, company_domain):
    user = _user(db, "outage@blitzenx.com", _template(db, "Emp T4"))
    with pytest.raises(m365.GraphError):
        m365.provision(db, user, FakeGraph(create_error=m365.GraphError(503, "down")))
    assert db.query(Task).filter(Task.subcategory == user.UserID).count() == 0


def test_no_account_for_outside_mailboxes(db, company_domain):
    user = _user(db, "pat@vendor.example", _template(db, "Vendor T2"))
    graph = FakeGraph()
    assert m365.provision(db, user, graph)["status"] == "not_company_mailbox"
    assert m365.queue_provisioning(user) is False
    assert graph.created == []
