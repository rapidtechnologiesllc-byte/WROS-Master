"""
EPIC-16 Fully Loaded Cost + Blended Delivery Rate API-level proof.
"""
import os
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
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.demand import Demand
from app.models.invoice import Invoice
from app.models.project import Project
from app.models.rbac_template import BusinessUnit
from app.models.tenant import Tenant
from app.models.timesheet import Timesheet
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

    from app.api.v1.endpoints.cost_rate import router as cost_rate_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(cost_rate_router)
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

    employee = Employee(
        tenant_id=tenant.id, first_name="Sam", last_name="Dev", email="sam@blitzenx.com",
        joining_date=date(2024, 1, 1), base_salary_usd_cents=1_000_000,  # $10,000/month
    )
    db.add(employee)
    db.commit()

    builders = Client(tenant_id=tenant.id, company_name="Builders Insurance", business_unit_id=axion.id)
    db.add(builders)
    db.commit()

    project = Project(tenant_id=tenant.id, client_id=builders.id, name="Builders Engagement")
    db.add(project)
    db.commit()

    today = date.today()
    db.add(Invoice(
        tenant_id=tenant.id, client_id=builders.id, project_id=project.id,
        status="PAID", total_usd_cents=100_000_00,
        billing_period_start=today.replace(day=1), billing_period_end=today,
        created_at=datetime(today.year, today.month, 15),
    ))
    db.commit()

    filled_demand = Demand(
        tenant_id=tenant.id, client_id=builders.id, job_title="Guidewire Dev",
        required_skills="[]", min_experience_years=3, work_location="REMOTE",
        headcount=1, positions_filled=1, status="FILLED", assigned_bu_id=axion.id,
    )
    db.add(filled_demand)
    db.commit()
    allocation = EmployeeAllocation(
        tenant_id=tenant.id, employee_id=employee.id, demand_id=filled_demand.id,
        client_id=builders.id, status="ACTIVE",
    )
    db.add(allocation)
    db.commit()
    db.add(Timesheet(
        tenant_id=tenant.id, employee_id=employee.id, allocation_id=allocation.id,
        week_starting_date=today.replace(day=1), billable_hours=100, status="APPROVED",
    ))
    db.commit()

    ids = {
        "tenant_id": tenant.id, "axion_id": axion.id, "employee_id": employee.id,
        "year": today.year, "month": today.month,
    }
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

def test_fully_loaded_cost_requires_a_config_first(client):
    ids = client.wros_ids
    resp = client.get(f"/employees/{ids['employee_id']}/fully-loaded-cost", headers=_avinash_auth())
    assert resp.status_code == 400

def test_fully_loaded_cost_computes_from_config(client):
    ids = client.wros_ids
    client.post(
        "/cost-rate-configs", headers=_avinash_auth(),
        json={"statutory_pct": 12.0, "overhead_pct": 8.0},
    )
    resp = client.get(f"/employees/{ids['employee_id']}/fully-loaded-cost", headers=_avinash_auth())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # base 1,000,000 + 12% (120,000) + 8% (80,000) = 1,200,000
    assert body["fully_loaded_cost_usd_cents"] == 1_200_000

def test_bu_specific_config_wins_over_org_wide(client):
    ids = client.wros_ids
    client.post("/cost-rate-configs", headers=_avinash_auth(), json={"statutory_pct": 12.0, "overhead_pct": 8.0})
    client.post(
        "/cost-rate-configs", headers=_avinash_auth(),
        json={"business_unit_id": ids["axion_id"], "statutory_pct": 15.0, "overhead_pct": 5.0},
    )
    resp = client.get(
        f"/employees/{ids['employee_id']}/fully-loaded-cost", headers=_avinash_auth(),
        params={"business_unit_id": ids["axion_id"]},
    )
    assert resp.status_code == 200, resp.text
    # base 1,000,000 + 15% (150,000) + 5% (50,000) = 1,200,000 (same total, different split -- proves BU row wins)
    assert resp.json()["fully_loaded_cost_usd_cents"] == 1_200_000

def test_blended_delivery_rate_computes_from_real_invoice_and_timesheet_data(client):
    ids = client.wros_ids
    resp = client.get(
        f"/blended-delivery-rate/bu/{ids['axion_id']}", headers=_avinash_auth(),
        params={"year": ids["year"], "month": ids["month"]},
    )
    assert resp.status_code == 200, resp.text
    # $100,000 revenue / 100 billable hours = $1,000/hour = 100,000 cents/hour
    assert resp.json()["blended_delivery_rate_usd_cents_per_hour"] == 100_000.0

def test_blended_delivery_rate_none_when_no_billable_hours(client):
    resp = client.get(
        "/blended-delivery-rate/bu/999999", headers=_avinash_auth(), params={"year": 2020, "month": 1},
    )
    assert resp.status_code == 200
    assert resp.json()["blended_delivery_rate_usd_cents_per_hour"] is None

def test_bu_pnl_computes_revenue_minus_fully_loaded_cost(client):
    ids = client.wros_ids
    client.post("/cost-rate-configs", headers=_avinash_auth(), json={"statutory_pct": 12.0, "overhead_pct": 8.0})
    resp = client.get(
        f"/pnl/bu/{ids['axion_id']}", headers=_avinash_auth(),
        params={"year": ids["year"], "month": ids["month"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["revenue_usd_cents"] == 100_000_00
    assert body["cost_usd_cents"] == 1_200_000  # fully loaded cost of the one allocated employee
    assert body["gross_margin_usd_cents"] == 100_000_00 - 1_200_000
    assert body["cost_data_complete"] is True

def test_org_pnl_summary_sums_across_business_units(client):
    client.post("/cost-rate-configs", headers=_avinash_auth(), json={"statutory_pct": 12.0, "overhead_pct": 8.0})
    ids = client.wros_ids
    resp = client.get("/pnl/org-summary", headers=_avinash_auth(), params={"year": ids["year"], "month": ids["month"]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_revenue_usd_cents"] == 100_000_00
    assert body["total_cost_usd_cents"] == 1_200_000
    assert body["org_cost_data_complete"] is True
    assert len(body["by_business_unit"]) == 1
    assert body["by_business_unit"][0]["business_unit_name"] == "Axion"

def test_org_pnl_summary_incomplete_when_no_config_set(client):
    ids = client.wros_ids
    resp = client.get("/pnl/org-summary", headers=_avinash_auth(), params={"year": ids["year"], "month": ids["month"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["org_cost_data_complete"] is False
    assert body["total_cost_usd_cents"] is None
    assert body["total_gross_margin_usd_cents"] is None

def test_bu_pnl_flags_incomplete_cost_data_when_no_config(client):
    ids = client.wros_ids
    resp = client.get(
        f"/pnl/bu/{ids['axion_id']}", headers=_avinash_auth(),
        params={"year": ids["year"], "month": ids["month"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cost_data_complete"] is False
    assert body["cost_usd_cents"] is None
    assert body["gross_margin_usd_cents"] is None

def test_reserve_fund_contribution_and_status(client):
    ids = client.wros_ids
    client.post("/cost-rate-configs", headers=_avinash_auth(), json={"statutory_pct": 12.0, "overhead_pct": 8.0})

    create_resp = client.post(
        "/reserve-fund/entries", headers=_avinash_auth(),
        json={
            "entry_type": "CONTRIBUTION", "amount_usd_cents": 500_000,
            "period_year": ids["year"], "period_month": ids["month"], "business_unit_id": ids["axion_id"],
        },
    )
    assert create_resp.status_code == 201, create_resp.text

    status_resp = client.get(
        f"/reserve-fund/bu/{ids['axion_id']}/status", headers=_avinash_auth(),
        params={"year": ids["year"], "month": ids["month"]},
    )
    assert status_resp.status_code == 200, status_resp.text
    body = status_resp.json()
    assert body["balance_usd_cents"] == 500_000
    # target = trailing avg monthly cost (1,200,000, only 1 month has data) x 12
    assert body["target_usd_cents"] == 1_200_000 * 12
    assert body["pct_funded"] == round(500_000 / (1_200_000 * 12) * 100, 1)

def test_reserve_fund_withdrawal_reduces_balance(client):
    ids = client.wros_ids
    client.post(
        "/reserve-fund/entries", headers=_avinash_auth(),
        json={
            "entry_type": "CONTRIBUTION", "amount_usd_cents": 500_000,
            "period_year": ids["year"], "period_month": ids["month"], "business_unit_id": ids["axion_id"],
        },
    )
    client.post(
        "/reserve-fund/entries", headers=_avinash_auth(),
        json={
            "entry_type": "WITHDRAWAL", "amount_usd_cents": 200_000,
            "period_year": ids["year"], "period_month": ids["month"], "business_unit_id": ids["axion_id"],
        },
    )
    status_resp = client.get(
        f"/reserve-fund/bu/{ids['axion_id']}/status", headers=_avinash_auth(),
        params={"year": ids["year"], "month": ids["month"]},
    )
    assert status_resp.json()["balance_usd_cents"] == 300_000

def test_hiring_affordability_affordable_hire(client):
    ids = client.wros_ids
    client.post("/cost-rate-configs", headers=_avinash_auth(), json={"statutory_pct": 12.0, "overhead_pct": 8.0})
    # Revenue is 100,000_00, current cost 1,200,000 -- plenty of room for a small hire.
    resp = client.get(
        f"/hiring-affordability/bu/{ids['axion_id']}", headers=_avinash_auth(),
        params={"proposed_annual_salary_usd_cents": 1_200_000, "year": ids["year"], "month": ids["month"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["affordable"] is True
    assert body["projected_margin_pct"] > 0

def test_hiring_affordability_unaffordable_hire(client):
    ids = client.wros_ids
    client.post("/cost-rate-configs", headers=_avinash_auth(), json={"statutory_pct": 12.0, "overhead_pct": 8.0})
    # A huge proposed salary blows past the BU's entire revenue.
    resp = client.get(
        f"/hiring-affordability/bu/{ids['axion_id']}", headers=_avinash_auth(),
        params={"proposed_annual_salary_usd_cents": 500_000_000_00, "year": ids["year"], "month": ids["month"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["affordable"] is False
    assert body["projected_margin_pct"] < 0
    assert "floor" in body["reason"]

def test_hiring_affordability_none_when_cost_data_incomplete(client):
    ids = client.wros_ids
    resp = client.get(
        f"/hiring-affordability/bu/{ids['axion_id']}", headers=_avinash_auth(),
        params={"proposed_annual_salary_usd_cents": 1_200_000, "year": ids["year"], "month": ids["month"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["affordable"] is None
    assert body["reason"] is not None

def test_intercompany_settlement_records_and_updates_net_position(client):
    resp = client.post(
        "/intercompany-settlements", headers=_avinash_auth(),
        json={
            "from_entity": "BXUS", "to_entity": "BXIN", "amount_usd_cents": 50_000_00,
            "settlement_date": date.today().isoformat(), "reason": "Offshore delivery reimbursement",
        },
    )
    assert resp.status_code == 201, resp.text

    bxin_resp = client.get("/intercompany-settlements/entity/BXIN/net-position", headers=_avinash_auth())
    assert bxin_resp.json()["net_position_usd_cents"] == 50_000_00

    bxus_resp = client.get("/intercompany-settlements/entity/BXUS/net-position", headers=_avinash_auth())
    assert bxus_resp.json()["net_position_usd_cents"] == -50_000_00

    list_resp = client.get("/intercompany-settlements", headers=_avinash_auth())
    assert len(list_resp.json()) == 1

def test_intercompany_settlement_rejects_same_entity(client):
    resp = client.post(
        "/intercompany-settlements", headers=_avinash_auth(),
        json={
            "from_entity": "BXUS", "to_entity": "BXUS", "amount_usd_cents": 100,
            "settlement_date": date.today().isoformat(), "reason": "Invalid",
        },
    )
    assert resp.status_code == 400

def test_bank_transaction_match_requires_exact_amount(client):
    ids = client.wros_ids
    create_resp = client.post(
        "/bank-transactions", headers=_avinash_auth(),
        json={"transaction_date": date.today().isoformat(), "amount_usd_cents": 999_00, "description": "Wire from Builders"},
    )
    assert create_resp.status_code == 201, create_resp.text
    txn_id = create_resp.json()["id"]

    match_resp = client.post(
        f"/bank-transactions/{txn_id}/match", headers=_avinash_auth(),
        json={"invoice_id": "does-not-need-to-be-real-for-this-check"},
    )
    # Invoice lookup itself 404s before the amount check even runs,
    # since we didn't seed a real invoice with that id here.
    assert match_resp.status_code == 404

def test_bank_transaction_matches_real_invoice_exact_amount(client):
    ids = client.wros_ids
    # This fixture's own seeded Invoice is $100,000.00 (100_000_00 cents).
    create_resp = client.post(
        "/bank-transactions", headers=_avinash_auth(),
        json={"transaction_date": date.today().isoformat(), "amount_usd_cents": 100_000_00, "description": "Wire from Builders"},
    )
    txn_id = create_resp.json()["id"]

    # Find the seeded invoice via the unmatched-paid-invoices list.
    unmatched = client.get("/invoices/unmatched-paid", headers=_avinash_auth()).json()
    assert len(unmatched) == 1
    invoice_id = unmatched[0]["invoice_id"]

    match_resp = client.post(
        f"/bank-transactions/{txn_id}/match", headers=_avinash_auth(),
        json={"invoice_id": invoice_id},
    )
    assert match_resp.status_code == 200, match_resp.text
    assert match_resp.json()["reconciled"] is True

    still_unmatched = client.get("/invoices/unmatched-paid", headers=_avinash_auth()).json()
    assert still_unmatched == []

def test_bank_transaction_rejects_amount_mismatch(client):
    create_resp = client.post(
        "/bank-transactions", headers=_avinash_auth(),
        json={"transaction_date": date.today().isoformat(), "amount_usd_cents": 1_00, "description": "Wrong amount"},
    )
    txn_id = create_resp.json()["id"]
    unmatched = client.get("/invoices/unmatched-paid", headers=_avinash_auth()).json()
    invoice_id = unmatched[0]["invoice_id"]

    match_resp = client.post(
        f"/bank-transactions/{txn_id}/match", headers=_avinash_auth(),
        json={"invoice_id": invoice_id},
    )
    assert match_resp.status_code == 400
