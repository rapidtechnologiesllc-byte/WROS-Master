"""
GET /ai-agent/memory/{candidate_id} -- HTTP wiring for S-021/HRMS-0421.
Routed under /ai-agent (not /candidates/{id}/memory) matching this
round's convention of hosting Thunder-intelligence candidate-scoped
reads there (missing-fields, portal-link).

Throwaway SQLite app, throwaway JWT keys -- never the real database.
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
from app.models.candidate import Candidate
from app.models.user import Users
import app.models  # noqa: F401

import app.services.candidate_memory_service as memory_svc


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

    from app.api.v1.endpoints.ai_agent import router as ai_agent_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(ai_agent_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword=get_password_hash("x"))
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    db.add_all([owner, candidate])
    db.commit()
    memory_svc.upsert_fact(db, "C-1", "U-ORG", "SALARY", "expected_ctc", "24 LPA", confidence=0.9)
    db.commit()
    db.close()

    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(email):
    return security.create_access_token(data={"sub": email, "type": "Super User"})


def test_get_memory_returns_facts(client):
    resp = client.get("/ai-agent/memory/C-1", headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com')}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidate_id"] == "C-1"
    assert body["summary"] is None
    assert len(body["facts"]) == 1
    assert body["facts"][0]["key"] == "expected_ctc"


def test_get_memory_requires_auth(client):
    resp = client.get("/ai-agent/memory/C-1")
    assert resp.status_code in (401, 403)


def test_get_memory_unknown_candidate_404(client):
    resp = client.get("/ai-agent/memory/NOPE", headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com')}"})
    assert resp.status_code == 404


def test_get_memory_includes_fact_id(client):
    resp = client.get("/ai-agent/memory/C-1", headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com')}"})
    fact = resp.json()["facts"][0]
    assert "id" in fact


def test_patch_fact_correction_updates_value_and_confidence(client):
    get_resp = client.get("/ai-agent/memory/C-1", headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com')}"})
    fact_id = get_resp.json()["facts"][0]["id"]

    patch_resp = client.patch(
        f"/ai-agent/memory/C-1/facts/{fact_id}",
        json={"fact_value": "26 LPA"},
        headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com')}"},
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["value"] == "26 LPA"
    assert body["confidence"] == 1.0


def test_patch_fact_correction_unknown_fact_404(client):
    resp = client.patch(
        "/ai-agent/memory/C-1/facts/999999",
        json={"fact_value": "x"},
        headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com')}"},
    )
    assert resp.status_code == 404


def test_patch_fact_correction_requires_auth(client):
    resp = client.patch("/ai-agent/memory/C-1/facts/1", json={"fact_value": "x"})
    assert resp.status_code in (401, 403)
