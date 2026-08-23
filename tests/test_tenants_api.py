"""
GET/PATCH /tenants/me/locale -- proves S-219/HRMS-0121 (Multi-Continent
Locale & Currency Config) end-to-end. Genuinely new backend -- no
Tenant-config model, service, or REST layer existed before this.

Throwaway SQLite app, throwaway JWT keys -- never the real database or
real signing keys.
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
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import Users
import app.models  # noqa: F401 -- registers every model on Base.metadata


@pytest.fixture()
def throwaway_jwt_keys(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    monkeypatch.setattr(security, "PRIVATE_KEY", private_pem)
    monkeypatch.setattr(security, "PUBLIC_KEY", public_pem)


@pytest.fixture()
def client(throwaway_jwt_keys):
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

    from app.api.v1.endpoints.tenants import router as tenants_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(tenants_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    from app.core.security import get_password_hash

    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()

    db.add(Users(
        UserID="U-ADMIN", UserRole="Admin", UserEmail="admin@blitzenx.com",
        UserPassword=get_password_hash("x"), tenant_id=tenant.id,
    ))
    db.commit()
    db.close()

    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(email, role="Admin"):
    return security.create_access_token(data={"sub": email, "type": role, "name": email})


def _auth():
    return {"Authorization": f"Bearer {_token_for('admin@blitzenx.com')}"}


def test_unauthenticated_request_is_rejected(client):
    resp = client.get("/tenants/me/locale")
    assert resp.status_code in (401, 403)


def test_get_locale_defaults(client):
    resp = client.get("/tenants/me/locale", headers=_auth())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["default_timezone"] == "UTC"
    assert body["default_date_format"] == "MM/DD/YYYY"
    assert body["default_currency"] == "USD"


def test_update_locale_partial(client):
    resp = client.patch(
        "/tenants/me/locale",
        json={"default_timezone": "Asia/Kolkata", "default_currency": "INR"},
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["default_timezone"] == "Asia/Kolkata"
    assert body["default_currency"] == "INR"
    # date format untouched by the partial update
    assert body["default_date_format"] == "MM/DD/YYYY"

    # persists across requests
    get_resp = client.get("/tenants/me/locale", headers=_auth())
    assert get_resp.json()["default_currency"] == "INR"


def test_update_locale_rejects_invalid_currency(client):
    resp = client.patch(
        "/tenants/me/locale",
        json={"default_currency": "JPY"},
        headers=_auth(),
    )
    assert resp.status_code == 422


def test_update_locale_rejects_invalid_date_format(client):
    resp = client.patch(
        "/tenants/me/locale",
        json={"default_date_format": "not-a-format"},
        headers=_auth(),
    )
    assert resp.status_code == 422
