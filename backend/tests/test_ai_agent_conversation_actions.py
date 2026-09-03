"""
POST /ai-agent/conversations/{id}/send, /take-over, /hand-back -- proves
S-009 (manual message send) and S-010 (conversation ownership/takeover)
on real routes, wired on top of the already-tested
app.services.whatsapp_routing_service layer (see test_whatsapp_routing.py
import logging
for the underlying service-level proof).

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
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.user import Users
from app.services.ai_conversation_service import AI_AGENT_NAME
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

    from app.api.v1.endpoints.ai_agent import router as ai_agent_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(ai_agent_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    from app.core.security import get_password_hash

    admin = Users(
        UserID="U-ADMIN", UserRole="Super User", UserEmail="admin@blitzenx.com",
        UserPassword=get_password_hash("x"),
    )
    recruiter = Users(
        UserID="U-REC", UserRole="Super User", UserEmail="recruiter@blitzenx.com",
        UserPassword=get_password_hash("x"), whatsapp_number="+15550001111",
    )
    db.add_all([admin, recruiter])
    db.commit()

    candidate = Candidate(
        candidateID="C-100", candidateEmail="cand@example.com", candidatePassword="h",
        candidateMobile="+19995551234",
    )
    db.add(candidate)
    db.commit()

    conversation = CandidateConversation(
        tenant_id=admin.UserID, candidate_id=candidate.candidateID,
        status="open", ai_agent_name=AI_AGENT_NAME, channel_preference="whatsapp",
        owner_type="ai_agent", owner_id=AI_AGENT_NAME,
    )
    db.add(conversation)
    db.commit()

    ids = {"candidate_id": candidate.candidateID, "conversation_id": conversation.id}
    db.close()

    test_client = TestClient(app)
    test_client.wros_ids = ids
    test_client.db_url = f"sqlite:///{db_path}"
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)

def _token_for(email):
    return security.create_access_token(data={"sub": email, "type": "Super User", "name": email})

def _auth(email="admin@blitzenx.com"):
    return {"Authorization": f"Bearer {_token_for(email)}"}

# ---------------------------------------------------------------------------
# S-009 -- manual send
# ---------------------------------------------------------------------------

def test_unauthenticated_send_is_rejected(client):
    resp = client.post(
        f"/ai-agent/conversations/{client.wros_ids['conversation_id']}/send",
        json={"message": "hi"},
    )
    assert resp.status_code in (401, 403)

def test_manual_send_transfers_ownership_to_sender(client):
    ids = client.wros_ids
    resp = client.post(
        f"/ai-agent/conversations/{ids['conversation_id']}/send",
        json={"message": "Hi, this is Priya from BlitzenX."},
        headers=_auth("recruiter@blitzenx.com"),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["owner_type"] == "hr_user"
    assert body["owner_id"] == "U-REC"
    assert body["delivered"] is False  # no whatsapp_client configured in this env

def test_manual_send_records_event(client):
    ids = client.wros_ids
    client.post(
        f"/ai-agent/conversations/{ids['conversation_id']}/send",
        json={"message": "Following up on your documents."},
        headers=_auth("recruiter@blitzenx.com"),
    )

    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    events = session.query(ConversationEvent).filter(
        ConversationEvent.conversation_id == ids["conversation_id"],
        ConversationEvent.event_type == "hr_message_sent",
    ).all()
    session.close()
    engine.dispose()
    assert len(events) == 1
    assert events[0].event_data["body"] == "Following up on your documents."

def test_manual_send_404_for_unknown_conversation(client):
    resp = client.post(
        "/ai-agent/conversations/999999/send",
        json={"message": "hi"},
        headers=_auth(),
    )
    assert resp.status_code == 404

def test_manual_send_rejects_empty_message(client):
    ids = client.wros_ids
    resp = client.post(
        f"/ai-agent/conversations/{ids['conversation_id']}/send",
        json={"message": ""},
        headers=_auth(),
    )
    assert resp.status_code == 422

# ---------------------------------------------------------------------------
# S-010 -- take-over / hand-back
# ---------------------------------------------------------------------------

def test_take_over_sets_human_owner(client):
    ids = client.wros_ids
    resp = client.post(
        f"/ai-agent/conversations/{ids['conversation_id']}/take-over",
        headers=_auth("recruiter@blitzenx.com"),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["owner_type"] == "hr_user"
    assert body["owner_id"] == "U-REC"

def test_take_over_records_ownership_changed_event(client):
    ids = client.wros_ids
    client.post(
        f"/ai-agent/conversations/{ids['conversation_id']}/take-over",
        headers=_auth("recruiter@blitzenx.com"),
    )
    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    events = session.query(ConversationEvent).filter(
        ConversationEvent.conversation_id == ids["conversation_id"],
        ConversationEvent.event_type == "ownership_changed",
    ).all()
    session.close()
    engine.dispose()
    assert len(events) == 1
    assert events[0].event_data["new_owner_type"] == "hr_user"

def test_hand_back_resets_to_ai(client):
    ids = client.wros_ids
    client.post(
        f"/ai-agent/conversations/{ids['conversation_id']}/take-over",
        headers=_auth("recruiter@blitzenx.com"),
    )
    resp = client.post(
        f"/ai-agent/conversations/{ids['conversation_id']}/hand-back",
        headers=_auth("recruiter@blitzenx.com"),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["owner_type"] == "ai_agent"
    assert body["owner_id"] == AI_AGENT_NAME

def test_take_over_404_for_unknown_conversation(client):
    resp = client.post("/ai-agent/conversations/999999/take-over", headers=_auth())
    assert resp.status_code == 404

def test_hand_back_404_for_unknown_conversation(client):
    resp = client.post("/ai-agent/conversations/999999/hand-back", headers=_auth())
    assert resp.status_code == 404
