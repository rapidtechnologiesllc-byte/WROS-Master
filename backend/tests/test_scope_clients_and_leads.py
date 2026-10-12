"""Business-unit visibility, slice 1: clients, client contacts and opportunities (leads).
Partner A must never see or touch BU B's records; unassigned prospects stay visible to all;
org-level users see everything (CEO 2026-10-12)."""
import pytest
from sqlalchemy.orm import Session

from tests.scope_fixtures import ApiClient, ids, two_bu_world


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


def test_client_list_shows_own_bu_and_unassigned_only(w, api):
    mine = ids(api.get(w.partner_a, "/api/v1/clients").json())
    assert w.client_a.id in mine and w.prospect.id in mine
    assert w.client_b.id not in mine
    everything = ids(api.get(w.org_user, "/api/v1/clients").json())
    assert {w.client_a.id, w.client_b.id, w.prospect.id} <= everything


def test_other_bus_client_is_not_found(w, api):
    assert api.get(w.partner_a, f"/api/v1/clients/{w.client_b.id}").status_code == 404
    assert api.get(w.partner_a, f"/api/v1/clients/{w.client_b.id}/contacts").status_code == 404
    assert api.get(w.partner_a, f"/api/v1/clients/{w.client_a.id}").status_code == 200


def test_cannot_edit_or_take_another_bus_client(w, api):
    assert api.patch(w.partner_a, f"/api/v1/clients/{w.client_b.id}", json={"industry": "x"}).status_code == 404
    moved = api.patch(w.partner_a, f"/api/v1/clients/{w.client_a.id}", json={"business_unit_id": w.bu_b.id})
    assert moved.status_code in (403, 422)


def test_opportunities_follow_their_client(db, w, api):
    from app.models.opportunity import Opportunity

    opp_a = Opportunity(tenant_id=1, client_id=w.client_a.id, revenue_value_usd_cents=100000)
    opp_b = Opportunity(tenant_id=1, client_id=w.client_b.id, revenue_value_usd_cents=100000)
    db.add_all([opp_a, opp_b])
    db.commit()
    listed = ids(api.get(w.partner_a, "/api/v1/opportunities").json())
    assert opp_a.id in listed and opp_b.id not in listed
    assert api.get(w.partner_a, f"/api/v1/opportunities/{opp_b.id}").status_code == 404
    assert api.get(w.partner_a, f"/api/v1/opportunities/{opp_b.id}/revenue-rollup").status_code == 404
