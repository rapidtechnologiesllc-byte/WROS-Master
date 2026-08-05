"""
GET/PATCH /portal/* -- HTTP wiring for S-017/HRMS-0417: real candidate
JWT auth (the "magic link" itself, per candidate_portal_service's
module docstring), BR-02 cross-candidate isolation, happy paths.

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
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.user import Interview, Users
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

    from app.api.v1.endpoints.candidate_portal import router as portal_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(portal_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate_a = Candidate(candidateID="C-A", candidateEmail="a@example.com", candidatePassword=get_password_hash("x"), candidateFirstName="Ann")
    candidate_b = Candidate(candidateID="C-B", candidateEmail="b@example.com", candidatePassword=get_password_hash("x"), candidateFirstName="Ben")
    db.add_all([owner, candidate_a, candidate_b])
    db.commit()
    conv_a = CandidateConversation(tenant_id=owner.UserID, candidate_id="C-A", status="open", owner_type="ai_agent", owner_id="thunder")
    db.add(conv_a)
    db.commit()
    db.add(ConversationEvent(conversation_id=conv_a.id, event_type="ai_message_sent", event_data={"channel": "email", "body": "Welcome!"}, triggered_by="ai_agent"))
    interview = Interview(candidate_id="C-A", start_time=datetime.utcnow() + timedelta(days=1), end_time=datetime.utcnow() + timedelta(days=1, hours=1), status="Scheduled")
    db.add(interview)
    db.commit()
    interview_id = interview.id
    db.close()

    test_client = TestClient(app)
    try:
        yield test_client, interview_id
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(candidate_id):
    return security.create_access_token(data={"sub": candidate_id, "type": "candidate"})


def test_home_returns_stage_and_pending_actions(client):
    test_client, _ = client
    resp = test_client.get("/portal/home", headers={"Authorization": f"Bearer {_token_for('C-A')}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidate_name"] == "Ann"
    assert body["stage"]["label"]
    assert isinstance(body["pending_actions"], list)


def test_home_requires_auth(client):
    test_client, _ = client
    resp = test_client.get("/portal/home")
    assert resp.status_code in (401, 403)


def test_messages_returns_cross_channel_thread(client):
    test_client, _ = client
    resp = test_client.get("/portal/messages", headers={"Authorization": f"Bearer {_token_for('C-A')}"})
    assert resp.status_code == 200
    assert resp.json()["messages"][0]["channel"] == "EMAIL"


def test_profile_patch_updates_missing_field(client):
    test_client, _ = client
    token = _token_for("C-A")
    before = test_client.get("/portal/profile-fields", headers={"Authorization": f"Bearer {token}"}).json()
    assert before["total_missing"] > 0

    resp = test_client.patch(
        "/portal/profile",
        json={"fields": {"candidateMobile": "+919876543210"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "candidateMobile" in body["updated"]
    assert body["total_missing"] == before["total_missing"] - 1


def test_interviews_lists_upcoming(client):
    test_client, interview_id = client
    resp = test_client.get("/portal/interviews", headers={"Authorization": f"Bearer {_token_for('C-A')}"})
    assert resp.status_code == 200
    interviews = resp.json()["interviews"]
    assert len(interviews) == 1
    assert interviews[0]["id"] == interview_id


def test_interview_ics_download(client):
    test_client, interview_id = client
    resp = test_client.get(f"/portal/interviews/{interview_id}/ics", headers={"Authorization": f"Bearer {_token_for('C-A')}"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/calendar")
    assert b"BEGIN:VEVENT" in resp.content


def test_interview_ics_cross_candidate_returns_404(client):
    test_client, interview_id = client
    resp = test_client.get(f"/portal/interviews/{interview_id}/ics", headers={"Authorization": f"Bearer {_token_for('C-B')}"})
    assert resp.status_code == 404


def test_reschedule_request_happy_path(client):
    test_client, interview_id = client
    resp = test_client.post(
        f"/portal/interviews/{interview_id}/reschedule-request",
        json={"note": "Can we move to Friday?"},
        headers={"Authorization": f"Bearer {_token_for('C-A')}"},
    )
    assert resp.status_code == 200
    assert resp.json()["request_id"]


def test_track_page_view_recorded_when_conversation_exists(client):
    """S-346 Step 4 / S-347 Step 4."""
    test_client, _ = client
    resp = test_client.post(
        "/portal/track",
        json={"page": "profile", "time_on_page_seconds": 45, "scroll_depth_pct": 80},
        headers={"Authorization": f"Bearer {_token_for('C-A')}"},
    )
    assert resp.status_code == 200
    assert resp.json()["recorded"] is True


def test_track_page_view_no_conversation_still_returns_200(client):
    """C-B has no conversation in this fixture -- a behavioral-telemetry
    beacon must never fail loudly over a missing precondition."""
    test_client, _ = client
    resp = test_client.post(
        "/portal/track",
        json={"page": "home", "time_on_page_seconds": 10},
        headers={"Authorization": f"Bearer {_token_for('C-B')}"},
    )
    assert resp.status_code == 200
    assert resp.json()["recorded"] is False


def test_track_page_view_requires_auth(client):
    test_client, _ = client
    resp = test_client.post("/portal/track", json={"page": "home", "time_on_page_seconds": 10})
    assert resp.status_code in (401, 403)
