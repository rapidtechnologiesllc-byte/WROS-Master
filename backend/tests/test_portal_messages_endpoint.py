"""
POST/GET /portal/conversations/{id}/messages -- proves the HTTP wiring:
real candidate JWT auth, cross-candidate 403, happy-path 201/200.
import logging
Business rules themselves are covered in test_portal_message_service.py.

Throwaway SQLite app, throwaway JWT keys -- never the real database.
No real Gemini call is made -- see the LLM mocking fixtures below;
without them, S-346's synchronous reply generation would hit the real
network (slow, flaky) on every POST in this file.
"""
import os
import tempfile
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.security as security
import app.services.prompt_framework_service as prompt_framework_svc
import app.services.thunder_service as thunder_svc
from app.core.security import get_password_hash
from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.user import Users
import app.models  # noqa: F401

@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setattr(thunder_svc, "GEMINI_API_KEY", "fake-key-for-test")

@pytest.fixture(autouse=True)
def _mock_gemini(monkeypatch):
    mock_response = MagicMock()
    mock_response.content = "Real Thunder reply text, long enough to pass validation."
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    monkeypatch.setattr(thunder_svc, "ChatGoogleGenerativeAI", MagicMock(return_value=mock_llm))

@pytest.fixture(autouse=True)
def _mock_intent_and_escalation_llm(monkeypatch):
    monkeypatch.setattr(prompt_framework_svc, "_default_llm_call", lambda *a, **k: '{"intent": "unclear", "confidence": 0.0}')

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

    from app.api.v1.endpoints.portal_messages import router as portal_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(portal_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate_a = Candidate(candidateID="C-A", candidateEmail="a@example.com", candidatePassword=get_password_hash("x"))
    candidate_b = Candidate(candidateID="C-B", candidateEmail="b@example.com", candidatePassword=get_password_hash("x"))
    db.add_all([owner, candidate_a, candidate_b])
    db.commit()
    conversation_a = CandidateConversation(tenant_id=owner.UserID, candidate_id="C-A", status="open", owner_type="ai_agent", owner_id="thunder")
    db.add(conversation_a)
    db.commit()
    conv_id = conversation_a.id
    db.close()

    test_client = TestClient(app)
    try:
        yield test_client, conv_id
    finally:
        engine.dispose()
        os.remove(db_path)

def _token_for(candidate_id):
    return security.create_access_token(data={"sub": candidate_id, "type": "candidate", "name": candidate_id})

def test_post_message_happy_path_returns_201(client):
    test_client, conv_id = client
    resp = test_client.post(
        f"/portal/conversations/{conv_id}/messages",
        json={"message_body": "Hello Thunder"},
        headers={"Authorization": f"Bearer {_token_for('C-A')}"},
    )
    assert resp.status_code == 201
    assert resp.json()["message_id"] is not None

def test_post_message_cross_candidate_returns_403(client):
    test_client, conv_id = client
    resp = test_client.post(
        f"/portal/conversations/{conv_id}/messages",
        json={"message_body": "sneaky"},
        headers={"Authorization": f"Bearer {_token_for('C-B')}"},
    )
    assert resp.status_code == 403

def test_post_message_no_token_returns_403(client):
    test_client, conv_id = client
    resp = test_client.post(f"/portal/conversations/{conv_id}/messages", json={"message_body": "hi"})
    assert resp.status_code in (401, 403)

def test_get_history_after_posting_returns_message(client):
    test_client, conv_id = client
    token = _token_for("C-A")
    test_client.post(
        f"/portal/conversations/{conv_id}/messages", json={"message_body": "Hello"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = test_client.get(f"/portal/conversations/{conv_id}/messages", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    # S-346: the candidate's message plus its real (mocked) auto-reply.
    assert body["total_count"] == 2
    assert body["messages"][0]["message_body"] == "Hello"
    assert body["messages"][1]["message_body"] == "Real Thunder reply text, long enough to pass validation."
