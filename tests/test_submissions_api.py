"""
POST /submissions, GET /submissions, GET /submissions/violations, PATCH
/submissions/{id}/client-response -- proves HRMS-0711 Client Submission
Pipeline end-to-end on real routes for the first time. Also proves
canonical S-249 ("Restrict Market Candidate Submission"):
check_market_profile_rule() (pre-existing, real) blocks a non-BENCH/
ACTIVE/ALLOCATED employee's candidate from being submitted.

Throwaway SQLite app, throwaway JWT keys -- never the real database or
real signing keys.
"""
import os
import tempfile
from datetime import date

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
from app.models.client import Client
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.tenant import Tenant
from app.models.user import Users
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

    from app.api.v1.endpoints.submissions import router as submissions_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(submissions_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    from app.core.security import get_password_hash

    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()

    db.add(Users(
        UserID="U-ADMIN", UserRole="Admin", UserEmail="admin@blitzenx.com",
        UserPassword=get_password_hash("x"), tenant_id=tenant.id,
    ))
    db.commit()

    acme = Client(tenant_id=tenant.id, company_name="Acme Insurance")
    db.add(acme)
    db.commit()

    demand = Demand(
        tenant_id=tenant.id, client_id=acme.id, job_title="Sr. Guidewire Developer",
        required_skills="[]", min_experience_years=3.0, work_location="REMOTE",
        status="OPEN", billing_rate_usd_cents=15000,
    )
    db.add(demand)
    db.commit()

    # Eligible candidate: converted to a BENCH employee, enough experience, W2.
    eligible_candidate = Candidate(
        candidateID="CAND-1", candidateFirstName="Sam", candidateLastName="Lee",
        candidateEmail="sam.candidate@blitzenx.com", candidatePassword="x",
        total_experience_months=72, employment_type="W2_FULLTIME", tenant_id=tenant.id,
    )
    db.add(eligible_candidate)
    db.commit()
    eligible_employee = Employee(
        tenant_id=tenant.id, candidate_id="CAND-1", first_name="Sam", last_name="Lee",
        email="sam@blitzenx.com", joining_date=date(2025, 1, 1), status="BENCH",
    )
    db.add(eligible_employee)
    db.commit()

    # Ineligible candidate: never converted to an employee at all.
    ineligible_candidate = Candidate(
        candidateID="CAND-2", candidateFirstName="Alex", candidateLastName="Kim",
        candidateEmail="alex.candidate@blitzenx.com", candidatePassword="x",
        total_experience_months=72, employment_type="W2_FULLTIME", tenant_id=tenant.id,
    )
    db.add(ineligible_candidate)
    db.commit()

    ids = {"tenant_id": tenant.id, "demand_id": demand.id}
    db.close()

    test_client = TestClient(app)
    test_client.wros_ids = ids
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(email, role="Admin"):
    return security.create_access_token(data={"sub": email, "type": role, "name": email})


def _auth():
    return {"Authorization": f"Bearer {_token_for('admin@blitzenx.com')}"}


def test_unauthenticated_request_is_rejected(client):
    resp = client.get("/submissions")
    assert resp.status_code in (401, 403)


def test_submit_eligible_candidate_succeeds(client):
    ids = client.wros_ids
    resp = client.post(
        "/submissions", json={"demand_id": ids["demand_id"], "candidate_id": "CAND-1"}, headers=_auth(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "SUBMITTED"
    assert body["candidate_name"] == "Sam Lee"
    assert body["demand_job_title"] == "Sr. Guidewire Developer"


def test_submit_candidate_never_converted_to_employee_is_blocked(client):
    """S-249: no employees record at all -- market profile guard blocks it."""
    ids = client.wros_ids
    resp = client.post(
        "/submissions", json={"demand_id": ids["demand_id"], "candidate_id": "CAND-2"}, headers=_auth(),
    )
    assert resp.status_code == 422
    blockers = resp.json()["detail"]
    errors = [b["error"] for b in blockers]
    assert "MARKET_PROFILE_SUBMISSION_BLOCKED" in errors


def test_duplicate_submission_is_rejected(client):
    ids = client.wros_ids
    client.post("/submissions", json={"demand_id": ids["demand_id"], "candidate_id": "CAND-1"}, headers=_auth())
    resp = client.post(
        "/submissions", json={"demand_id": ids["demand_id"], "candidate_id": "CAND-1"}, headers=_auth(),
    )
    assert resp.status_code == 409


def test_list_submissions_filtered_by_demand(client):
    ids = client.wros_ids
    client.post("/submissions", json={"demand_id": ids["demand_id"], "candidate_id": "CAND-1"}, headers=_auth())

    resp = client.get(f"/submissions?demand_id={ids['demand_id']}", headers=_auth())
    assert resp.status_code == 200
    assert len(resp.json()["submissions"]) == 1


def test_violation_log_records_blocked_attempt(client):
    ids = client.wros_ids
    client.post("/submissions", json={"demand_id": ids["demand_id"], "candidate_id": "CAND-2"}, headers=_auth())

    resp = client.get("/submissions/violations", headers=_auth())
    assert resp.status_code == 200
    violations = resp.json()["violations"]
    assert len(violations) == 1
    assert violations[0]["violation_type"] == "NO_MARKET_PROFILE"


def test_client_response_transitions_status(client):
    ids = client.wros_ids
    submit_resp = client.post(
        "/submissions", json={"demand_id": ids["demand_id"], "candidate_id": "CAND-1"}, headers=_auth(),
    )
    submission_id = submit_resp.json()["id"]

    resp = client.patch(
        f"/submissions/{submission_id}/client-response",
        json={"new_status": "SHORTLISTED"}, headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "SHORTLISTED"


def test_client_response_rejects_invalid_transition(client):
    ids = client.wros_ids
    submit_resp = client.post(
        "/submissions", json={"demand_id": ids["demand_id"], "candidate_id": "CAND-1"}, headers=_auth(),
    )
    submission_id = submit_resp.json()["id"]
    client.patch(
        f"/submissions/{submission_id}/client-response",
        json={"new_status": "PLACED"}, headers=_auth(),
    )  # not reachable directly from SUBMITTED

    resp = client.patch(
        f"/submissions/{submission_id}/client-response",
        json={"new_status": "PLACED"}, headers=_auth(),
    )
    assert resp.status_code == 409


def test_submit_to_nonexistent_demand_is_404(client):
    resp = client.post(
        "/submissions", json={"demand_id": "does-not-exist", "candidate_id": "CAND-1"}, headers=_auth(),
    )
    assert resp.status_code == 404
