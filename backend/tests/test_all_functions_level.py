"""CEO 2026-11-05: at L15, L16 and L17 a person has no function: they answer for all of them."""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnitCompany
from app.models.location import Location
from app.models.org_structure import Department, OrgRole
from app.models.role_template import RoleTemplate
from app.models.user import Users
from app.services import account_activation_service as activation
from tests.scope_fixtures import ApiClient, two_bu_world


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
def api(db, monkeypatch):
    monkeypatch.setattr(activation, "queue_account_email", lambda user, purpose="ACTIVATE", once_key=None: True)
    client = ApiClient(db)
    yield client
    client.close()


def _role(db, name, level):
    role = db.query(OrgRole).filter_by(tenant_id=1, name=name).first()
    if role is None:
        role = OrgRole(tenant_id=1, name=name, hierarchy_level=level, active=True)
        db.add(role)
    role.hierarchy_level = level
    db.flush()
    return role


def _add(api, db, w, title):
    if not db.query(RoleTemplate).filter_by(tenant_id=1, name="Employee").first():
        db.add(RoleTemplate(tenant_id=1, name="Employee", display_name="Employee", hierarchy_level=2))
    department = Department(id=str(uuid.uuid4()), tenant_id=1, name=f"Sales {uuid.uuid4().hex[:4]}", active=True)
    company = Location(tenant_id=1, name=f"BX-US-{uuid.uuid4().hex[:6]}", country="US")
    db.add_all([department, company])
    db.flush()
    db.add(BusinessUnitCompany(tenant_id=1, business_unit_id=w.bu_a.id, company_id=company.id))
    db.commit()
    email = f"p{uuid.uuid4().hex[:8]}@example.com"
    done = api.post(w.org_user, "/api/v1/employees", json={
        "company_id": company.id, "first_name": "Asha", "last_name": "Rao", "email": email, "joining_date": "2026-01-05", "business_unit_id": w.bu_a.id,
        "billable": False, "pay_amount_cents": 12000000, "pay_currency": "USD", "pay_basis": "ANNUAL", "department_id": department.id, "current_title": title})
    assert done.status_code in (200, 201), done.text
    db.expire_all()
    return db.query(Users).filter(Users.UserEmail == email).one(), department


def test_a_partner_has_no_function_of_their_own(api, db, w):
    _role(db, "Test Partner", 16)
    user, _ = _add(api, db, w, "Test Partner")
    assert user.department_id is None


def test_a_chief_of_one_function_keeps_it(db):
    from app.services.org_roles_service import answers_for_all_functions

    assert answers_for_all_functions(OrgRole(hierarchy_level=16, designation="cfo")) is False
    assert answers_for_all_functions(OrgRole(hierarchy_level=17, designation="ceo")) is True
    assert answers_for_all_functions(OrgRole(hierarchy_level=16)) is True


def test_below_that_level_the_function_stays(api, db, w):
    _role(db, "Test Lead", 10)
    user, department = _add(api, db, w, "Test Lead")
    assert user.department_id == department.id


def test_the_forms_are_told_which_roles_have_no_function(api, db, w):
    _role(db, "Test L15", 15)
    _role(db, "Test L14", 14)
    roles = {r["name"]: r for r in api.get(w.org_user, "/api/v1/org/roles").json()}
    assert roles["Test L15"]["all_functions"] is True and roles["Test L14"]["all_functions"] is False
    form = {r["name"]: r for r in api.get(w.org_user, "/api/v1/employees/import/template").json()["org_roles"]}
    assert form["Test L15"]["all_functions"] is True and form["Test L14"]["all_functions"] is False
