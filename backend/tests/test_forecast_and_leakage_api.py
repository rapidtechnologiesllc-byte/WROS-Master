"""
S-242 (Forecast vs Actual) + S-243 (Revenue Leakage Detection) API-level
same fixture shape as test_revenue_targets_api.py.
"""
import os
from datetime import date, datetime, timedelta

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
from app.models.invoice import Invoice
from app.models.opportunity import Opportunity
from app.models.project import Project
from app.models.rbac_template import BusinessUnit, Role
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
    engine = create_engine(f"sqlite:///{db_path}")

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    from app.api.v1.endpoints.forecast_and_leakage import router as forecast_and_leakage_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(forecast_and_leakage_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    RBACService.seed_roles_and_permissions(db)

    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()

    axion = BusinessUnit(name="Axion")
    db.add(axion)
    db.commit()

    partner_role = db.query(Role).filter(Role.name == "Partner").first()
    hr_manager_role = db.query(Role).filter(Role.name == "HR Manager").first()
    db.add(Users(
        UserID="U-TROY", UserRole="Partner", UserEmail="troy@blitzenx.com",
        UserPassword="h", tenant_id=tenant.id, role_id=partner_role.id, business_unit_id=axion.id,
    ))
    db.add(Users(
        UserID="U-AVINASH", UserRole="Super User", UserEmail="avinash@blitzenx.com",
        UserPassword="h", tenant_id=tenant.id,
    ))
    db.add(Users(
        UserID="U-HR", UserRole="HR Manager", UserEmail="hr@blitzenx.com",
        UserPassword="h", tenant_id=tenant.id, role_id=hr_manager_role.id if hr_manager_role else None,
    ))
    db.commit()

    builders = Client(tenant_id=tenant.id, company_name="Builders Insurance", business_unit_id=axion.id)
    db.add(builders)
    db.commit()

    ids = {"tenant_id": tenant.id, "axion_id": axion.id, "builders_id": builders.id}
    db.close()

    test_client = TestClient(app)
    test_client.wros_ids = ids
    test_client.SessionLocal = TestSessionLocal
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)

def _token_for(email):
    return security.create_access_token(data={"sub": email, "type": "internal", "name": email})

def _troy_auth():
    return {"Authorization": f"Bearer {_token_for('troy@blitzenx.com')}"}

def _avinash_auth():
    return {"Authorization": f"Bearer {_token_for('avinash@blitzenx.com')}"}

def _hr_auth():
    return {"Authorization": f"Bearer {_token_for('hr@blitzenx.com')}"}

def test_forecast_vs_actual_combines_won_opportunity_and_invoice(client):
    ids = client.wros_ids
    db = client.SessionLocal()
    today = date.today()
    won = Opportunity(
        tenant_id=ids["tenant_id"], client_id=ids["builders_id"], stage="WON",
        revenue_value_usd_cents=500_000, probability_pct=100, expected_close_date=today,
    )
    db.add(won)
    project = Project(tenant_id=ids["tenant_id"], client_id=ids["builders_id"], name="Builders SI Engagement")
    db.add(project)
    db.commit()
    invoice = Invoice(
        tenant_id=ids["tenant_id"], client_id=ids["builders_id"], project_id=project.id,
        status="PAID", total_usd_cents=300_000,
        billing_period_start=today.replace(day=1), billing_period_end=today,
    )
    db.add(invoice)
    db.commit()
    db.close()

    resp = client.get(
        "/forecast-vs-actual", headers=_avinash_auth(),
        params={"year": today.year, "month": today.month},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["actual_usd_cents"] == 300_000
    assert body["forecast_usd_cents"] == 500_000
    assert body["variance_usd_cents"] == -200_000

def test_stalled_opportunity_scan_flags_stale_pipeline(client):
    ids = client.wros_ids
    db = client.SessionLocal()
    stale_time = datetime.utcnow() - timedelta(days=45)
    stalled = Opportunity(
        tenant_id=ids["tenant_id"], client_id=ids["builders_id"], stage="PROPOSAL",
        revenue_value_usd_cents=200_000, probability_pct=50, updated_at=stale_time,
    )
    db.add(stalled)
    db.commit()
    db.close()

    resp = client.post("/revenue-leakage/scan", headers=_avinash_auth())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    stalled_flags = [f for f in body["flags"] if f["pattern_type"] == "STALLED_OPPORTUNITY"]
    assert len(stalled_flags) == 1
    assert stalled_flags[0]["estimated_impact_usd_cents"] == 200_000

def test_unfilled_demand_scan_flags_past_due_demand(client):
    ids = client.wros_ids
    db = client.SessionLocal()
    overdue = Demand(
        tenant_id=ids["tenant_id"], client_id=ids["builders_id"], job_title="Guidewire Dev",
        required_skills="[]", min_experience_years=3, work_location="REMOTE",
        headcount=3, positions_filled=1, status="OPEN",
        required_start_date=date.today() - timedelta(days=10),
        assigned_bu_id=ids["axion_id"], revenue_potential_usd_cents=900_000,
    )
    db.add(overdue)
    db.commit()
    db.close()

    resp = client.post("/revenue-leakage/scan", headers=_avinash_auth())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    unfilled_flags = [f for f in body["flags"] if f["pattern_type"] == "UNFILLED_DEMAND"]
    assert len(unfilled_flags) == 1
    # 2 of 3 positions open -> 2/3 of the revenue potential
    assert unfilled_flags[0]["estimated_impact_usd_cents"] == round(900_000 * 2 / 3)

def test_rescan_does_not_duplicate_flags(client):
    ids = client.wros_ids
    db = client.SessionLocal()
    stale_time = datetime.utcnow() - timedelta(days=45)
    db.add(Opportunity(
        tenant_id=ids["tenant_id"], client_id=ids["builders_id"], stage="PROPOSAL",
        revenue_value_usd_cents=200_000, probability_pct=50, updated_at=stale_time,
    ))
    db.commit()
    db.close()

    client.post("/revenue-leakage/scan", headers=_avinash_auth())
    resp = client.post("/revenue-leakage/scan", headers=_avinash_auth())
    stalled_flags = [f for f in resp.json()["flags"] if f["pattern_type"] == "STALLED_OPPORTUNITY"]
    assert len(stalled_flags) == 1

def test_hr_manager_cannot_scan_leakage_no_pnl_access(client):
    """Avinash's explicit access spec: 'finance & HR manager (no actual
    p&l)' -- HR Manager has revenue.view but not revenue.view_pnl, and
    leakage detail is gated at the P&L tier."""
    resp = client.post("/revenue-leakage/scan", headers=_hr_auth())
    assert resp.status_code == 403

def test_resolve_leakage_flag(client):
    ids = client.wros_ids
    db = client.SessionLocal()
    stale_time = datetime.utcnow() - timedelta(days=45)
    db.add(Opportunity(
        tenant_id=ids["tenant_id"], client_id=ids["builders_id"], stage="PROPOSAL",
        revenue_value_usd_cents=200_000, probability_pct=50, updated_at=stale_time,
    ))
    db.commit()
    db.close()

    scan_resp = client.post("/revenue-leakage/scan", headers=_avinash_auth())
    flag_id = scan_resp.json()["flags"][0]["id"]

    resolve_resp = client.post(
        f"/revenue-leakage/{flag_id}/resolve", headers=_avinash_auth(),
        json={"resolution_note": "Contract signed, moving to WON."},
    )
    assert resolve_resp.status_code == 200, resolve_resp.text
    assert resolve_resp.json()["resolved_at"] is not None

    active_resp = client.get("/revenue-leakage/active", headers=_avinash_auth())
    assert active_resp.json()["flags"] == []
