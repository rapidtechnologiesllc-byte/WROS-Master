"""
Task 6 (EPIC-03 Revenue-to-Workforce Conversion) API-level proof.
Throwaway SQLite, throwaway JWT keys -- never the real database.
"""
import os
import tempfile
from datetime import date, datetime

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
from app.models.invoice import Invoice
from app.models.opportunity import Opportunity
from app.models.project import Project
from app.models.rbac_template import BusinessUnit
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.rbac_service_template import RBACService
import app.models  # noqa: F401


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

    from app.api.v1.endpoints.revenue_to_demand import router as r2d_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(r2d_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    RBACService.seed_roles_and_permissions(db)

    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()

    axion = BusinessUnit(name="Axion")
    db.add(axion)
    db.commit()

    db.add(Users(
        UserID="U-AVINASH", UserRole="Super User", UserEmail="avinash@blitzenx.com",
        UserPassword="h", tenant_id=tenant.id,
    ))
    db.commit()

    builders = Client(tenant_id=tenant.id, company_name="Builders Insurance", business_unit_id=axion.id)
    db.add(builders)
    db.commit()

    project = Project(tenant_id=tenant.id, client_id=builders.id, name="Builders Engagement")
    db.add(project)
    db.commit()

    today = date.today()
    # Trailing revenue: 3 months x $300k = $900k, avg $300k/month
    for offset in (1, 2, 3):
        m = today.month - offset
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        db.add(Invoice(
            tenant_id=tenant.id, client_id=builders.id, project_id=project.id,
            status="PAID", total_usd_cents=300_000_00,
            billing_period_start=date(y, m, 1), billing_period_end=date(y, m, 28),
            created_at=datetime(y, m, 15),
        ))
    db.commit()

    # 2 employees currently allocated -> revenue_per_head = 300k/2 = 150k/month
    # (each allocation needs a real filled Demand row -- demand_id is NOT NULL)
    emp1 = Employee(tenant_id=tenant.id, first_name="A", last_name="One", email="a1@blitzenx.com", joining_date=date(2024, 1, 1))
    emp2 = Employee(tenant_id=tenant.id, first_name="A", last_name="Two", email="a2@blitzenx.com", joining_date=date(2024, 1, 1))
    db.add_all([emp1, emp2])
    db.commit()
    filled_demand_1 = Demand(
        tenant_id=tenant.id, client_id=builders.id, job_title="Guidewire Dev 1",
        required_skills="[]", min_experience_years=3, work_location="REMOTE",
        headcount=1, positions_filled=1, status="FILLED", assigned_bu_id=axion.id,
    )
    filled_demand_2 = Demand(
        tenant_id=tenant.id, client_id=builders.id, job_title="Guidewire Dev 2",
        required_skills="[]", min_experience_years=3, work_location="REMOTE",
        headcount=1, positions_filled=1, status="FILLED", assigned_bu_id=axion.id,
    )
    db.add_all([filled_demand_1, filled_demand_2])
    db.commit()
    db.add(EmployeeAllocation(tenant_id=tenant.id, employee_id=emp1.id, demand_id=filled_demand_1.id, client_id=builders.id, status="ACTIVE"))
    db.add(EmployeeAllocation(tenant_id=tenant.id, employee_id=emp2.id, demand_id=filled_demand_2.id, client_id=builders.id, status="ACTIVE"))
    db.commit()

    # Forecast for target month: WON opportunity worth $600k -> implies 4 heads needed at 150k/head
    db.add(Opportunity(
        tenant_id=tenant.id, client_id=builders.id, stage="WON",
        revenue_value_usd_cents=600_000_00, probability_pct=100, expected_close_date=today,
    ))
    db.commit()

    # Open demand already in pipeline: 1 position
    db.add(Demand(
        tenant_id=tenant.id, client_id=builders.id, job_title="Guidewire Dev",
        required_skills="[]", min_experience_years=3, work_location="REMOTE",
        headcount=1, positions_filled=0, status="OPEN", assigned_bu_id=axion.id,
    ))
    db.commit()

    ids = {"axion_id": axion.id, "year": today.year, "month": today.month}
    db.close()

    test_client = TestClient(app)
    test_client.wros_ids = ids
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _avinash_auth():
    token = security.create_access_token(data={"sub": "avinash@blitzenx.com", "type": "internal", "name": "avinash@blitzenx.com"})
    return {"Authorization": f"Bearer {token}"}


def test_revenue_to_demand_projection(client):
    ids = client.wros_ids
    resp = client.get(
        f"/revenue-to-demand/bu/{ids['axion_id']}", headers=_avinash_auth(),
        params={"year": ids["year"], "month": ids["month"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["current_headcount"] == 2
    assert body["revenue_per_head_usd_cents"] == 15_000_000  # 300k/head/month, in cents
    assert body["forecast_usd_cents"] == 60_000_000  # WON opp counted at full value
    assert body["projected_headcount_needed"] == 4.0  # 600k forecast / 150k per head
    assert body["open_demand_headcount"] == 1
    # gap = needed(4) - current(2) - already-open-demand(1) = 1 more to plan for
    assert body["workforce_gap"] == 1.0


def test_zero_headcount_returns_no_ratio(client):
    """A BU with no current headcount can't derive a revenue-per-head
    ratio -- must return None, never a fabricated number or a
    divide-by-zero crash."""
    resp_headers = _avinash_auth()
    # A brand-new BU with no clients/employees at all.
    create_resp = client.get("/revenue-to-demand/bu/999999", headers=resp_headers, params={"year": 2026, "month": 1})
    assert create_resp.status_code == 200
    body = create_resp.json()
    assert body["current_headcount"] == 0
    assert body["revenue_per_head_usd_cents"] is None
    assert body["projected_headcount_needed"] is None
    assert body["workforce_gap"] is None
