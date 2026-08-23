"""
EPIC-14/S-379 (HRMS-1401) -- M365 Launchpad account linking.
GET /msgraph/link/start, GET /msgraph/link-status, POST /msgraph/unlink,
and /auth/callback's account-linking branch (an already-logged-in WROS
user links their M365 account without their WROS session token being
silently swapped out).

Throwaway SQLite app, throwaway JWT keys -- never the real database,
never a real Microsoft account (msal + Graph /me calls are monkeypatched).
"""
import os
import tempfile

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.security as security
from app.core.security import get_password_hash
from app.models.base import Base
from app.models.user import Users
import app.models  # noqa: F401


@pytest.fixture()
def throwaway_jwt_keys(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    monkeypatch.setattr(security, "PRIVATE_KEY", private_pem)
    monkeypatch.setattr(security, "PUBLIC_KEY", public_pem)


@pytest.fixture()
def client(throwaway_jwt_keys, monkeypatch):
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    import app.api.v1.endpoints.msgraph as msgraph_module
    from app.core.database import get_db

    monkeypatch.setattr(msgraph_module, "user_tokens", {})
    monkeypatch.setattr(msgraph_module, "_account_id_by_user_id", {})
    monkeypatch.setattr(msgraph_module, "redirect_url", "https://hrms.example.com/")

    app = FastAPI()
    app.include_router(msgraph_module.router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    db.add(Users(UserID="U-A", UserRole="Recruiter", UserEmail="a@blitzenx.com", UserPassword=get_password_hash("x")))
    db.add(Users(UserID="U-B", UserRole="Recruiter", UserEmail="b@blitzenx.com", UserPassword=get_password_hash("x")))
    db.commit()
    db.close()

    test_client = TestClient(app, follow_redirects=False)
    try:
        yield test_client, msgraph_module
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(email):
    return security.create_access_token(data={"sub": email})


def _auth(email):
    return {"Authorization": f"Bearer {_token_for(email)}"}


# ---- /link/start, /link-status, /unlink ----

def test_link_status_false_when_not_linked(client):
    test_client, _ = client
    resp = test_client.get("/msgraph/link-status", headers=_auth("a@blitzenx.com"))
    assert resp.status_code == 200
    assert resp.json() == {"linked": False}


def test_link_status_true_once_linked(client):
    test_client, msgraph_module = client
    msgraph_module._account_id_by_user_id["U-A"] = "oid-a"
    msgraph_module.user_tokens["oid-a"] = {"access_token": "fake"}

    resp = test_client.get("/msgraph/link-status", headers=_auth("a@blitzenx.com"))
    assert resp.json() == {"linked": True}


def test_link_start_returns_auth_url_carrying_a_real_state_token(client):
    test_client, msgraph_module = client
    resp = test_client.get("/msgraph/link/start", headers=_auth("a@blitzenx.com"))
    assert resp.status_code == 200
    auth_url = resp.json()["auth_url"]
    assert auth_url.startswith("https://login.microsoftonline.com/") or "oauth2/v2.0/authorize" in auth_url
    assert "state=" in auth_url


def test_unlink_clears_the_mapping_and_token(client):
    test_client, msgraph_module = client
    msgraph_module._account_id_by_user_id["U-A"] = "oid-a"
    msgraph_module.user_tokens["oid-a"] = {"access_token": "fake"}

    resp = test_client.post("/msgraph/unlink", headers=_auth("a@blitzenx.com"))
    assert resp.json() == {"linked": False}
    assert "U-A" not in msgraph_module._account_id_by_user_id
    assert "oid-a" not in msgraph_module.user_tokens


def test_unauthenticated_requests_are_rejected(client):
    test_client, _ = client
    assert test_client.get("/msgraph/link-status").status_code in (401, 403)
    assert test_client.get("/msgraph/link/start").status_code in (401, 403)
    assert test_client.post("/msgraph/unlink").status_code in (401, 403)


# ---- /auth/callback linking branch ----

def _mock_msal_and_graph_me(monkeypatch, msgraph_module, *, oid="new-ms-oid", email="a@blitzenx.com"):
    class _FakeMsal:
        def acquire_token_by_authorization_code(self, code, scopes, redirect_uri):
            return {
                "access_token": "fake-access-token",
                "id_token_claims": {"oid": oid},
            }

    monkeypatch.setattr(msgraph_module, "_msal_client", lambda: _FakeMsal())

    class _FakeGraphMeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"mail": email, "displayName": "A User", "id": oid}

    monkeypatch.setattr(msgraph_module.requests, "get", lambda *a, **k: _FakeGraphMeResponse())


def test_callback_with_valid_link_state_links_existing_user_without_new_wros_token(client, monkeypatch):
    test_client, msgraph_module = client
    _mock_msal_and_graph_me(monkeypatch, msgraph_module, oid="oid-for-a", email="a@blitzenx.com")

    link_start = test_client.get("/msgraph/link/start", headers=_auth("a@blitzenx.com"))
    from urllib.parse import urlparse, parse_qs
    state = parse_qs(urlparse(link_start.json()["auth_url"]).query)["state"][0]

    resp = test_client.get("/msgraph/auth/callback", params={"code": "fake-code", "state": state})

    assert resp.status_code == 307
    assert resp.headers["location"] == "https://hrms.example.com/m365?linked=true"
    # No "?token=" WROS-session param on the redirect -- the caller's
    # existing WROS session is untouched, exactly the point of this path.
    assert "token=" not in resp.headers["location"]
    assert msgraph_module._account_id_by_user_id["U-A"] == "oid-for-a"
    assert msgraph_module.user_tokens["oid-for-a"]["access_token"] == "fake-access-token"


def test_callback_without_link_state_uses_original_login_flow_unchanged(client, monkeypatch):
    """The old hardcoded 'xyz' default (or any non-link state) must
    fall through to byte-for-byte the original behavior: a fresh WROS
    JWT minted and appended to the redirect."""
    test_client, msgraph_module = client
    _mock_msal_and_graph_me(monkeypatch, msgraph_module, oid="oid-plain-login", email="a@blitzenx.com")

    resp = test_client.get("/msgraph/auth/callback", params={"code": "fake-code", "state": "xyz"})

    assert resp.status_code == 307
    assert resp.headers["location"].startswith("https://hrms.example.com/?token=")
    assert msgraph_module._account_id_by_user_id["U-A"] == "oid-plain-login"


def test_callback_link_state_for_a_since_deleted_user_falls_back_to_login_flow(client, monkeypatch):
    """A stale/tampered state naming a user row that no longer exists
    must not crash the callback -- fail open to the original login path
    rather than a dead end."""
    test_client, msgraph_module = client
    _mock_msal_and_graph_me(monkeypatch, msgraph_module, oid="oid-ghost", email="ghost@blitzenx.com")

    ghost_state = security.create_access_token(data={"sub": "ghost@blitzenx.com", "msgraph_link": True})
    resp = test_client.get("/msgraph/auth/callback", params={"code": "fake-code", "state": ghost_state})

    assert resp.status_code == 307
    assert resp.headers["location"].startswith("https://hrms.example.com/?token=")


def test_a_full_wros_token_cannot_be_used_as_a_link_state(client, monkeypatch):
    """A normal, already-issued WROS access token must not be accepted
    as a link-state token even though decode_access_token() can parse
    it -- only a token carrying msgraph_link=True counts."""
    test_client, msgraph_module = client
    _mock_msal_and_graph_me(monkeypatch, msgraph_module, oid="oid-x", email="a@blitzenx.com")

    normal_token = security.create_access_token(data={"sub": "a@blitzenx.com", "type": "Recruiter"})
    resp = test_client.get("/msgraph/auth/callback", params={"code": "fake-code", "state": normal_token})

    # Falls through to the plain login flow -- proves msgraph_link=True
    # is genuinely required, not just "any decodable token".
    assert resp.headers["location"].startswith("https://hrms.example.com/?token=")
