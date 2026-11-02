"""FY goal tree roll-up (CEO 2026-11-02): BU targets add up to partner, company and
organization rows; a figure typed on a summed row is kept as its plan. Revenue stops at the
company -- company revenue includes intercompany billing, so the organization revenue target
is external revenue, typed on its own."""
import pytest
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnitCompany
from app.models.location import Location
from app.services.ceo_fy_progress_service import get_fy_targets
from tests.scope_fixtures import ApiClient, two_bu_world, uid

TREE = "/api/v1/goals/tree"
TARGETS = "/api/v1/goals/targets"


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
    world = two_bu_world(db)
    company = Location(tenant_id=1, name=f"co-{uid()}")
    db.add(company)
    db.flush()
    db.add_all([BusinessUnitCompany(tenant_id=1, business_unit_id=bu.id, company_id=company.id)
                for bu in (world.bu_a, world.bu_b)])
    db.commit()
    world.company = company
    return world


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _walk(node):
    yield node
    for child in node.get("children") or []:
        yield from _walk(child)


def _node(tree, level, entity_id):
    return next(n for n in _walk(tree["tree"]) if n["level"] == level and n["entity_id"] == entity_id)


def _company_with_bus(tree, w):
    return _node(tree, "LOCATION", w.company.id)


def _set(api, user, level, entity_id, metric, target):
    resp = api.put(user, TARGETS, json={"level": level, "entity_id": entity_id, "metric": metric, "target": target})
    assert resp.status_code == 200, resp.text


def test_bu_targets_roll_up_to_partner_company_and_org(db, w, api):
    company = _company_with_bus(api.get(w.org_user, TREE).json(), w)["entity_id"]
    _set(api, w.org_user, "ORG", "org", "headcount", 175)
    _set(api, w.org_user, "BU", f"{company}:{w.bu_a.id}", "headcount", 100)
    _set(api, w.org_user, "BU", f"{company}:{w.bu_b.id}", "headcount", 50)

    tree = api.get(w.org_user, TREE).json()
    partner_a = _node(tree, "PARTNER", f"{company}:{w.partner_a.UserID}")["metrics"]["headcount"]
    assert partner_a["target"] == 100 and partner_a["rolled_up"] is True

    company_cell = _node(tree, "LOCATION", company)["metrics"]["headcount"]
    assert company_cell["target"] == 150 and company_cell["rolled_up"] is True

    org = tree["tree"]["metrics"]["headcount"]
    assert org["rolled_up"] is True
    assert org["plan"] == 175
    assert org["unassigned"] == 175 - org["target"]
    assert get_fy_targets(db, tree["year"], tenant_id=1)["headcount"]["target"] == org["target"]


def test_row_without_targets_below_keeps_its_typed_target(w, api):
    company = _company_with_bus(api.get(w.org_user, TREE).json(), w)["entity_id"]
    _set(api, w.org_user, "PARTNER", f"{company}:{w.partner_a.UserID}", "new_logos", 4)

    cell = _node(api.get(w.org_user, TREE).json(), "PARTNER", f"{company}:{w.partner_a.UserID}")["metrics"]["new_logos"]
    assert cell["target"] == 4
    assert cell["rolled_up"] is False
    assert "plan" not in cell


def test_revenue_rolls_to_company_but_org_stays_external(w, api):
    company = _company_with_bus(api.get(w.org_user, TREE).json(), w)["entity_id"]
    _set(api, w.org_user, "ORG", "org", "revenue", 15_000_000)
    _set(api, w.org_user, "BU", f"{company}:{w.bu_a.id}", "revenue", 2_000_000)

    tree = api.get(w.org_user, TREE).json()
    assert _node(tree, "LOCATION", company)["metrics"]["revenue"]["rolled_up"] is True
    org = tree["tree"]["metrics"]["revenue"]
    assert org["target"] == 15_000_000
    assert org["rolled_up"] is False
    assert org["companies_total"] >= 2_000_000  # other companies in the test DB may add theirs
