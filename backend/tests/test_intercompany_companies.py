"""Intercompany settlements reference companies by id (CEO 2026-10-23), not free-text names
matched at read time -- where a typo silently moved money into "Group". New entries require both
companies; old entries were linked once by exact name (data migration intercompany_company_links)
and the ones no company matched raise a Finance task and can be linked from the screen."""
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.db_contract import _intercompany_company_links
from app.models.intercompany_ledger import IntercompanySettlement
from app.models.location import Location
from app.models.task import Task
from app.services import revenue_chain_service as chain
from app.services.goal_tree_service import company_bu_actuals
from tests.scope_fixtures import ApiClient, two_bu_world, uid


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
    world.us = Location(tenant_id=1, name=f"BX-US {uid()}")
    world.india = Location(tenant_id=1, name=f"BX-IN {uid()}")
    db.add_all([world.us, world.india])
    db.commit()
    return world


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _record(api, w, **kw):
    body = {"from_company_id": w.us.id, "to_company_id": w.india.id, "amount_usd_cents": 500_000,
            "settlement_date": "2026-09-15", "reason": "Offshore delivery", **kw}
    return api.post(w.org_user, "/api/v1/intercompany-settlements", json=body)


def test_a_new_entry_requires_real_companies_and_takes_their_names(db, w, api):
    res = _record(api, w)
    assert res.status_code == 201, res.text
    body = res.json()
    assert (body["from_company_id"], body["to_company_id"]) == (w.us.id, w.india.id)
    assert (body["from_entity"], body["to_entity"]) == (w.us.name, w.india.name)

    assert _record(api, w, to_company_id="no-such-company").status_code == 400
    assert _record(api, w, to_company_id=w.us.id).status_code == 400
    missing = api.post(w.org_user, "/api/v1/intercompany-settlements",
                       json={"from_entity": "BXUS", "to_entity": "BXIN", "amount_usd_cents": 1,
                             "settlement_date": "2026-09-15", "reason": "old shape"})
    assert missing.status_code == 422


def test_net_position_is_by_company(db, w, api):
    _record(api, w)
    _record(api, w, from_company_id=w.india.id, to_company_id=w.us.id, amount_usd_cents=200_000)
    india = api.get(w.org_user, f"/api/v1/intercompany-settlements/company/{w.india.id}/net-position").json()
    assert india == {"company_id": w.india.id, "entity": w.india.name, "net_position_usd_cents": 300_000}
    assert api.get(w.org_user, "/api/v1/intercompany-settlements/company/nope/net-position").status_code == 404


def test_company_pnl_and_goal_tree_attribute_by_id_even_after_a_rename(db, w, api):
    _record(api, w)
    w.india.name = "Renamed India entity"
    db.commit()
    pnl = chain.pnl(db, start=date(2026, 9, 1), end=date(2026, 9, 30), tenant_id=1)
    rows = {r["key"]: r for r in pnl["by_company"]}
    assert rows[w.india.id]["intercompany_revenue_usd_cents"] == 500_000
    assert rows[w.us.id]["intercompany_cost_usd_cents"] == 500_000
    actuals, intercompany = company_bu_actuals(db, 1, 2026)
    assert actuals[(w.india.id, None)]["revenue"] == 5_000
    assert intercompany >= 5_000


def test_old_entries_are_linked_by_exact_name_and_the_rest_raise_a_task(db, w):
    exact = IntercompanySettlement(tenant_id=1, from_entity=f"  {w.us.name.upper()} ", to_entity=w.india.name,
                                   amount_usd_cents=100, settlement_date=date(2026, 9, 1), reason="r")
    typo = IntercompanySettlement(tenant_id=1, from_entity=w.us.name, to_entity="BX-INDIA-TYPO",
                                  amount_usd_cents=200, settlement_date=date(2026, 9, 2), reason="r")
    db.add_all([exact, typo])
    db.flush()

    linked = _intercompany_company_links(db)
    assert linked >= 1
    assert (exact.from_company_id, exact.to_company_id) == (w.us.id, w.india.id)
    assert typo.from_company_id == w.us.id and typo.to_company_id is None
    task = db.query(Task).filter(Task.title.like("Link % intercompany entr%")).order_by(Task.id.desc()).first()
    assert task is not None and "BX-INDIA-TYPO" in task.description and task.link == "/pnl?view=operations"


def test_an_unlinked_entry_can_be_linked_once(db, w, api):
    old = IntercompanySettlement(tenant_id=1, from_entity="??", to_entity="??", amount_usd_cents=300,
                                 settlement_date=date(2026, 9, 3), reason="r")
    db.add(old)
    db.commit()
    url = f"/api/v1/intercompany-settlements/{old.id}/link-companies"
    res = api.post(w.org_user, url, json={"from_company_id": w.us.id, "to_company_id": w.india.id})
    assert res.status_code == 200 and res.json()["to_company_id"] == w.india.id
    again = api.post(w.org_user, url, json={"from_company_id": w.india.id, "to_company_id": w.us.id})
    assert again.status_code == 400  # a linked entry is never re-pointed
