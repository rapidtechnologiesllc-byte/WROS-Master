"""Partner Home (CEO decision 2, 2026-10-17): one partner screen, scoped to every business unit the
partner leads. GET /dashboards/partner/performance (KPIs, trend, actions) and GET /dashboards/partner
(targets, operations) enforce the same scope: a partner sees all of their own BUs in total, may narrow
to one of them, and is refused any other BU or any other partner; org-level users pick a partner."""
import uuid
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.training_dashboards import get_partner_dashboard, get_partner_performance
from app.models.business_unit import BusinessUnit
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.project import Project
from app.models.role_template import RoleTemplate
from app.models.tenant import Tenant
from app.models.user import Users

NOW = datetime.utcnow()
PERIOD = f"{NOW:%Y-%m}"


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _uid():
    return uuid.uuid4().hex[:8]


def _user(db, org_level=False):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    role = RoleTemplate(tenant_id=1, name=f"p-{_uid()}", display_name="P", hierarchy_level=16,
                        org_level_access=org_level, enabled=True)
    db.add(role)
    db.flush()
    user = Users(UserID=f"U-{_uid()}", UserName=f"User {_uid()}", UserEmail=f"{_uid()}@x.com", UserPassword="x",
                 UserRole="x", tenant_id=1, role_template_id=role.id)
    db.add(user)
    db.flush()
    return user


def _unit(db, partner, revenue_cents=0):
    unit = BusinessUnit(tenant_id=1, name=f"bu-{_uid()}", display_name=f"BU {_uid()}",
                        partner_user_id=partner.UserID if partner else None)
    db.add(unit)
    db.flush()
    if revenue_cents:
        client = Client(tenant_id=1, company_name=f"Client {_uid()}", business_unit_id=unit.id, payment_terms_days=30)
        db.add(client)
        db.flush()
        project = Project(tenant_id=1, client_id=client.id, name=f"Project {_uid()}", delivery_engine="CORE")
        db.add(project)
        db.flush()
        db.add(Invoice(tenant_id=1, client_id=client.id, project_id=project.id, status="APPROVED",
                       billing_period_start=NOW.date(), billing_period_end=NOW.date(),
                       total_usd_cents=revenue_cents, created_at=NOW))
        db.flush()
    return unit


def _performance(db, user, **params):
    return get_partner_performance(partner_user_id=params.get("partner_user_id"),
                                   business_unit_id=params.get("business_unit_id"), year_month=PERIOD,
                                   months_back=2, db=db, current_user=user)


def test_a_partner_sees_every_bu_they_lead_in_total_and_per_bu(db):
    partner = _user(db)
    first, second = _unit(db, partner, 100_00), _unit(db, partner, 250_00)
    _unit(db, _user(db), 999_00)  # another partner's BU never counts

    result = _performance(db, partner)
    kpis = result["data"]["kpis"]
    assert kpis["business_unit_ids"] == sorted([first.id, second.id])
    assert kpis["revenue_usd_cents"] == 350_00
    per_bu = {row["business_unit_id"]: row["revenue_usd_cents"] for row in kpis["by_business_unit"]}
    assert per_bu == {first.id: 100_00, second.id: 250_00}
    assert {bu["id"] for bu in result["business_units"]} == {first.id, second.id}
    assert len(result["data"]["trend"]) == 2 and result["data"]["trend"][-1]["period"] == PERIOD


def test_the_bu_filter_narrows_to_one_of_the_partners_bus(db):
    partner = _user(db)
    first, _second = _unit(db, partner, 100_00), _unit(db, partner, 250_00)
    kpis = _performance(db, partner, business_unit_id=first.id)["data"]["kpis"]
    assert kpis["business_unit_ids"] == [first.id] and kpis["revenue_usd_cents"] == 100_00


def test_a_bu_the_partner_does_not_lead_is_refused_on_both_endpoints(db):
    partner = _user(db)
    _unit(db, partner)
    foreign = _unit(db, _user(db))
    with pytest.raises(HTTPException) as denied:
        _performance(db, partner, business_unit_id=foreign.id)
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as denied:
        get_partner_dashboard(partner_user_id=None, business_unit_id=foreign.id, year=None, db=db,
                              current_user=partner)
    assert denied.value.status_code == 403


def test_a_partner_cannot_open_another_partners_home(db):
    partner, other = _user(db), _user(db)
    _unit(db, partner)
    _unit(db, other)
    with pytest.raises(HTTPException) as denied:
        _performance(db, partner, partner_user_id=other.UserID)
    assert denied.value.status_code == 403


def test_someone_who_partners_no_bu_and_is_not_org_level_is_refused(db):
    with pytest.raises(HTTPException) as denied:
        _performance(db, _user(db))
    assert denied.value.status_code == 403


def test_org_level_users_pick_a_partner(db):
    partner, leader = _user(db), _user(db, org_level=True)
    unit = _unit(db, partner, 40_00)
    assert _performance(db, leader)["status"] == "needs_partner"
    kpis = _performance(db, leader, partner_user_id=partner.UserID)["data"]["kpis"]
    assert kpis["business_unit_ids"] == [unit.id] and kpis["revenue_usd_cents"] == 40_00


def test_actions_follow_the_kpis():
    from app.services.partner_roi_service import get_partner_actions

    kpis = {"practice_utilization_pct": 50, "pnl_margin_pct": 10, "practice_growth_yoy_pct": -5, "net_new_logos": 0}
    assert [a["category"] for a in get_partner_actions(kpis)] == ["MARGIN", "UTILIZATION", "GROWTH", "LOGOS"]
    healthy = {"practice_utilization_pct": 90, "pnl_margin_pct": 30, "practice_growth_yoy_pct": 5, "net_new_logos": 3}
    assert get_partner_actions(healthy) == []
