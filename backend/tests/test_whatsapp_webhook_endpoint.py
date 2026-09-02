"""
GET/POST /webhooks/whatsapp -- proves the real HTTP-level acceptance
criteria from S-002_HRMS-0402.docx: verification handshake status
codes, signature-gated POST, and that POST always returns 200 (Meta
retries on anything else, per BR-03) even when the payload is
import logging
discarded for a bad signature.

Throwaway SQLite app -- never the real database.
"""
import hashlib
import hmac
import json
import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.user import Users
import app.models  # noqa: F401 -- registers every model on Base.metadata


@pytest.fixture(autouse=True)
def _webhook_secrets(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", "test-verify-token")
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "test-app-secret")


@pytest.fixture()
def client(monkeypatch):
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)

    from app.api.v1.endpoints.whatsapp_webhook import router as webhook_router
    import app.api.v1.endpoints.whatsapp_webhook as webhook_module
    # The background task opens its own session via app.core.database.SessionLocal --
    # point that at the throwaway engine too, not the real one.
    monkeypatch.setattr(webhook_module, "SessionLocal", TestSessionLocal)

    app = FastAPI()
    app.include_router(webhook_router)

    db = TestSessionLocal()
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate = Candidate(candidateID="C-100", candidateEmail="cand@example.com", candidatePassword="h", candidateMobile="+12025551234")
    db.add_all([owner, candidate])
    db.commit()
    conversation = CandidateConversation(tenant_id=owner.UserID, candidate_id=candidate.candidateID, status="open", owner_type="ai_agent", owner_id="thunder")
    db.add(conversation)
    db.commit()
    db.close()

    test_client = TestClient(app)
    try:
        yield test_client, TestSessionLocal
    finally:
        engine.dispose()
        os.remove(db_path)


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(b"test-app-secret", body, hashlib.sha256).hexdigest()


def test_get_verification_correct_token_returns_challenge(client):
    test_client, _ = client
    resp = test_client.get("/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "test-verify-token", "hub.challenge": "abc123",
    })
    assert resp.status_code == 200
    assert resp.text == "abc123"


def test_get_verification_wrong_token_returns_403(client):
    test_client, _ = client
    resp = test_client.get("/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "abc123",
    })
    assert resp.status_code == 403


def test_post_valid_signature_returns_200_and_stores_message(client):
    test_client, SessionLocal = client
    payload = {
        "entry": [{"changes": [{"value": {
            "messages": [{"id": "wamid.HTTP1", "from": "12025551234", "timestamp": "1721740800", "type": "text", "text": {"body": "hello via http"}}],
        }}]}]
    }
    body = json.dumps(payload).encode()
    resp = test_client.post("/webhooks/whatsapp", content=body, headers={
        "X-Hub-Signature-256": _sign(body), "Content-Type": "application/json",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "received"

    db = SessionLocal()
    try:
        event = db.query(ConversationEvent).filter(ConversationEvent.event_type == "candidate_reply").first()
        assert event is not None
        assert event.event_data["body"] == "hello via http"
    finally:
        db.close()


def test_post_invalid_signature_returns_200_but_discards(client):
    """BR-03: Meta retries on non-200, so a bad signature must never
    make this endpoint return anything other than 200 -- it just
    doesn't process the payload."""
    test_client, SessionLocal = client
    payload = {"entry": [{"changes": [{"value": {"messages": [{"id": "wamid.BAD", "from": "12025551234", "timestamp": "1721740800", "type": "text", "text": {"body": "should not be stored"}}]}}]}]}
    body = json.dumps(payload).encode()
    resp = test_client.post("/webhooks/whatsapp", content=body, headers={
        "X-Hub-Signature-256": "sha256=wrongsignature", "Content-Type": "application/json",
    })
    assert resp.status_code == 200

    db = SessionLocal()
    try:
        assert db.query(ConversationEvent).filter(ConversationEvent.event_type == "candidate_reply").count() == 0
    finally:
        db.close()


def test_post_missing_signature_header_returns_200_but_discards(client):
    test_client, _ = client
    resp = test_client.post("/webhooks/whatsapp", content=b'{"entry":[]}', headers={"Content-Type": "application/json"})
    assert resp.status_code == 200
