"""
S-213/HRMS-0115 -- proves BR-0115-01 (Admin-only write) and BR-0115-03
(BU-override-via-header) on real routes, not just the service in
isolation. Throwaway SQLite, throwaway JWT keys -- never the real database.
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
from app.models.rbac import BusinessUnit
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

    from app.api.v1.endpoints.system_config import router as system_config_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(system_config_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    from app.core.security import get_password_hash

    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()

    bu = BusinessUnit(name="Delivery", tenant_id=tenant.id)
    db.add(bu)
    db.commit()

    db.add(Users(
        UserID="U-ADMIN", UserRole="Admin", UserEmail="admin@blitzenx.com",
        UserPassword=get_password_hash("x"), tenant_id=tenant.id,
    ))
    db.add(Users(
        UserID="U-REC", UserRole="Recruiter", UserEmail="recruiter@blitzenx.com",
        UserPassword=get_password_hash("x"), tenant_id=tenant.id,
    ))
    db.commit()

    from app.models.bu_access import BUAccess
    db.add(BUAccess(user_id="U-ADMIN", business_unit_id=bu.id, is_default=True))
    db.commit()

    ids = {"bu_id": bu.id}
    db.close()

    test_client = TestClient(app)
    test_client.wros_ids = ids
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _auth(email, role):
    token = security.create_access_token(data={"sub": email, "type": role, "name": email})
    return {"Authorization": f"Bearer {token}"}


def test_non_admin_write_rejected(client):
    resp = client.put(
        "/system-config/settings/business_hours_start",
        json={"value": 9},
        headers=_auth("recruiter@blitzenx.com", "Recruiter"),
    )
    assert resp.status_code == 403


def test_admin_write_then_read_reflects_change(client):
    write_resp = client.put(
        "/system-config/settings/business_hours_start",
        json={"value": 9},
        headers=_auth("admin@blitzenx.com", "Admin"),
    )
    assert write_resp.status_code == 200, write_resp.text

    read_resp = client.get("/system-config/settings", headers=_auth("admin@blitzenx.com", "Admin"))
    assert read_resp.status_code == 200
    channels = {item["config_key"]: item["value"] for item in read_resp.json()["CHANNELS"]}
    assert channels["business_hours_start"] == 9


def test_bu_scoped_write_requires_valid_bu_header(client):
    bu_id = client.wros_ids["bu_id"]
    resp = client.put(
        "/system-config/settings/business_hours_start",
        json={"value": 7},
        headers={**_auth("admin@blitzenx.com", "Admin"), "X-Active-BU-Id": str(bu_id)},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["business_unit_id"] == bu_id

    # A BU id the admin has no access to is rejected, not silently trusted.
    forged = client.put(
        "/system-config/settings/business_hours_start",
        json={"value": 6},
        headers={**_auth("admin@blitzenx.com", "Admin"), "X-Active-BU-Id": "99999"},
    )
    assert forged.status_code == 403


def test_settings_response_includes_locale_from_real_tenant_columns(client):
    resp = client.get("/system-config/settings", headers=_auth("admin@blitzenx.com", "Admin"))
    assert resp.status_code == 200
    assert resp.json()["LOCALE"]["default_currency"] == "USD"
