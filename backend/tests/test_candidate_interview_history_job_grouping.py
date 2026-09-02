"""
2026-08-05 -- GET /interviews/candidate-history/{candidate_id} used to
build InterviewDetailedResponse rows without ever surfacing
InterviewPanel.job_id, even though the column already existed --
Avinash: a candidate can interview for N jobs, N rounds each, and the
screen needs to show what happened per job (L1/L2/...), which requires
job info on each interview row. Proves the real route now returns
job_id/job_title per interview, and that they're correct per round --
import logging
not just that the underlying columns exist.

Throwaway SQLite, throwaway JWT keys -- never the real database.
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
from app.models.base import Base
from app.models.candidate import Candidate
from app.models.tenant import Tenant
from app.models.user import Interview, InterviewPanel, Jobs, Users
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

    from app.api.v1.endpoints.interviews import router as interviews_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(interviews_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    from app.core.security import get_password_hash

    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()
    db.add(Users(UserID="U-ADMIN", UserRole="Super User", UserEmail="admin@blitzenx.com",
                 UserPassword=get_password_hash("x"), tenant_id=tenant.id))
    candidate = Candidate(
        candidateID="C-MULTI", candidateEmail="multi@example.com", candidatePassword="h",
        candidateFirstName="Sam", candidateLastName="Lee", tenant_id=tenant.id,
    )
    job_a = Jobs(jobID="J-A", jobTitle="Guidewire Developer", jobDescription="", jobSkills="Guidewire", jobLocation="Remote", jobExperience="5+", tenant_id=tenant.id)
    job_b = Jobs(jobID="J-B", jobTitle="Java Developer", jobDescription="", jobSkills="Java", jobLocation="Remote", jobExperience="3+", tenant_id=tenant.id)
    db.add_all([candidate, job_a, job_b])
    db.commit()

    panel_a_l1 = InterviewPanel(candidate_id="C-MULTI", job_id="J-A", round_name="L1")
    panel_a_l2 = InterviewPanel(candidate_id="C-MULTI", job_id="J-A", round_name="L2")
    panel_b_l1 = InterviewPanel(candidate_id="C-MULTI", job_id="J-B", round_name="L1")
    db.add_all([panel_a_l1, panel_a_l2, panel_b_l1])
    db.commit()

    now = datetime.utcnow()
    db.add_all([
        Interview(panel_id=panel_a_l1.id, candidate_id="C-MULTI", status="Completed", start_time=now, end_time=now),
        Interview(panel_id=panel_a_l2.id, candidate_id="C-MULTI", status="Scheduled", start_time=now, end_time=now),
        Interview(panel_id=panel_b_l1.id, candidate_id="C-MULTI", status="Completed", start_time=now, end_time=now),
    ])
    db.commit()
    db.close()

    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _auth():
    token = security.create_access_token(data={"sub": "admin@blitzenx.com", "type": "Super User", "name": "admin@blitzenx.com"})
    return {"Authorization": f"Bearer {token}"}


def test_candidate_history_returns_job_id_and_title_per_round(client):
    resp = client.get("/interviews/candidate-history/C-MULTI", headers=_auth())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_interviews"] == 3

    by_job = {}
    for iv in body["interviews"]:
        assert iv["job_id"] is not None
        assert iv["job_title"] is not None
        by_job.setdefault(iv["job_id"], []).append(iv["panel_round_name"])

    assert set(by_job.keys()) == {"J-A", "J-B"}
    assert sorted(by_job["J-A"]) == ["L1", "L2"]
    assert by_job["J-B"] == ["L1"]
    job_titles = {iv["job_id"]: iv["job_title"] for iv in body["interviews"]}
    assert job_titles["J-A"] == "Guidewire Developer"
    assert job_titles["J-B"] == "Java Developer"
