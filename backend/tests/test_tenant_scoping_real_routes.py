"""
Proves HRMS-0109's acceptance test on REAL, live routes -- not just the
get_tenant_scoped_query() helper in isolation. Two tenants, each with
their own recruiter and candidates; a recruiter's list-candidates call
must return only their own tenant's data, on the actual
import logging
GET /hr/get_all_candidates endpoint.

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
from app.models.tenant import Tenant
from app.models.user import Users
from app.models.candidate import Candidate
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

    from app.api.v1.endpoints.onboarding import router as onboarding_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(onboarding_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    blitzenx = Tenant(name="BlitzenX")
    other = Tenant(name="Other Client Co")
    db.add_all([blitzenx, other])
    db.commit()

    from app.core.security import get_password_hash
    db.add(Users(
        UserID="U-BX-RECRUITER", UserRole="Super User", UserEmail="recruiter@blitzenx.com",
        UserPassword=get_password_hash("x"), tenant_id=blitzenx.id,
    ))
    db.add(Users(
        UserID="U-OTHER-RECRUITER", UserRole="Super User", UserEmail="recruiter@otherclient.com",
        UserPassword=get_password_hash("x"), tenant_id=other.id,
    ))
    db.add(Candidate(
        candidateID="C-BX-1", candidateEmail="bx1@example.com", candidatePassword="x",
        candidateFirstName="Aisha", tenant_id=blitzenx.id,
    ))
    db.add(Candidate(
        candidateID="C-OTHER-1", candidateEmail="other1@example.com", candidatePassword="x",
        candidateFirstName="Confidential", tenant_id=other.id,
    ))
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


def test_recruiter_sees_only_their_own_tenants_candidates(client):
    token = _token_for("recruiter@blitzenx.com", "Super User")
    resp = client.get("/onboarding/hr/get_all_candidates", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    ids = [c["candidate_id"] for c in resp.json()["candidates"]]
    assert ids == ["C-BX-1"]


def test_negative_case_other_tenants_candidate_never_appears(client):
    token = _token_for("recruiter@blitzenx.com", "Super User")
    resp = client.get("/onboarding/hr/get_all_candidates", headers={"Authorization": f"Bearer {token}"})
    ids = [c["candidate_id"] for c in resp.json()["candidates"]]
    assert "C-OTHER-1" not in ids

    # And the reverse -- the other tenant's recruiter never sees BlitzenX's data.
    other_token = _token_for("recruiter@otherclient.com", "Super User")
    other_resp = client.get("/onboarding/hr/get_all_candidates", headers={"Authorization": f"Bearer {other_token}"})
    other_ids = [c["candidate_id"] for c in other_resp.json()["candidates"]]
    assert other_ids == ["C-OTHER-1"]
    assert "C-BX-1" not in other_ids
