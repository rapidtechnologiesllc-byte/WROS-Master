"""
GET /sla/breaches -- HTTP wiring for S-020/HRMS-0420: recruiter-auth
import logging
gated, returns active NO_CONTACT breaches for the resolved tenant.

Throwaway SQLite app, throwaway JWT keys -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta

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
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation
from app.models.sla_breach import CandidateSLABreach
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

    from app.api.v1.endpoints.sla_breach import router as sla_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(sla_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword=get_password_hash("x"))
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    db.add_all([owner, candidate])
    db.commit()
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="awaiting_candidate", owner_type="ai_agent", owner_id="thunder")
    db.add(conv)
    db.commit()
    db.add(CandidateSLABreach(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, sla_type="NO_CONTACT", breached_at=datetime.utcnow() - timedelta(hours=2), is_resolved=False))
    db.commit()
    db.close()

    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for_user(email):
    return security.create_access_token(data={"sub": email, "type": "Super User"})


def test_list_breaches_returns_active_breach(client):
    resp = client.get("/sla/breaches?is_resolved=false", headers={"Authorization": f"Bearer {_token_for_user('ceo@blitzenx.com')}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 1
    assert body["breaches"][0]["candidate_name"] == "Priya"
    assert body["breaches"][0]["sla_type"] == "NO_CONTACT"


def test_list_breaches_requires_auth(client):
    resp = client.get("/sla/breaches?is_resolved=false")
    assert resp.status_code in (401, 403)


def test_resolved_true_is_rejected(client):
    resp = client.get("/sla/breaches?is_resolved=true", headers={"Authorization": f"Bearer {_token_for_user('ceo@blitzenx.com')}"})
    assert resp.status_code == 400
