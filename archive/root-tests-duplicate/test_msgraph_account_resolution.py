"""
app.api.v1.endpoints.msgraph -- _require_account() identity resolution.

Real bug fix, 2026-08-05: this used to trust a raw `account_id` cookie
that /auth/callback never actually set (confirmed by grep -- no
set_cookie call exists anywhere in the module), so every real call
through it 401'd, silently breaking "Schedule Interview"'s Microsoft
Teams meeting creation. Even if the cookie had been wired up naively,
trusting an unsigned client value as a direct key into `user_tokens`
(real Graph access tokens) with no cross-check against the actual
authenticated caller would be a real IDOR. Fixed to derive identity
from the same JWT (Depends(get_current_hr_or_admin)) every other
"resolve MY OWN data" endpoint in this codebase already uses.

Throwaway SQLite app, throwaway JWT keys -- never the real database,
never a real Microsoft account.
"""
import os
import tempfile

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import Depends, FastAPI, HTTPException
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

    # Isolate the module-level in-memory stores per test -- they're
    # process-global in the real app, which would otherwise leak state
    # between tests (and between real requests, a separate known
    # limitation already flagged in the module's own comments).
    monkeypatch.setattr(msgraph_module, "user_tokens", {})
    monkeypatch.setattr(msgraph_module, "_account_id_by_user_id", {})

    probe_app = FastAPI()

    @probe_app.get("/probe/require-account")
    def probe(account_id: str = Depends(msgraph_module._require_account)):
        return {"account_id": account_id}

    probe_app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    user_a = Users(UserID="U-A", UserRole="employee", UserEmail="a@blitzenx.com", UserPassword=get_password_hash("x"))
    user_b = Users(UserID="U-B", UserRole="employee", UserEmail="b@blitzenx.com", UserPassword=get_password_hash("x"))
    db.add_all([user_a, user_b])
    db.commit()
    db.close()

    test_client = TestClient(probe_app)
    try:
        yield test_client, msgraph_module
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(email):
    return security.create_access_token(data={"sub": email})


def test_unlinked_account_raises_401(client):
    test_client, _ = client
    resp = test_client.get("/probe/require-account", headers={"Authorization": f"Bearer {_token_for('a@blitzenx.com')}"})
    assert resp.status_code == 401


def test_linked_account_resolves_correctly(client):
    test_client, msgraph_module = client
    msgraph_module._account_id_by_user_id["U-A"] = "graph-oid-for-a"
    msgraph_module.user_tokens["graph-oid-for-a"] = {"access_token": "fake"}

    resp = test_client.get("/probe/require-account", headers={"Authorization": f"Bearer {_token_for('a@blitzenx.com')}"})
    assert resp.status_code == 200
    assert resp.json()["account_id"] == "graph-oid-for-a"


def test_one_user_never_resolves_another_users_account(client):
    """The real IDOR this fix closes: User A must never be able to
    obtain User B's Graph token by any means available through this
    dependency."""
    test_client, msgraph_module = client
    msgraph_module._account_id_by_user_id["U-A"] = "graph-oid-for-a"
    msgraph_module._account_id_by_user_id["U-B"] = "graph-oid-for-b"
    msgraph_module.user_tokens["graph-oid-for-a"] = {"access_token": "fake-a"}
    msgraph_module.user_tokens["graph-oid-for-b"] = {"access_token": "fake-b"}

    resp_a = test_client.get("/probe/require-account", headers={"Authorization": f"Bearer {_token_for('a@blitzenx.com')}"})
    resp_b = test_client.get("/probe/require-account", headers={"Authorization": f"Bearer {_token_for('b@blitzenx.com')}"})

    assert resp_a.json()["account_id"] == "graph-oid-for-a"
    assert resp_b.json()["account_id"] == "graph-oid-for-b"


def test_stale_mapping_without_live_token_raises_401(client):
    """A mapping can exist without a live token (e.g. server restarted,
    in-memory user_tokens cleared) -- must fail closed, not return a
    dangling account_id the caller can't actually use."""
    test_client, msgraph_module = client
    msgraph_module._account_id_by_user_id["U-A"] = "graph-oid-for-a"
    # deliberately NOT populating user_tokens["graph-oid-for-a"]

    resp = test_client.get("/probe/require-account", headers={"Authorization": f"Bearer {_token_for('a@blitzenx.com')}"})
    assert resp.status_code == 401
