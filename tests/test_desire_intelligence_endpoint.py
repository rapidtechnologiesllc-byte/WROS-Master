"""
GET/POST /candidates/{id}/desire-intelligence -- S-350/HRMS-P120.

RBAC per Avinash's explicit 2026-08-05 direction: view is candidate.view
(everyone), edit (refresh) is the new candidate.desire_intelligence.edit
permission -- Partner/BU Head/HR Manager/Super User only, NOT Recruiter.

Throwaway SQLite app, throwaway JWT keys, real RBACService seed data
(so the actual role->permission mapping is exercised, not hand-faked)
-- never the real database.
"""
import os
import tempfile
from datetime import datetime

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
from app.models.candidate_desire_profile import CandidateDesireProfile
from app.models.motivation import MotivationOutcome
from app.models.user import Users
from app.services.rbac_service import RBACService
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

    from app.api.v1.endpoints.desire_intelligence import router as desire_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(desire_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    RBACService.seed_roles_and_permissions(db)

    hr_manager_role = db.query(__import__("app.models.rbac", fromlist=["Role"]).Role).filter_by(name="HR Manager").first()
    recruiter_role = db.query(__import__("app.models.rbac", fromlist=["Role"]).Role).filter_by(name="Recruiter").first()

    hr_manager = Users(UserID="U-HRM", UserRole="HR Manager", UserEmail="hrm@blitzenx.com", UserPassword=get_password_hash("x"), role_id=hr_manager_role.id)
    recruiter = Users(UserID="U-REC", UserRole="Recruiter", UserEmail="rec@blitzenx.com", UserPassword=get_password_hash("x"), role_id=recruiter_role.id)
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword=get_password_hash("x"))
    db.add_all([hr_manager, recruiter, candidate])
    db.commit()
    db.close()

    test_client = TestClient(app)
    try:
        yield test_client, TestSessionLocal
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(email):
    return security.create_access_token(data={"sub": email})


def test_get_returns_no_profile_shape_when_none_exists(client):
    test_client, _ = client
    resp = test_client.get("/candidates/C-1/desire-intelligence", headers={"Authorization": f"Bearer {_token_for('rec@blitzenx.com')}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_profile"] is False
    assert body["desire_ranking"] == []


def test_get_visible_to_recruiter(client):
    """Per Avinash's explicit direction: view is available to everyone
    with candidate.view, not restricted to HR/Director."""
    test_client, SessionLocal = client
    db = SessionLocal()
    db.add(CandidateDesireProfile(
        tenant_id="U-HRM", candidate_id="C-1", top_desire_category="CAREER_GROWTH", top_desire_score=0.8,
        desire_ranking=[{"category": "CAREER_GROWTH", "score": 0.8, "signal_count": 2, "direction": "TOWARDS"}],
        engagement_level="HOT", profile_updated_at=datetime.utcnow(),
    ))
    db.commit()
    db.close()

    resp = test_client.get("/candidates/C-1/desire-intelligence", headers={"Authorization": f"Bearer {_token_for('rec@blitzenx.com')}"})
    assert resp.status_code == 200
    assert resp.json()["top_desire_category"] == "CAREER_GROWTH"


def test_get_includes_motivation_history(client):
    test_client, SessionLocal = client
    db = SessionLocal()
    db.add(MotivationOutcome(
        tenant_id="U-HRM", candidate_id="C-1", trigger_type="SCHEDULED_NURTURE",
        message_sent="Hi there, checking in on your growth path interest!", desire_category_targeted="CAREER_GROWTH",
    ))
    db.commit()
    db.close()

    resp = test_client.get("/candidates/C-1/desire-intelligence", headers={"Authorization": f"Bearer {_token_for('rec@blitzenx.com')}"})
    history = resp.json()["motivation_history"]
    assert len(history) == 1
    assert history[0]["trigger_type"] == "SCHEDULED_NURTURE"
    assert history[0]["message_preview"].startswith("Hi there")


def test_refresh_denied_for_recruiter(client):
    test_client, _ = client
    resp = test_client.post("/candidates/C-1/desire-intelligence/refresh", headers={"Authorization": f"Bearer {_token_for('rec@blitzenx.com')}"})
    assert resp.status_code == 403


def test_refresh_allowed_for_hr_manager(client, monkeypatch):
    test_client, _ = client
    monkeypatch.setattr("app.api.v1.endpoints.desire_intelligence.build_and_narrate", lambda *a, **k: None)
    resp = test_client.post("/candidates/C-1/desire-intelligence/refresh", headers={"Authorization": f"Bearer {_token_for('hrm@blitzenx.com')}"})
    assert resp.status_code == 200


def test_get_nonexistent_candidate_returns_404(client):
    test_client, _ = client
    resp = test_client.get("/candidates/NOPE/desire-intelligence", headers={"Authorization": f"Bearer {_token_for('rec@blitzenx.com')}"})
    assert resp.status_code == 404
