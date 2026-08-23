"""
POST /thunder/test-chat, GET /thunder/test-chat/history, POST
/thunder/test-chat/reset -- proves the "Test Thunder" flow end-to-end
on real routes.

UPDATED 2026-07-23: access is now gated behind the "thunder.test" RBAC
permission (Super User only by default -- see rbac_service.py's
PERMISSIONS_SEED/ROLE_PERMISSIONS_SEED and require_permission()'s
Super User bypass), not "any logged-in internal user, any role" as
before. Tightened after the frontend nav entry that surfaced this QA
tool to every role (including the CEO's own Super User account) caused
real account-identity confusion -- see the nav removal in Shell.js.
Real governance underneath (R-08, consent, debounce) is unchanged.

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
    # "Super User" is the only role thunder.test's require_permission()
    # bypass grants by default -- matches Avinash's real account's
    # UserRole value exactly (case-insensitive check).
    db.add(Users(
        UserID="U-CEO", UserRole="Super User", UserEmail="ceo@blitzenx.com",
        UserPassword=get_password_hash("x"),
    ))
    db.add(Users(
        UserID="U-CEO2", UserRole="Super User", UserEmail="ceo2@blitzenx.com",
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


def test_non_super_user_role_is_rejected(client):
    """thunder.test is Super-User-only by default -- a Recruiter (or any
    other non-Super-User role) must get 403, not a real Thunder reply."""
    token = _token_for("recruiter@blitzenx.com", role="Recruiter")
    resp = client.post(
        "/thunder/test-chat",
        json={"message": "Hello"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


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
    """Two different Super User accounts testing Thunder each get their
    own isolated conversation, keyed off UserID -- not a shared identity."""
    ceo_token = _token_for("ceo@blitzenx.com")
    ceo2_token = _token_for("ceo2@blitzenx.com")

    with _mock_gemini("Reply to CEO"):
        client.post(
            "/thunder/test-chat", json={"message": "CEO's message"},
            headers={"Authorization": f"Bearer {ceo_token}"},
        )

    ceo2_history = client.get(
        "/thunder/test-chat/history", headers={"Authorization": f"Bearer {ceo2_token}"}
    ).json()["messages"]
    assert ceo2_history == []
