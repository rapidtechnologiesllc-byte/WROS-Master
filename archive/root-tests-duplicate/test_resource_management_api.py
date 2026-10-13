"""
POST /resource-management/scan, GET /resource-management/recommendations,
POST .../pursue|approve|reject -- proves HRMS-1105 (canonical S-320)
Resource Management Agent end-to-end on real routes, not just the
service layer (see the Definition of Done correction in CLAUDE.md --
service-only was never sufficient).

No real Gemini call -- ChatGoogleGenerativeAI is mocked.
Throwaway SQLite app, throwaway JWT keys -- never the real database or
real signing keys.
"""
import os
import tempfile
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.security as security
import app.services.resource_management_agent_service as svc
from app.models.base import Base
from app.models.client import Client
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.resource_agent import BenchAllocationRecommendation
from app.models.resource_management import BenchPoolEntry
from app.models.tenant import Tenant
from app.models.user import Users
import app.models  # noqa: F401 -- registers every model on Base.metadata


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setattr(svc, "GEMINI_API_KEY", "fake-key-for-test")


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

    from app.api.v1.endpoints.resource_management import router as rm_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(rm_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    from app.core.security import get_password_hash

    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()

    db.add(Users(
        UserID="U-RM", UserRole="Admin", UserEmail="rm@blitzenx.com",
        UserPassword=get_password_hash("x"), tenant_id=tenant.id,
    ))
    db.commit()

    acme = Client(tenant_id=tenant.id, company_name="Acme Insurance")
    globex = Client(tenant_id=tenant.id, company_name="Globex Corp")
    db.add_all([acme, globex])
    db.commit()

    employee = Employee(
        tenant_id=tenant.id, first_name="Sam", last_name="Lee",
        email="sam@blitzenx.com", joining_date=date(2025, 1, 1),
        status="BENCH", current_title="Guidewire Developer",
        current_skills='["Guidewire PolicyCenter", "Java"]',
    )
    db.add(employee)
    db.commit()
    db.add(BenchPoolEntry(tenant_id=tenant.id, employee_id=employee.id, available_from=date(2025, 1, 1)))
    db.commit()

    demand_a = Demand(
        tenant_id=tenant.id, client_id=acme.id, job_title="Guidewire Dev - Acme",
        required_skills='["Guidewire PolicyCenter", "Java"]',
        min_experience_years=3.0, work_location="REMOTE",
        status="OPEN", billing_rate_usd_cents=15000,
    )
    demand_b = Demand(
        tenant_id=tenant.id, client_id=globex.id, job_title="Guidewire Dev - Globex",
        required_skills='["Guidewire PolicyCenter", "Java"]',
        min_experience_years=3.0, work_location="REMOTE",
        status="OPEN", billing_rate_usd_cents=16000,
    )
    db.add_all([demand_a, demand_b])
    db.commit()

    rec_a = BenchAllocationRecommendation(
        tenant_id=tenant.id, employee_id=employee.id, demand_id=demand_a.id,
        confidence_pct=82, rationale="Strong skill match.", status="PENDING_RM_REVIEW",
    )
    rec_b = BenchAllocationRecommendation(
        tenant_id=tenant.id, employee_id=employee.id, demand_id=demand_b.id,
        confidence_pct=74, rationale="Good skill match.", status="PENDING_RM_REVIEW",
    )
    db.add_all([rec_a, rec_b])
    db.commit()

    ids = {
        "tenant_id": tenant.id, "employee_id": employee.id,
        "demand_a_id": demand_a.id, "demand_b_id": demand_b.id,
        "rec_a_id": rec_a.id, "rec_b_id": rec_b.id,
    }
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


def _auth(client):
    token = _token_for("rm@blitzenx.com")
    return {"Authorization": f"Bearer {token}"}


def _mock_gemini(response_text):
    mock_response = MagicMock()
    mock_response.content = response_text
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    return patch.object(svc, "ChatGoogleGenerativeAI", return_value=mock_llm)


def test_unauthenticated_scan_is_rejected(client):
    resp = client.post("/resource-management/scan")
    assert resp.status_code in (401, 403)


def test_scan_creates_recommendations(client):
    ids = client.wros_ids
    with _mock_gemini(
        f'[{{"demand_id": "{ids["demand_a_id"]}", "confidence_pct": 91, "rationale": "Great fit"}}]'
    ):
        resp = client.post("/resource-management/scan", headers=_auth(client))
    assert resp.status_code == 200
    body = resp.json()
    assert body["recommendations_created"] >= 1


def test_get_queue_returns_enriched_recommendations(client):
    resp = client.get("/resource-management/recommendations", headers=_auth(client))
    assert resp.status_code == 200
    recs = resp.json()["recommendations"]
    assert len(recs) == 2
    by_id = {r["id"]: r for r in recs}
    ids = client.wros_ids
    rec_a = by_id[ids["rec_a_id"]]
    assert rec_a["employee_name"] == "Sam Lee"
    assert rec_a["demand_job_title"] == "Guidewire Dev - Acme"
    assert rec_a["client_name"] == "Acme Insurance"
    assert rec_a["confidence_pct"] == 82.0


def test_pursue_moves_to_in_progress(client):
    ids = client.wros_ids
    resp = client.post(
        f"/resource-management/recommendations/{ids['rec_a_id']}/pursue", headers=_auth(client),
    )
    assert resp.status_code == 200
    assert resp.json()["recommendation"]["status"] == "IN_PROGRESS"


def test_pursuing_second_client_for_same_employee_is_hard_blocked(client):
    """The exact scenario Avinash described: an employee already in play
    at one client must never be simultaneously pursued for a second."""
    ids = client.wros_ids
    first = client.post(
        f"/resource-management/recommendations/{ids['rec_a_id']}/pursue", headers=_auth(client),
    )
    assert first.status_code == 200

    second = client.post(
        f"/resource-management/recommendations/{ids['rec_b_id']}/pursue", headers=_auth(client),
    )
    assert second.status_code == 409
    assert "already" in second.json()["detail"].lower()


def test_approve_creates_allocation(client):
    ids = client.wros_ids
    client.post(f"/resource-management/recommendations/{ids['rec_a_id']}/pursue", headers=_auth(client))

    resp = client.post(
        f"/resource-management/recommendations/{ids['rec_a_id']}/approve", headers=_auth(client),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["recommendation"]["status"] == "APPROVED"
    assert body["allocation_id"]


def test_approve_without_pursuing_first_is_rejected(client):
    ids = client.wros_ids
    resp = client.post(
        f"/resource-management/recommendations/{ids['rec_a_id']}/approve", headers=_auth(client),
    )
    assert resp.status_code == 409


def test_reject_releases_exclusivity_hold(client):
    ids = client.wros_ids
    client.post(f"/resource-management/recommendations/{ids['rec_a_id']}/pursue", headers=_auth(client))

    reject_resp = client.post(
        f"/resource-management/recommendations/{ids['rec_a_id']}/reject", headers=_auth(client),
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["recommendation"]["status"] == "REJECTED"

    pursue_b = client.post(
        f"/resource-management/recommendations/{ids['rec_b_id']}/pursue", headers=_auth(client),
    )
    assert pursue_b.status_code == 200


def test_actively_engaged_check_reflects_pursue_state(client):
    ids = client.wros_ids
    before = client.get(
        f"/resource-management/employees/{ids['employee_id']}/actively-engaged", headers=_auth(client),
    )
    assert before.json()["actively_engaged"] is False

    client.post(f"/resource-management/recommendations/{ids['rec_a_id']}/pursue", headers=_auth(client))

    after = client.get(
        f"/resource-management/employees/{ids['employee_id']}/actively-engaged", headers=_auth(client),
    )
    assert after.json()["actively_engaged"] is True


def test_matching_bench_resources_finds_skill_matched_employee(client):
    """S-253: fixture employee (Guidewire PolicyCenter + Java skills, on
    the bench) should surface as a top match for demand_a (same required
    skills)."""
    ids = client.wros_ids
    resp = client.get(
        f"/resource-management/demands/{ids['demand_a_id']}/matching-bench-resources", headers=_auth(client),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["demand_job_title"] == "Guidewire Dev - Acme"
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["employee_id"] == ids["employee_id"]
    assert body["candidates"][0]["score_pct"] == 100.0


def test_matching_bench_resources_404_for_unknown_demand(client):
    resp = client.get(
        "/resource-management/demands/does-not-exist/matching-bench-resources", headers=_auth(client),
    )
    assert resp.status_code == 404
