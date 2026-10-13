"""Sales identifies an opportunity (CEO 2026-10-12: "the opportunity starts with the sales
team identifying an opportunity -- this itself is not working"). Opportunities are gated by
the opportunities permission, never by the P&L permission (revenue); the Client Owner list
exists; what is sold is kept; unknown fields are refused instead of silently dropped."""
import pytest
from sqlalchemy.orm import Session

from app.models.role_template import Resource, RoleTemplatePermission
from tests.scope_fixtures import ApiClient, person, scoped_role, two_bu_world


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
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _without(db, role, *resource_names):
    """The role with every action on these resources revoked."""
    ids = [r for (r,) in db.query(Resource.id).filter(Resource.name.in_(resource_names))]
    db.query(RoleTemplatePermission).filter(RoleTemplatePermission.role_template_id == role.id,
                                            RoleTemplatePermission.resource_id.in_(ids)) \
        .update({RoleTemplatePermission.can_view: False, RoleTemplatePermission.can_create: False,
                 RoleTemplatePermission.can_edit: False, RoleTemplatePermission.can_delete: False},
                synchronize_session=False)
    db.flush()
    return role


@pytest.fixture
def world(db):
    w = two_bu_world(db)
    w.seller = person(db, _without(db, scoped_role(db), "revenue"), "Seller", business_unit_id=w.bu_a.id)
    w.bu_a.partner_user_id = w.partner_a.UserID
    w.seller_bu = w.bu_a
    w.accountant = person(db, _without(db, scoped_role(db), "opportunities", "pipeline-management"), "Accountant")
    db.commit()
    return w


def _body(w, **extra):
    return {"client_id": w.client_a.id, "revenue_value_usd_cents": 50_000_00, **extra}


def test_client_owners_route_is_not_swallowed_by_the_opportunity_route(api, world):
    response = api.get(world.seller, "/api/v1/opportunities/client-owners")
    assert response.status_code == 200, response.text
    users = response.json()["users"]
    me = [u for u in users if u["is_current_user"]]
    assert me and me[0]["id"] == world.seller.UserID
    assert world.accountant.UserID not in {u["id"] for u in users}  # cannot sell


def test_seller_without_revenue_creates_lists_and_sees_the_board(api, world):
    created = api.post(world.seller, "/api/v1/opportunities", json=_body(
        world, service="Implementation", guidewire_module="PolicyCenter", client_type="Carrier",
        pricing_model="T&M"))
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["client_owner_id"] == world.seller.UserID           # defaults to the caller
    assert item["client_owner_name"] == "Seller"
    assert (item["service"], item["guidewire_module"]) == ("Implementation", "PolicyCenter")
    listed = api.get(world.seller, "/api/v1/opportunities").json()["opportunities"]
    assert item["id"] in {o["id"] for o in listed}
    assert api.get(world.seller, "/api/v1/opportunities/pipeline").status_code == 200


def test_revenue_alone_does_not_open_opportunities(api, world):
    assert api.get(world.accountant, "/api/v1/opportunities").status_code == 403
    assert api.post(world.accountant, "/api/v1/opportunities", json=_body(world)).status_code == 403


def test_unknown_fields_are_refused_not_dropped(api, world):
    response = api.post(world.seller, "/api/v1/opportunities", json=_body(world, account_manager_id="x"))
    assert response.status_code == 422


def test_client_owner_must_be_someone_who_can_sell(api, world):
    response = api.post(world.seller, "/api/v1/opportunities",
                        json=_body(world, client_owner_id=world.accountant.UserID))
    assert response.status_code == 422 and "Client Owner" in response.json()["detail"]


def test_seller_cannot_open_an_opportunity_for_another_business_units_client(api, world):
    response = api.post(world.seller, "/api/v1/opportunities",
                        json={"client_id": world.client_b.id, "revenue_value_usd_cents": 1000})
    assert response.status_code in (403, 404)


def test_pipeline_access_seed_preserves_and_opens_access_once(db):
    """Startup grant, by permission: a role that saw revenue keeps the pipeline; a role that
    may view opportunities may view the board. Runs once: a later revoke stays revoked."""
    from app.core.db_contract import _initialize_pipeline_access
    from app.models.system_config import SystemConfig

    finance = _without(db, scoped_role(db), "opportunities", "pipeline-management")
    sales = _without(db, scoped_role(db), "pipeline-management", "revenue")
    db.query(SystemConfig).filter(SystemConfig.config_key == "pipeline_access_seeded").delete()
    db.flush()

    def can_view(role, name):
        return db.query(RoleTemplatePermission.can_view).join(
            Resource, Resource.id == RoleTemplatePermission.resource_id).filter(
            RoleTemplatePermission.role_template_id == role.id, Resource.name == name).scalar()

    _initialize_pipeline_access(db)
    assert can_view(finance, "opportunities") and can_view(finance, "pipeline-management")
    assert can_view(sales, "pipeline-management")

    _without(db, sales, "pipeline-management")  # an admin revokes it afterwards
    _initialize_pipeline_access(db)              # next startup
    assert not can_view(sales, "pipeline-management")
