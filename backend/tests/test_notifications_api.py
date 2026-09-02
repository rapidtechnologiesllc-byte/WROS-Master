"""
GET /notifications, POST /notifications/{id}/mark-read -- proves
S-105/HRMS-P210 (Portal Notification Center) end-to-end on real routes.
Wires the pre-existing, already-shipped HRMS-0113 notification engine
(send_notification()/get_unread_count()/mark_as_read(), already called
by other stories this session) whose own model docstring flagged "no
import logging
nav-shell UI" as the one real gap.

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

    from app.api.v1.endpoints.notifications import router as notifications_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(notifications_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    from app.core.security import get_password_hash

    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()

    admin = Users(
        UserID="U-ADMIN", UserRole="Admin", UserEmail="admin@blitzenx.com",
        UserPassword=get_password_hash("x"), tenant_id=tenant.id,
    )
    db.add(admin)
    db.commit()

    ids = {"tenant_id": tenant.id, "user_id": admin.UserID}
    db.close()

    test_client = TestClient(app)
    test_client.wros_ids = ids
    test_client.db_url = f"sqlite:///{db_path}"
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(email, role="Admin"):
    return security.create_access_token(data={"sub": email, "type": role, "name": email})


def _auth():
    return {"Authorization": f"Bearer {_token_for('admin@blitzenx.com')}"}


def _seed_notification(client, *, message="SLA breach on demand X", priority_tier="P0"):
    from app.models.user import Users
    from app.services.notification_service import send_notification

    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    recipient = session.query(Users).filter(Users.UserID == client.wros_ids["user_id"]).first()
    notification = send_notification(
        session, calling_context_tenant_id=client.wros_ids["tenant_id"], recipient=recipient,
        priority_tier=priority_tier, message=message, channel_preference="IN_APP",
    )
    session.commit()
    notification_id = notification.id
    session.close()
    engine.dispose()
    return notification_id


def test_unauthenticated_request_is_rejected(client):
    resp = client.get("/notifications")
    assert resp.status_code in (401, 403)


def test_list_notifications_empty(client):
    resp = client.get("/notifications", headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert body["notifications"] == []
    assert body["unread_count"] == 0


def test_list_notifications_returns_sent_in_app_feed(client):
    _seed_notification(client, message="New interview scheduled")
    resp = client.get("/notifications", headers=_auth())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["notifications"]) == 1
    assert body["notifications"][0]["message"] == "New interview scheduled"
    assert body["notifications"][0]["delivery_status"] == "SENT"
    assert body["unread_count"] == 1


def test_mark_read_reduces_unread_count(client):
    notification_id = _seed_notification(client)
    mark_resp = client.post(f"/notifications/{notification_id}/mark-read", headers=_auth())
    assert mark_resp.status_code == 200, mark_resp.text
    assert mark_resp.json()["read_at"] is not None

    list_resp = client.get("/notifications", headers=_auth())
    assert list_resp.json()["unread_count"] == 0


def test_mark_read_404_for_unknown_id(client):
    resp = client.post("/notifications/does-not-exist/mark-read", headers=_auth())
    assert resp.status_code == 404
