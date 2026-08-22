"""
S-076/HRMS-0476 -- Conversation Audit Log.

Unit tests for app.services.audit_log_service.log_audit_event(), plus
API-level tests proving GET /ai-agent/candidates/{id}/audit-log surfaces
real entries written by the S-009 (manual send) and S-010 (take-over/
hand-back) endpoints -- the two EPIC-04-scoped audit points wired this
round (see conversation_audit_log.py's module docstring for what's
deliberately NOT wired: offers, overrides, state transitions -- other
epics' own code).

"""
import os

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
from app.models.candidate_ai import CandidateConversation
from app.models.conversation_audit_log import ConversationAuditLog
from app.models.user import Users
from app.services.ai_conversation_service import AI_AGENT_NAME
from app.services.audit_log_service import log_audit_event
import app.models  # noqa: F401 -- registers every model on Base.metadata

# ---------------------------------------------------------------------------
# Service-level unit tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

@pytest.fixture()
def fixtures(db_session):
    org_owner = Users(UserID="U-ORG", UserRole="Admin", UserEmail="admin@blitzenx.com", UserPassword="h")
    db_session.add(org_owner)
    db_session.commit()

    candidate = Candidate(
        candidateID="C-300", candidateEmail="cand300@example.com", candidatePassword="h",
        candidateMobile="+19995551234",
    )
    db_session.add(candidate)
    db_session.commit()

    conversation = CandidateConversation(
        tenant_id=org_owner.UserID, candidate_id=candidate.candidateID,
        status="open", ai_agent_name=AI_AGENT_NAME, owner_type="ai_agent", owner_id=AI_AGENT_NAME,
    )
    db_session.add(conversation)
    db_session.commit()

    return org_owner, candidate, conversation

def test_log_audit_event_inserts_record(db_session, fixtures):
    org_owner, candidate, conversation = fixtures
    entry = log_audit_event(
        db_session, tenant_id=org_owner.UserID, candidate_id=candidate.candidateID,
        conversation_id=conversation.id, audit_event_type="OWNERSHIP_CHANGED",
        description="HR took over.", actor_type="HR", actor_id="U-REC",
        before_state={"owner_type": "ai_agent"}, after_state={"owner_type": "hr_user"},
    )
    db_session.commit()

    assert entry.id is not None
    stored = db_session.query(ConversationAuditLog).filter(ConversationAuditLog.id == entry.id).first()
    assert stored.audit_event_type == "OWNERSHIP_CHANGED"
    assert stored.before_state == {"owner_type": "ai_agent"}
    assert stored.after_state == {"owner_type": "hr_user"}

def test_log_audit_event_conversation_id_optional(db_session, fixtures):
    org_owner, candidate, conversation = fixtures
    entry = log_audit_event(
        db_session, tenant_id=org_owner.UserID, candidate_id=candidate.candidateID,
        audit_event_type="SOME_EVENT", description="No conversation tie.",
        actor_type="SYSTEM", actor_id="system",
    )
    db_session.commit()
    assert entry.conversation_id is None

# ---------------------------------------------------------------------------
# API-level: audit entries surface via GET /ai-agent/candidates/{id}/audit-log
# ---------------------------------------------------------------------------

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
    engine = create_engine(f"sqlite:///{db_path}")

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

    recruiter = Users(
        UserID="U-REC", UserRole="Super User", UserEmail="recruiter@blitzenx.com",
        UserPassword=get_password_hash("x"),
    )
    db.add(recruiter)
    db.commit()

    candidate = Candidate(
        candidateID="C-301", candidateEmail="cand301@example.com", candidatePassword="h",
        candidateMobile="+19995551234",
    )
    db.add(candidate)
    db.commit()

    conversation = CandidateConversation(
        tenant_id="U-REC", candidate_id=candidate.candidateID,
        status="open", ai_agent_name=AI_AGENT_NAME, owner_type="ai_agent", owner_id=AI_AGENT_NAME,
    )
    db.add(conversation)
    db.commit()

    ids = {"candidate_id": candidate.candidateID, "conversation_id": conversation.id}
    db.close()

    test_client = TestClient(app)
    test_client.wros_ids = ids
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)

def _auth():
    token = security.create_access_token(
        data={"sub": "recruiter@blitzenx.com", "type": "Super User", "name": "recruiter@blitzenx.com"}
    )
    return {"Authorization": f"Bearer {token}"}

def test_audit_log_empty_for_new_candidate(client):
    ids = client.wros_ids
    resp = client.get(f"/ai-agent/candidates/{ids['candidate_id']}/audit-log", headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["audit_entries"] == []

def test_take_over_writes_audit_entry_visible_via_api(client):
    ids = client.wros_ids
    client.post(f"/ai-agent/conversations/{ids['conversation_id']}/take-over", headers=_auth())

    resp = client.get(f"/ai-agent/candidates/{ids['candidate_id']}/audit-log", headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 1
    assert body["audit_entries"][0]["audit_event_type"] == "OWNERSHIP_CHANGED"
    assert body["audit_entries"][0]["actor_type"] == "HR"
    assert body["audit_entries"][0]["before_state"]["owner_type"] == "ai_agent"
    assert body["audit_entries"][0]["after_state"]["owner_type"] == "hr_user"

def test_manual_send_writes_audit_entry(client):
    ids = client.wros_ids
    client.post(
        f"/ai-agent/conversations/{ids['conversation_id']}/send",
        json={"message": "Hello from HR"},
        headers=_auth(),
    )
    resp = client.get(f"/ai-agent/candidates/{ids['candidate_id']}/audit-log", headers=_auth())
    entries = resp.json()["audit_entries"]
    assert len(entries) == 1
    assert entries[0]["audit_event_type"] == "MANUAL_MESSAGE_SENT"

def test_take_over_then_hand_back_writes_two_chronological_entries(client):
    ids = client.wros_ids
    client.post(f"/ai-agent/conversations/{ids['conversation_id']}/take-over", headers=_auth())
    client.post(f"/ai-agent/conversations/{ids['conversation_id']}/hand-back", headers=_auth())

    resp = client.get(f"/ai-agent/candidates/{ids['candidate_id']}/audit-log", headers=_auth())
    entries = resp.json()["audit_entries"]
    assert len(entries) == 2
    assert entries[0]["after_state"]["owner_type"] == "hr_user"
    assert entries[1]["after_state"]["owner_type"] == "ai_agent"

def test_audit_log_404_for_unknown_candidate(client):
    resp = client.get("/ai-agent/candidates/DOES-NOT-EXIST/audit-log", headers=_auth())
    assert resp.status_code == 404
