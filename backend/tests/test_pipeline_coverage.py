"""S-244 Pipeline Coverage on the Executive Revenue dashboard: open pipeline against the
stored FY revenue targets -- the org target for org-level users, the caller's own BU
targets for anyone BU-scoped -- never a target typed in by the viewer."""
import pytest
from sqlalchemy.orm import Session

from app.models.opportunity import Opportunity
from app.models.revenue_target import BURevenueTarget
from app.models.strategic_goal import GoalTarget
from app.services.fiscal_year_service import current_fy
from app.services.revenue_target_service import coverage_status
from tests.scope_fixtures import ApiClient, two_bu_world

DASHBOARD = "/api/v1/revenue-targets/dashboard"


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


def _opportunity(db, client, usd, stage="PROPOSAL"):
    db.add(Opportunity(tenant_id=1, client_id=client.id, stage=stage, revenue_value_usd_cents=usd * 100,
                       probability_pct=50))


def _bu_target(db, unit, usd):
    db.add(BURevenueTarget(tenant_id=1, business_unit_id=unit.id, target_period="ANNUAL",
                           fiscal_year=current_fy(db), target_amount_usd_cents=usd * 100))


def _bu_row(body, unit):
    return next(b for b in body["bu_metrics"] if b["business_unit_id"] == unit.id)


def test_bu_coverage_uses_the_latest_annual_bu_target(db, w, api):
    _opportunity(db, w.client_a, 300_000)
    _opportunity(db, w.client_a, 999_000, stage="CONTRACT")  # won: not open pipeline
    _bu_target(db, w.bu_a, 50_000)
    _bu_target(db, w.bu_a, 100_000)  # superseding row wins
    db.commit()

    row = _bu_row(api.get(w.org_user, DASHBOARD).json(), w.bu_a)
    assert row["target_usd_cents"] == 10_000_000
    assert row["pipeline_coverage"] == 3.0
    assert row["pipeline_coverage_status"] == "HEALTHY"


def test_partner_coverage_is_own_bus_against_own_targets(db, w, api):
    _opportunity(db, w.client_a, 150_000)
    _opportunity(db, w.client_b, 900_000)
    _bu_target(db, w.bu_a, 100_000)
    _bu_target(db, w.bu_b, 100_000)
    db.add(GoalTarget(tenant_id=1, year=current_fy(db), level="ORG", entity_id="org", metric="revenue",
                      target=1_000))
    db.commit()

    body = api.get(w.partner_a, DASHBOARD).json()
    assert body["pipeline_coverage_target_usd_cents"] == 10_000_000
    assert body["pipeline_coverage_pipeline_usd_cents"] == 15_000_000
    assert body["pipeline_coverage"] == 1.5
    assert body["pipeline_coverage_status"] == "LOW"
    assert {b["business_unit_id"] for b in body["bu_metrics"]} == {w.bu_a.id}


def test_org_coverage_uses_org_fy_target(db, w, api):
    _opportunity(db, w.client_a, 100_000)
    db.add(GoalTarget(tenant_id=1, year=current_fy(db), level="ORG", entity_id="org", metric="revenue",
                      target=200_000))
    db.commit()

    body = api.get(w.org_user, DASHBOARD).json()
    assert body["pipeline_coverage_target_usd_cents"] == 20_000_000
    expected = round(body["pipeline_coverage_pipeline_usd_cents"] / 20_000_000, 2)
    assert body["pipeline_coverage"] == expected
    assert body["pipeline_coverage_benchmark"] == 3.0


def test_no_target_means_no_coverage(db, w, api):
    _opportunity(db, w.client_a, 100_000)
    db.commit()

    body = api.get(w.partner_a, DASHBOARD).json()
    assert body["pipeline_coverage"] is None
    assert body["pipeline_coverage_status"] == "NO_TARGET"
    assert _bu_row(body, w.bu_a)["pipeline_coverage"] is None


def test_manual_target_endpoint_is_gone(w, api):
    resp = api.get(w.org_user, "/api/v1/revenue-targets/pipeline-coverage",
                   params={"revenue_target_usd_cents": 100})
    assert resp.status_code in (404, 405)


@pytest.mark.parametrize("ratio,status", [(None, "NO_TARGET"), (0.0, "LOW"), (1.99, "LOW"), (2.0, "THIN"),
                                          (2.99, "THIN"), (3.0, "HEALTHY"), (7.5, "HEALTHY")])
def test_coverage_bands(ratio, status):
    assert coverage_status(ratio) == status
