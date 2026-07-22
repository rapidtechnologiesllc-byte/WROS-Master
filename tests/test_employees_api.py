"""
POST /employees, GET /employees, GET /employees/bench-pool, GET
/employees/bench-aging-alerts, GET /employees/{id}, POST
/employees/{id}/mark-bench|remove-from-bench, GET
/employees/{id}/bench-history -- proves S-245 (Create Employee Profile)
+ S-246 (Mark Employee as Bench, extended with bench_periods history) +
S-247 (View Bench Pool) + S-248 (Bench Duration & Aging Report)
end-to-end on real routes.

Throwaway SQLite app, throwaway JWT keys -- never the real database or
real signing keys.
"""
import os
import tempfile
from datetime import date, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.security as security
from app.models.base import Base
from app.models.resource_management import BenchPoolEntry
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

    from app.api.v1.endpoints.employees import router as employees_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(employees_router)
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

    ids = {"tenant_id": tenant.id}
    db.close()

    test_client = TestClient(app)
    test_client.wros_ids = ids
    test_client.db_url = f"sqlite:///{db_path}"
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(email, role="Admin"):
    return security.create_access_token(data={"sub": email, "type": role, "name": email})


def _auth():
    return {"Authorization": f"Bearer {_token_for('admin@blitzenx.com')}"}


def _create_employee(client, **overrides):
    body = {
        "first_name": "Sam", "last_name": "Lee", "email": "sam@blitzenx.com",
        "joining_date": "2025-01-01", "current_title": "Guidewire Developer",
        "current_skills": ["Guidewire PolicyCenter", "Java"],
        "base_salary_usd_cents": 900000,
    }
    body.update(overrides)
    resp = client.post("/employees", json=body, headers=_auth())
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_unauthenticated_request_is_rejected(client):
    resp = client.get("/employees")
    assert resp.status_code in (401, 403)


def test_create_employee_profile(client):
    body = _create_employee(client)
    assert body["first_name"] == "Sam"
    assert body["status"] == "PRE_JOINING"
    assert body["delivery_engine"] == "SPECIALITY"
    assert body["current_skills"] == ["Guidewire PolicyCenter", "Java"]
    assert body["employee_number"]  # auto-generated, non-empty
    assert body["is_on_bench"] is False


def test_create_employee_rejects_duplicate_email(client):
    _create_employee(client)
    resp = client.post(
        "/employees",
        json={
            "first_name": "Other", "last_name": "Person", "email": "sam@blitzenx.com",
            "joining_date": "2025-02-01",
        },
        headers=_auth(),
    )
    assert resp.status_code == 409


def test_list_employees(client):
    _create_employee(client)
    _create_employee(client, email="jane@blitzenx.com", first_name="Jane")

    resp = client.get("/employees", headers=_auth())
    assert resp.status_code == 200
    assert len(resp.json()["employees"]) == 2


def test_mark_bench_then_visible_in_bench_pool(client):
    employee = _create_employee(client)
    mark_resp = client.post(
        f"/employees/{employee['id']}/mark-bench",
        json={"reason": "NEWLY_JOINED"}, headers=_auth(),
    )
    assert mark_resp.status_code == 200
    assert mark_resp.json()["is_on_bench"] is True
    assert mark_resp.json()["bench_days"] == 0

    pool_resp = client.get("/employees/bench-pool", headers=_auth())
    assert pool_resp.status_code == 200
    pool = pool_resp.json()["employees"]
    assert len(pool) == 1
    assert pool[0]["id"] == employee["id"]


def test_mark_bench_rejects_invalid_reason(client):
    employee = _create_employee(client)
    resp = client.post(
        f"/employees/{employee['id']}/mark-bench",
        json={"reason": "MADE_UP_REASON"}, headers=_auth(),
    )
    assert resp.status_code == 422


def test_remove_from_bench_closes_history_and_leaves_pool(client):
    employee = _create_employee(client)
    client.post(f"/employees/{employee['id']}/mark-bench", json={"reason": "NEWLY_JOINED"}, headers=_auth())

    remove_resp = client.post(f"/employees/{employee['id']}/remove-from-bench", headers=_auth())
    assert remove_resp.status_code == 200
    assert remove_resp.json()["is_on_bench"] is False

    pool_resp = client.get("/employees/bench-pool", headers=_auth())
    assert pool_resp.json()["employees"] == []

    history_resp = client.get(f"/employees/{employee['id']}/bench-history", headers=_auth())
    assert history_resp.status_code == 200
    periods = history_resp.json()["periods"]
    assert len(periods) == 1
    assert periods[0]["bench_end_date"] is not None
    assert periods[0]["reason_for_bench"] == "NEWLY_JOINED"


def test_bench_aging_alerts_reflect_current_bench_pool(client):
    employee = _create_employee(client)
    client.post(f"/employees/{employee['id']}/mark-bench", json={"reason": "NEWLY_JOINED"}, headers=_auth())

    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    entry = session.query(BenchPoolEntry).filter(BenchPoolEntry.employee_id == employee["id"]).first()
    entry.available_from = date.today() - timedelta(days=60)
    session.commit()
    session.close()
    engine.dispose()

    resp = client.get("/employees/bench-aging-alerts", headers=_auth())
    assert resp.status_code == 200
    alerts = resp.json()["alerts"]
    assert len(alerts) == 1
    assert alerts[0]["days_on_bench"] == 60
    assert alerts[0]["employee_name"] == "Sam Lee"


def test_get_employee_404_for_unknown_id(client):
    resp = client.get("/employees/does-not-exist", headers=_auth())
    assert resp.status_code == 404


def test_staffing_eligibility_true_for_speciality_by_default(client):
    employee = _create_employee(client)
    resp = client.get(
        f"/employees/{employee['id']}/staffing-eligibility?delivery_engine=SPECIALITY", headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json()["eligible"] is True


def test_staffing_eligibility_false_for_core_without_certification(client):
    employee = _create_employee(client)
    resp = client.get(
        f"/employees/{employee['id']}/staffing-eligibility?delivery_engine=CORE", headers=_auth(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["eligible"] is False
    assert "Core-certified" in body["reason"]
