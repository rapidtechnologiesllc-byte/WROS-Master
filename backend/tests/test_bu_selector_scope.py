"""Top-bar business unit selector (CEO 2026-11-02: "the BU selection here is wrong, it has to be
rolled up from user login ... me as the CEO shouldnt have any restriction but partner should only see
their BU stuff & P&L"). What it lists comes from the role template; picking a BU narrows every
screen to it, and a BU outside the user's scope never shows anything more."""
import pytest
from sqlalchemy.orm import Session

from tests.scope_fixtures import ApiClient, ids, two_bu_world

CLIENTS = "/api/v1/clients?active_only=false"


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


def _get(api, user, path, bu=None):
    headers = ApiClient.headers(user)
    if bu is not None:
        headers["X-Active-BU-Id"] = str(bu)
    return api.client.get(path, headers=headers)


def _client_ids(response):
    assert response.status_code == 200, response.text
    return {c["id"] for c in response.json()["clients"]}


def test_org_level_user_sees_every_bu_and_starts_unrestricted(w, api):
    body = _get(api, w.org_user, "/api/v1/bu-context/my-access").json()
    assert body["can_view_all_bus"] is True
    assert {w.bu_a.id, w.bu_b.id} <= {a["business_unit_id"] for a in body["access"]}
    assert body["active_business_unit_id"] is None
    assert {w.client_a.id, w.client_b.id} <= _client_ids(_get(api, w.org_user, CLIENTS))


def test_org_level_user_narrows_to_one_bu(w, api):
    seen = _client_ids(_get(api, w.org_user, CLIENTS, bu=w.bu_a.id))
    assert w.client_a.id in seen and w.client_b.id not in seen
    body = _get(api, w.org_user, "/api/v1/bu-context/my-access", bu=w.bu_a.id).json()
    assert body["active_business_unit_id"] == w.bu_a.id


def test_partner_lists_only_own_bu_with_role(w, api):
    body = _get(api, w.partner_a, "/api/v1/bu-context/my-access").json()
    assert body["can_view_all_bus"] is False
    assert [(a["business_unit_id"], a["roles"]) for a in body["access"]] == [(w.bu_a.id, ["Partner"])]


def test_partner_cannot_widen_with_another_bu(w, api):
    seen = _client_ids(_get(api, w.partner_a, CLIENTS, bu=w.bu_b.id))
    assert w.client_b.id not in seen and w.client_a.id in seen
    body = _get(api, w.partner_a, "/api/v1/bu-context/my-access", bu=w.bu_b.id).json()
    assert body["active_business_unit_id"] is None
    assert api.post(w.partner_a, "/api/v1/bu-context/switch",
                    json={"business_unit_id": w.bu_b.id}).status_code == 403
    assert api.post(w.partner_a, "/api/v1/bu-context/switch",
                    json={"business_unit_id": w.bu_a.id}).status_code == 200


def test_pnl_follows_the_selector(w, api):
    period = "?start=2026-08-01&end=2026-08-31&group_by=business_unit"
    org = _get(api, w.org_user, "/api/v1/revenue-chain/summary" + period, bu=w.bu_a.id)
    assert org.status_code == 200, org.text
    assert ids(org.json(), "key") <= {w.bu_a.id}
