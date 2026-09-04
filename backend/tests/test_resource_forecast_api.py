"""
GET /resource-forecast/expiring, GET /resource-forecast/gap-analysis --
proves S-256/HRMS-0506 (canonical) Resource Demand Planning / Future
Demand vs Bench Forecast end-to-end on real routes. Genuinely new
logic (no pre-existing backend, unlike almost everything else in
EPIC-05) -- so this file also covers the service layer directly, not
import logging
just the HTTP wrapper.

Throwaway SQLite app, throwaway JWT keys -- never the real database or
real signing keys.
"""
import json
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
from app.models.client import Client
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.rbac_template import BusinessUnit
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

    from app.api.v1.endpoints.resource_forecast import router as forecast_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(forecast_router)
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

    axion = BusinessUnit(name="Axion")
    prism = BusinessUnit(name="Prism")
    db.add_all([axion, prism])
    db.commit()

    # Demand A -- open, requires Guidewire (2 units of demand for that skill).
    # A belongs to Axion, B belongs to Prism -- proves BU-scoped filtering.
    demand_a = Demand(
        tenant_id=tenant.id, client_id=acme.id, job_title="Guidewire Dev A",
        required_skills=json.dumps(["Guidewire"]), min_experience_years=3.0,
        work_location="REMOTE", status="OPEN", billing_rate_usd_cents=15000,
        assigned_bu_id=axion.id,
    )
    demand_b = Demand(
        tenant_id=tenant.id, client_id=acme.id, job_title="Guidewire Dev B",
        required_skills=json.dumps(["Guidewire"]), min_experience_years=3.0,
        work_location="REMOTE", status="IN_PROGRESS", billing_rate_usd_cents=15000,
        assigned_bu_id=prism.id,
    )
    db.add_all([demand_a, demand_b])
    db.commit()

    # Bench employee with Guidewire skill (current supply = 1).
    bench_employee = Employee(
        tenant_id=tenant.id, first_name="Sam", last_name="Lee", email="sam@blitzenx.com",
        joining_date=date(2025, 1, 1), status="BENCH",
        current_skills=json.dumps(["Guidewire"]),
    )
    db.add(bench_employee)
    db.commit()
    db.add(BenchPoolEntry(
        tenant_id=tenant.id, employee_id=bench_employee.id, available_from=date(2025, 6, 1),
        skill_tags=json.dumps(["Guidewire"]),
    ))
    db.commit()

    # Employee ACTIVE on an allocation ending in 20 days (expiring soon, adds to 30d supply).
    expiring_employee = Employee(
        tenant_id=tenant.id, first_name="Jane", last_name="Doe", email="jane@blitzenx.com",
        joining_date=date(2025, 1, 1), status="ALLOCATED",
        current_skills=json.dumps(["Guidewire"]),
    )
    db.add(expiring_employee)
    db.commit()
    expiring_allocation = EmployeeAllocation(
        tenant_id=tenant.id, employee_id=expiring_employee.id, demand_id=demand_a.id, client_id=acme.id,
        status="ACTIVE", start_date=date(2025, 1, 1), end_date=date.today() + timedelta(days=20),
    )
    db.add(expiring_allocation)
    db.commit()

    # Employee ACTIVE on an allocation ending in 75 days (60-90 bucket, not in 30d supply).
    later_employee = Employee(
        tenant_id=tenant.id, first_name="Alex", last_name="Kim", email="alex@blitzenx.com",
        joining_date=date(2025, 1, 1), status="ALLOCATED",
        current_skills=json.dumps(["PolicyCenter"]),
    )
    db.add(later_employee)
    db.commit()
    later_allocation = EmployeeAllocation(
        tenant_id=tenant.id, employee_id=later_employee.id, demand_id=demand_b.id, client_id=acme.id,
        status="ACTIVE", start_date=date(2025, 1, 1), end_date=date.today() + timedelta(days=75),
    )
    db.add(later_allocation)
    db.commit()

    ids = {
        "tenant_id": tenant.id, "bench_employee_id": bench_employee.id,
        "expiring_employee_id": expiring_employee.id, "later_employee_id": later_employee.id,
        "axion_id": axion.id, "prism_id": prism.id,
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

def _auth():
    return {"Authorization": f"Bearer {_token_for('admin@blitzenx.com')}"}

def test_unauthenticated_request_is_rejected(client):
    resp = client.get("/resource-forecast/expiring")
    assert resp.status_code in (401, 403)

def test_expiring_allocations_bucketed_correctly(client):
    ids = client.wros_ids
    resp = client.get("/resource-forecast/expiring", headers=_auth())
    assert resp.status_code == 200
    body = resp.json()

    assert len(body["under_30_days"]) == 1
    assert body["under_30_days"][0]["employee_id"] == ids["expiring_employee_id"]

    assert len(body["sixty_to_90_days"]) == 1
    assert body["sixty_to_90_days"][0]["employee_id"] == ids["later_employee_id"]

    assert body["thirty_to_60_days"] == []

def test_gap_analysis_computes_supply_vs_demand_per_skill(client):
    resp = client.get("/resource-forecast/gap-analysis", headers=_auth())
    assert resp.status_code == 200
    rows = {r["skill"]: r for r in resp.json()["rows"]}

    guidewire = rows["Guidewire"]
    assert guidewire["current_bench_count"] == 1
    assert guidewire["expiring_allocations_count_30d"] == 1
    assert guidewire["total_projected_supply"] == 2
    assert guidewire["open_demand_count"] == 2  # demand_a (OPEN) + demand_b (IN_PROGRESS)
    assert guidewire["gap"] == 0

    # PolicyCenter only appears on an employee in the 60-90 day bucket --
    # not on the bench, not in the 30-day expiring set, and no open
    # demand requires it -- so it correctly never surfaces as a row at
    # all (the service only unions skills from those three sources).
    assert "PolicyCenter" not in rows

def test_gap_analysis_scoped_to_business_unit_filters_demand_only(client):
    """business_unit_id narrows open_demand_count to that BU's own
    Demand rows (demand_a=Axion, demand_b=Prism) -- bench/expiring
    supply stays org-wide (no BU field exists on Employee/BenchPoolEntry
    anywhere in this codebase, a real, already-flagged gap -- filtering
    those would fabricate data, not narrow it)."""
    ids = client.wros_ids
    resp = client.get(
        "/resource-forecast/gap-analysis", headers=_auth(),
        params={"business_unit_id": ids["axion_id"]},
    )
    assert resp.status_code == 200
    rows = {r["skill"]: r for r in resp.json()["rows"]}
    guidewire = rows["Guidewire"]
    assert guidewire["open_demand_count"] == 1  # only demand_a (Axion), not demand_b (Prism)
    assert guidewire["current_bench_count"] == 1  # bench stays org-wide, unfiltered
    assert guidewire["expiring_allocations_count_30d"] == 1
