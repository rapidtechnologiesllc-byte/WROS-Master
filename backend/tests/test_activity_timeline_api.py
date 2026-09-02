"""
S-216/HRMS-0118 -- proves the real routes, not just the service layer.
Specifically covers a routing-order bug caught before it shipped:
GET /file-uploads/{file_id}/access-url must resolve to the access-url
handler, not get swallowed by GET /file-uploads/{entity_type}/{entity_id}
import logging
treating "access-url" as an entity_id.

Throwaway SQLite, throwaway JWT keys -- never the real database.
"""
import io
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
import app.services.file_upload_service as upload_svc
from app.models.base import Base
from app.models.tenant import Tenant
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
    monkeypatch.setattr(
        upload_svc, "_upload_to_sharepoint",
        lambda access_token, entity_type, entity_id, file_content, unique_filename: {
            "webUrl": f"https://sharepoint.example/{entity_type}/{entity_id}/{unique_filename}"
        },
    )
    monkeypatch.setattr(upload_svc, "get_graph_token", lambda: "fake-token")

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

    from app.api.v1.endpoints.activity_timeline import router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()
    from app.core.security import get_password_hash
    db.add(Users(
        UserID="U-1", UserRole="Recruiter", UserEmail="rec@blitzenx.com",
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


def _auth():
    token = security.create_access_token(data={"sub": "rec@blitzenx.com", "type": "Recruiter", "name": "rec@blitzenx.com"})
    return {"Authorization": f"Bearer {token}"}


def test_upload_then_access_url_route_resolves_correctly_not_swallowed(client):
    upload_resp = client.post(
        "/file-uploads/candidate/C-1",
        params={"file_category": "RESUME"},
        files={"file": ("resume.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        headers=_auth(),
    )
    assert upload_resp.status_code == 200, upload_resp.text
    file_id = upload_resp.json()["id"]
    # Default unconfigured scanner -> QUARANTINED -> no access URL yet.
    assert upload_resp.json()["scan_status"] == "QUARANTINED"

    access_resp = client.get(f"/file-uploads/{file_id}/access-url", headers=_auth())
    assert access_resp.status_code == 200
    # Proves the route resolved to the real access-url handler (returns
    # a real {"access_url": ...} shape) rather than being swallowed by
    # the /{entity_type}/{entity_id} list route, which would 200 with a
    # completely different (list) response shape or an empty list.
    assert "access_url" in access_resp.json()
    assert access_resp.json()["access_url"] is None  # quarantined, not clean


def test_timeline_and_file_list_real_routes(client):
    client.post(
        "/activity-timeline/candidate/C-1",
        json={"action": "NOTE_ADDED", "description": "Called candidate"},
        headers=_auth(),
    )
    resp = client.get("/activity-timeline/candidate/C-1", headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["entries"][0]["action"] == "NOTE_ADDED"

    list_resp = client.get("/file-uploads/candidate/C-1", headers=_auth())
    assert list_resp.status_code == 200
    assert list_resp.json() == []
