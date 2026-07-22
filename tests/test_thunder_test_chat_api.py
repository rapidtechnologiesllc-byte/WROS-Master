"""
POST /thunder/test-chat, GET /thunder/test-chat/history, POST
/thunder/test-chat/reset -- proves the "Test Thunder" flow end-to-end
on real routes: any logged-in internal user (any role) can chat with
Thunder without a live WhatsApp Business API, and the real governance
(R-08, consent, debounce) stays in front of the mocked transport.

No real Gemini call -- ChatGoogleGenerativeAI is mocked.
Throwaway SQLite app, throwaway JWT keys -- never the real database or
real signing keys.
"""
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.security as security
import app.services.thunder_service as thunder_svc
import app.services.whatsapp_routing_service as routing
from app.models.base import Base
from app.models.user import Users
import app.models  # noqa: F401 -- registers every model on Base.metadata


@pytest.fixture(autouse=True)
def _default_whatsapp_number(monkeypatch):
    monkeypatch.setattr(routing, "DEFAULT_WHATSAPP_NUMBER", "+10005550000")


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


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setattr(thunder_svc, "GEMINI_API_KEY", "fake-key-for-test")


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

    from app.api.v1.endpoints.thunder import router as thunder_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(thunder_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    from app.core.security import get_password_hash
    db.add(Users(
        UserID="U-CEO", UserRole="Admin", UserEmail="ceo@blitzenx.com",
        UserPassword=get_password_hash("x"),
    ))
    db.add(Users(
        UserID="U-REC", UserRole="Recruiter", UserEmail="recruiter@blitzenx.com",
        UserPassword=get_password_hash("x"),
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


def _mock_gemini(reply_text):
    mock_response = MagicMock()
    mock_response.content = reply_text
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    return patch.object(thunder_svc, "ChatGoogleGenerativeAI", return_value=mock_llm)


def test_send_test_chat_message_returns_thunder_reply(client):
    token = _token_for("ceo@blitzenx.com")
    with _mock_gemini("Thanks for the update!"):
        resp = client.post(
            "/thunder/test-chat",
            json={"message": "Hi Thunder, checking in"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["thunder_reply"] == "Thanks for the update!"
    assert body["candidate_message"] == "Hi Thunder, checking in"
    assert body["mock_send"] is True
    assert body["delivered"] is True


def test_unauthenticated_request_is_rejected(client):
    resp = client.post("/thunder/test-chat", json={"message": "Hi"})
    assert resp.status_code in (401, 403)


def test_any_internal_role_can_use_test_chat(client):
    """Available to all internal users regardless of role -- not gated
    behind a specific granular permission."""
    token = _token_for("recruiter@blitzenx.com", role="Recruiter")
    with _mock_gemini("Sure, happy to help!"):
        resp = client.post(
            "/thunder/test-chat",
            json={"message": "Hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200


def test_history_reflects_prior_turn(client):
    token = _token_for("ceo@blitzenx.com")
    with _mock_gemini("Reply text"):
        client.post(
            "/thunder/test-chat", json={"message": "Message text"},
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = client.get("/thunder/test-chat/history", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    messages = resp.json()["messages"]
    assert [(m["sender"], m["body"]) for m in messages] == [
        ("candidate", "Message text"),
        ("thunder", "Reply text"),
    ]


def test_reset_clears_history_for_next_message(client):
    token = _token_for("ceo@blitzenx.com")
    with _mock_gemini("Reply text"):
        client.post(
            "/thunder/test-chat", json={"message": "Message text"},
            headers={"Authorization": f"Bearer {token}"},
        )

    reset_resp = client.post("/thunder/test-chat/reset", headers={"Authorization": f"Bearer {token}"})
    assert reset_resp.status_code == 200

    history_resp = client.get("/thunder/test-chat/history", headers={"Authorization": f"Bearer {token}"})
    assert history_resp.json()["messages"] == []


def test_testers_do_not_share_a_conversation(client):
    ceo_token = _token_for("ceo@blitzenx.com")
    rec_token = _token_for("recruiter@blitzenx.com", role="Recruiter")

    with _mock_gemini("Reply to CEO"):
        client.post(
            "/thunder/test-chat", json={"message": "CEO's message"},
            headers={"Authorization": f"Bearer {ceo_token}"},
        )

    rec_history = client.get(
        "/thunder/test-chat/history", headers={"Authorization": f"Bearer {rec_token}"}
    ).json()["messages"]
    assert rec_history == []
