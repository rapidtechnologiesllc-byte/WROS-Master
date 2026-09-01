"""
GET /candidates/{id}/ai-assignment -- proves the HTTP-level auth
gating; everything else covered at the service layer in
test_ai_recruiter_assignment.py.

2026-08-06: this file used to also cover GET/PATCH /admin/tenant/ai-
config, a confirmed-dead duplicate of the real /admin/ai-config
endpoint (deleted from ai_recruiter_assignment.py). Those 4 tests moved
to tests/test_tenant_ai_config_api.py instead of being deleted outright
-- /admin/ai-config is the real, frontend-wired endpoint and had zero
test coverage of its own before this.

Throwaway SQLite app, throwaway JWT keys, real RBAC seed -- never the
real database.
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
from app.models.candidate_ai import CandidateAIAssignment
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

    from app.api.v1.endpoints.ai_recruiter_assignment import router as assignment_router
    from app.core.database import get_db
    from app.services.rbac_service_template import RBACService

    app = FastAPI()
    app.include_router(assignment_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    RBACService.seed_roles_and_permissions(db)

    super_user_role = db.query(RoleTemplate).filter_by(name="Super User").first()
    recruiter_role = db.query(RoleTemplate).filter_by(name="Recruiter").first()

    super_user = Users(UserID="U-CEO", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword=get_password_hash("x"), role_id=super_user_role.id if super_user_role else None)
    recruiter = Users(UserID="U-REC", UserRole="Recruiter", UserEmail="recruiter@blitzenx.com", UserPassword=get_password_hash("x"), role_id=recruiter_role.id if recruiter_role else None)
    candidate = Candidate(candidateID="C-100", candidateEmail="cand@example.com", candidatePassword="h")
    db.add_all([super_user, recruiter, candidate])
    db.commit()
    db.add(CandidateAIAssignment(tenant_id="U-CEO", candidate_id="C-100", ai_agent_name="Thunder", ai_agent_persona="I am Thunder.", is_active=True))
    db.commit()
    db.close()

    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(email, role):
    return security.create_access_token(data={"sub": email, "type": role, "name": email})


def test_get_candidate_assignment_returns_active_record(client):
    resp = client.get(
        "/candidates/C-100/ai-assignment",
        headers={"Authorization": f"Bearer {_token_for('recruiter@blitzenx.com', 'Recruiter')}"},
    )
    assert resp.status_code == 200
    assert resp.json()["ai_agent_name"] == "Thunder"


def test_get_candidate_assignment_404_for_unknown_candidate(client):
    resp = client.get(
        "/candidates/C-DOES-NOT-EXIST/ai-assignment",
        headers={"Authorization": f"Bearer {_token_for('recruiter@blitzenx.com', 'Recruiter')}"},
    )
    assert resp.status_code == 404


