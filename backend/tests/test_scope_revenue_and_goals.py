"""Business-unit visibility, slice 1 (money): revenue chain and P&L, BU revenue targets,
partner incentives and the FY goal tree. Partner A must never see BU B's money or set
BU B's targets; org-level users see and set everything (CEO 2026-10-12)."""
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.project import Project
from app.models.user import Jobs
from app.services import timesheet_service
from app.services.employee_allocation_service import allocate_employee_to_project
from tests.scope_fixtures import ApiClient, ids, two_bu_world, uid

MONDAY = date(2026, 8, 3)


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def w(db):
    return two_bu_world(db)


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _billed_week(db, client, unit):
    """One approved 8-hour day for a worker of `unit` on a project of `client`."""
    project = Project(tenant_id=1, client_id=client.id, name=f"Project {uid()}", delivery_engine="CORE", currency="USD")
    db.add(project)
    db.flush()
    job = Jobs(tenant_id=1, client_id=client.id, project_id=project.id, business_unit_id=unit.id, jobTitle="Dev",
               jobDescription="d", jobSkills="x", jobExperience="5", jobLocation="Remote", billing_rate_usd_cents=10000)
    worker = Employee(tenant_id=1, first_name="Sam", last_name=uid(), email=f"s{uid()}@x.com",
                      joining_date=date(2025, 1, 1), status="BENCH", bu_id=unit.id)
    db.add_all([job, worker])
    db.flush()
    allocation = allocate_employee_to_project(db, tenant_id=1, employee=worker, demand=job, start_date=date(2026, 8, 1))
    db.flush()
    ts = timesheet_service.create_weekly_draft(db, allocation, MONDAY, tenant_id=1)
    db.flush()
    timesheet_service.upsert_entries(db, ts, [{"entry_date": MONDAY, "hours": 8}])
    ts.status = "APPROVED"
    db.commit()
    return ts


def test_revenue_chain_and_pnl_show_only_own_business_units(db, w, api):
    mine, theirs = _billed_week(db, w.client_a, w.bu_a), _billed_week(db, w.client_b, w.bu_b)
    period = {"start": "2026-08-01", "end": "2026-08-31"}

    lines = ids(api.get(w.partner_a, "/api/v1/revenue-chain/lines", params=period).json(), "timesheet_id")
    assert mine.id in lines and theirs.id not in lines
    asked_for_b = api.get(w.partner_a, "/api/v1/revenue-chain/lines",
                          params={**period, "partner_user_id": w.partner_b.UserID}).json()
    assert asked_for_b["count"] == 0

    summary = api.get(w.partner_a, "/api/v1/revenue-chain/summary", params={**period, "group_by": "business_unit"})
    assert ids(summary.json(), "key") == {w.bu_a.id}

    pnl = api.get(w.partner_a, "/api/v1/revenue-chain/pnl", params=period).json()
    assert {row["key"] for row in pnl["by_business_unit"]} == {w.bu_a.id}
    assert pnl["revenue_usd_cents"] == 80000

    org = api.get(w.org_user, "/api/v1/revenue-chain/lines", params=period).json()
    assert {mine.id, theirs.id} <= ids(org, "timesheet_id")


def test_bu_revenue_targets_are_own_business_units_only(w, api):
    query = {"target_period": "ANNUAL", "fiscal_year": 2026}
    assert api.get(w.partner_a, f"/api/v1/revenue-targets/bu/{w.bu_b.id}", params=query).status_code == 404
    assert api.get(w.partner_a, f"/api/v1/revenue-targets/bu/{w.bu_a.id}", params=query).status_code == 200
    body = {"business_unit_id": w.bu_b.id, "target_period": "ANNUAL", "fiscal_year": 2026,
            "target_amount_usd_cents": 100000}
    assert api.post(w.partner_a, "/api/v1/revenue-targets/bu", json=body).status_code == 403


def test_partner_sees_only_own_incentives_and_never_sets_them(w, api):
    assert api.get(w.partner_a, f"/api/v1/partner-incentives/partners/{w.partner_b.UserID}/events").status_code == 404
    assert api.get(w.partner_a, f"/api/v1/partner-incentives/partners/{w.partner_a.UserID}/events").status_code == 200
    assert api.get(w.org_user, f"/api/v1/partner-incentives/partners/{w.partner_b.UserID}/events").status_code == 200
    rule = {"partner_user_id": w.partner_a.UserID, "incentive_type": "REVENUE_SHARE", "revenue_share_pct": 50,
            "trigger_description": "self-set"}
    assert api.post(w.partner_a, "/api/v1/partner-incentives/rules", json=rule).status_code == 403
    calc = f"/api/v1/partner-incentives/partners/{w.partner_a.UserID}/calculate-revenue-share"
    assert api.post(w.partner_a, calc, params={"year": 2026, "month": 8}).status_code == 403


def test_goal_tree_shows_and_sets_only_own_business_units(w, api):
    tree = api.get(w.partner_a, "/api/v1/goals/tree", params={"year": 2026}).json()
    assert ids(tree, "bu_id") == {w.bu_a.id}
    assert tree["tree"]["editable"] is False
    full = api.get(w.org_user, "/api/v1/goals/tree", params={"year": 2026}).json()
    assert {w.bu_a.id, w.bu_b.id} <= ids(full, "bu_id")

    def target(bu, level="BU"):
        entity = "org" if level == "ORG" else f"{company}:{bu.id}"
        return {"level": level, "entity_id": entity, "metric": "revenue", "target": 1000, "year": 2026}

    company = next(n for n in tree["tree"]["children"])["entity_id"]
    assert api.put(w.partner_a, "/api/v1/goals/targets", json=target(w.bu_b)).status_code == 403
    assert api.put(w.partner_a, "/api/v1/goals/targets", json=target(w.bu_a, "ORG")).status_code == 403
    assert api.put(w.partner_a, "/api/v1/goals/fy-targets/revenue", json={"target": 1000}).status_code == 403
    assert api.put(w.partner_a, "/api/v1/goals/fy-settings", json={"start_month": 4}).status_code == 403
