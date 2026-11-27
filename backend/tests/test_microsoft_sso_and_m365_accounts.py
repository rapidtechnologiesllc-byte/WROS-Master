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
    def __init__(self, existing=None, create_error=None, lookup_error=None, aliases=None):
        self.accounts = dict(existing or {})
        self.create_error = create_error
        self.lookup_error = lookup_error
        self.aliases = dict(aliases or {})
        self.created = []

    def get_user(self, upn):
        return self.accounts.get(upn.lower())

    def find_user(self, address):
        if self.lookup_error:
            raise self.lookup_error
        return self.get_user(address) or self.aliases.get(address.lower())

    def create_user(self, body):
        if self.create_error:
            raise self.create_error
        self.created.append(body)
        account = {"id": "oid-1", "userPrincipalName": body["userPrincipalName"], "assignedLicenses": []}
        self.accounts[body["userPrincipalName"]] = account
        return account


@pytest.fixture
def company_domain(monkeypatch):
    from app.api.v1.endpoints import msgraph

    monkeypatch.setattr(m365.settings, "OUTLOOK_REQUIRED_DOMAINS", "blitzenx.com")
    monkeypatch.setattr(msgraph, "graph_oauth_settings", lambda: {"configured": True, "scopes": []})
    monkeypatch.setattr(msgraph, "REDIRECT_URI", "https://hrms.example/msgraph/auth/callback")


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
    code = create_access_token({"sub": user.UserID, "msgraph_sso_exchange": True, "jti": f"j-{user.UserID}"},
                               timedelta(minutes=2))

    response = client.post("/api/v1/auth/microsoft/exchange", json={"code": code})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["entity_type"] == "user" and body["refresh_token"]
    assert not body.get("email_otp_required") and not body.get("force_password_reset")
    # the same code twice: refused (single use)
    assert client.post("/api/v1/auth/microsoft/exchange", json={"code": code}).status_code == 401


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


def test_outlook_is_not_required_when_microsoft_is_not_set_up(db, monkeypatch):
    from app.api.v1.endpoints import msgraph

    monkeypatch.setattr(m365.settings, "OUTLOOK_REQUIRED_DOMAINS", "blitzenx.com")
    monkeypatch.setattr(msgraph, "graph_oauth_settings", lambda: {"configured": False})
    staff = _user(db, "staff9@blitzenx.com", _template(db, "Staff T9"))
    assert msgraph._requirement(db, staff)["required"] is False


def test_a_refused_lookup_asks_it_admin_and_does_not_hold_the_welcome(db, company_domain):
    user = _user(db, "noread@blitzenx.com", _template(db, "Emp T5"))
    graph = FakeGraph(lookup_error=m365.GraphError(403, "Insufficient privileges"))
    assert m365.provision(db, user, graph)["status"] == "account_task"
    assert db.query(Task).filter(Task.subcategory == user.UserID).one().category == m365.ACCOUNT_TASK_CATEGORY
    assert graph.created == []
    assert m365.mailbox_pending(db, user.UserID) is False  # it may exist: the welcome goes out


def test_an_existing_account_under_an_alias_is_not_created_twice(db, company_domain):
    user = _user(db, "alias@blitzenx.com", _template(db, "Emp T6"))
    graph = FakeGraph(aliases={"alias@blitzenx.com": {"id": "x", "assignedLicenses": [{"skuId": "s"}]}})
    assert m365.provision(db, user, graph) == {"status": "licensed", "created": False}
    assert graph.created == []


def test_provisioning_gives_up_after_a_day_and_asks_it_admin(db, company_domain, monkeypatch):
    from datetime import datetime

    from app.services.message_handlers.provision_m365_account_handler import ProvisionM365AccountHandler

    user = _user(db, "slow@blitzenx.com", _template(db, "Emp T7"))
    db.commit()
    monkeypatch.setattr(m365, "graph_configured", lambda: False)
    old = SimpleNamespace(id="m1", payload={"user_id": user.UserID}, created_at=datetime.utcnow() - timedelta(days=2))
    result = ProvisionM365AccountHandler.process.__wrapped__(old, db) if hasattr(
        ProvisionM365AccountHandler.process, "__wrapped__") else ProvisionM365AccountHandler.process(old, db)
    assert result["status"] == "account_task"


def test_password_reset_is_never_held_for_the_mailbox(db, company_domain, monkeypatch):
    from app.services.message_handlers import send_account_email_handler as handler

    user = _user(db, "reset@blitzenx.com", _template(db, "Emp T8"))
    m365.provision(db, user, FakeGraph())  # account created, unlicensed: an ACTIVATE welcome would wait
    db.commit()
    assert m365.mailbox_pending(db, user.UserID) is True
    sent = []

    class Mailbox:
        def create_draft(self, *a):
            sent.append(a)
            return ("draft-1", None, None)

        def is_draft(self, _):
            return True

        def send(self, _):
            pass

    message = SimpleNamespace(id="m2", payload={"user_id": user.UserID, "purpose": "RESET"})
    handler.SendAccountEmailHandler.process(message, db, mailbox=Mailbox())
    assert sent  # not deferred


def test_sign_in_is_refused_when_two_accounts_share_the_address(db, company_domain, monkeypatch):
    from app.api.v1.endpoints import msgraph

    for i in range(2):
        _user(db, "Twin@blitzenx.com" if i else "twin@blitzenx.com", _template(db, f"Twin T{i}"))
    db.flush()

    class Msal:
        def acquire_token_by_authorization_code(self, *a, **k):
            return {"access_token": "t", "id_token_claims": {"preferred_username": "twin@blitzenx.com", "oid": "o"}}

    monkeypatch.setattr(msgraph, "_msal_client", lambda: Msal())
    request = SimpleNamespace(cookies={msgraph.SSO_NONCE_COOKIE: "n"})
    response = msgraph._sso_callback(request, None, db, {"msgraph_sso": True, "nonce": "n"}, "code")
    assert "sso_error=" in response.headers["location"]
