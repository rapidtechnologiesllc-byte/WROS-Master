"""Delete on the Users & Access Control screens (2026-10-13). Every delete checks what still
points at the row from the database's own foreign keys (app.core.references): nothing ->
deleted; something -> 409 naming it (never a bare 500, nothing lost). A person with history
is deactivated instead: they can't sign in or use an existing token, and their records stay."""
import pytest
from sqlalchemy.orm import Session

from app.core.database import authenticate_user
from app.core.security import create_refresh_token, get_password_hash
from app.models.location import Location
from app.models.org_structure import OrgNode
from app.models.user import Users
from app.services.org_structure_service import create_org_node
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import ApiClient, person, two_bu_world, uid


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


@pytest.fixture
def world(db):
    w = two_bu_world(db)
    db.commit()
    return w


def test_a_business_unit_in_use_says_why_and_an_empty_one_goes(db, api, world):
    used = api.delete(world.org_user, f"/api/v1/rbac/business-units/{world.bu_a.id}")
    assert used.status_code == 409 and "1 job" in used.json()["detail"]

    from app.models.business_unit import BusinessUnit
    empty = BusinessUnit(tenant_id=1, name=f"BU-empty-{uid()}", display_name="Empty")
    db.add(empty)
    db.commit()
    assert api.delete(world.org_user, f"/api/v1/rbac/business-units/{empty.id}").status_code == 200


def test_a_person_with_history_is_deactivated_not_erased(db, api, world):
    from app.models.employee import Employee

    worker = person(db, world.partner_role, "Has history")
    worker.UserPassword = get_password_hash("Secret!123")
    from datetime import date
    db.add(Employee(first_name="H", last_name="H", email=f"{uid()}@emp.test", wros_user_id=worker.UserID,
                    tenant_id=1, joining_date=date.today()))
    db.commit()

    response = api.delete(world.org_user, f"/api/v1/hr/users/{worker.UserID}")
    assert response.status_code == 200 and response.json()["status"] == "Deactivated"
    db.expire_all()
    assert db.get(Users, worker.UserID).terminated_at is not None      # still there, history kept
    assert authenticate_user(db, worker.UserEmail, "Secret!123") is False  # can't sign in
    assert api.get(worker, "/api/v1/hr/me").status_code == 401           # existing token stops working
    listed = {u["user_id"]: u for u in api.get(world.org_user, "/api/v1/hr/users/all").json()["users"]}
    assert listed[worker.UserID]["active"] is False


def test_a_person_without_history_is_deleted(db, api, world):
    newcomer = person(db, world.partner_role, "No history")
    db.commit()
    response = api.delete(world.org_user, f"/api/v1/hr/users/{newcomer.UserID}")
    assert response.status_code == 200 and response.json()["status"] == "Success"
    db.expire_all()
    assert db.get(Users, newcomer.UserID) is None


def test_nobody_deletes_themselves_or_another_tenants_company(db, api, world):
    assert api.delete(world.org_user, f"/api/v1/hr/users/{world.org_user.UserID}").status_code == 400
    from app.models.tenant import Tenant
    if db.query(Tenant).filter_by(id=2).first() is None:
        db.add(Tenant(id=2, name="other-tenant"))
        db.flush()
    other = Location(tenant_id=2, name=f"Other co {uid()}")
    db.add(other)
    db.commit()
    assert api.delete(world.org_user, f"/api/v1/api/admin/users-access-control/delivery-centers/{other.id}").status_code == 404


def test_a_seat_with_reports_says_why(db, api, world):
    top = db.query(OrgNode).filter(OrgNode.tenant_id == 1, OrgNode.hierarchy_level == 17,
                                   OrgNode.active.is_(True)).first()         or create_org_node(db, tenant_id=1, name="CEO seat", hierarchy_level=17, specialization="General")
    boss = create_org_node(db, tenant_id=1, name=f"Boss {uid()}", hierarchy_level=16, specialization="General",
                           parent_id=top.id)
    create_org_node(db, tenant_id=1, name=f"Report {uid()}", hierarchy_level=14, specialization="General",
                    parent_id=boss.id)
    db.commit()
    response = api.delete(world.org_user, f"/api/v1/org/nodes/{boss.id}")
    assert response.status_code == 409 and "1 org node" in response.json()["detail"]
    assert db.get(OrgNode, boss.id) is not None


def test_refresh_finds_internal_users_by_id_and_refuses_deactivated_ones(db, api, world):
    user = world.org_user
    user.UserEmail = f"refresh-{uid()}@example.com"  # the login response validates the address
    db.commit()
    token = create_refresh_token({"sub": user.UserID, "type": "refresh"})
    ok = api.client.post("/api/v1/auth/v1/refresh", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200, ok.text

    from datetime import datetime
    user.terminated_at = datetime.utcnow()
    db.commit()
    refused = api.client.post("/api/v1/auth/v1/refresh", headers={"Authorization": f"Bearer {token}"})
    assert refused.status_code == 401


def test_a_function_add_on_records_its_function_and_a_role_set_cannot_take_one(db, api, world):
    import uuid

    from app.models.org_structure import Department

    admin = person(db, full_access_role(db), "Admin")
    if not db.query(Department).filter(Department.tenant_id == 1, Department.name == "Recruitment",
                                       Department.active.is_(True)).first():
        db.add(Department(id=str(uuid.uuid4()), tenant_id=1, name="Recruitment", active=True))  # a standard function
    db.commit()
    created = api.post(admin, "/api/v1/admin/role-templates", json={
        "name": f"Recruitment access {uid()}", "display_name": "Recruitment access",
        "specialization": "Recruitment", "permissions": []})
    assert created.status_code == 200, created.text
    detail = api.get(admin, f"/api/v1/admin/role-templates/{created.json()['id']}").json()
    assert detail["specialization"] == "Recruitment" and detail["owner_role"] is None
    assert api.post(admin, "/api/v1/admin/role-templates", json={
        "name": f"x {uid()}", "display_name": "x", "specialization": "Astrology", "permissions": []}).status_code == 422

    from app.models.org_structure import OrgRole
    from app.services.org_roles_service import ensure_permission_set
    role = OrgRole(tenant_id=1, name=f"Role {uid()}", hierarchy_level=5)
    db.add(role)
    db.flush()
    ensure_permission_set(db, role)
    db.commit()
    assert api.put(admin, f"/api/v1/admin/role-templates/{role.role_template_id}",
                   json={"specialization": "Recruitment", "permissions": []}).status_code == 400
