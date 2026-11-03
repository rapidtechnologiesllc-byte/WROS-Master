"""Manage Functions > Permissions (CEO 2026-11-03): each function shows and edits the access everyone in it
gets -- its add-on template, the same one the user form gives -- without changing how access works."""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.org_structure import Department
from app.models.role_template import RoleTemplate
from tests.scope_fixtures import ApiClient, two_bu_world


def uid():
    return uuid.uuid4().hex[:8]


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


def _function(db, name):
    dept = Department(id=str(uuid.uuid4()), tenant_id=1, name=name, active=True)
    db.add(dept)
    db.commit()
    return dept


def _listed(api, user, dept_id):
    return next(d for d in api.get(user, "/api/v1/org/departments").json() if d["id"] == dept_id)


def test_a_function_shows_its_access_and_one_without_gets_an_empty_one_once(db, api):
    world = two_bu_world(db)
    finance = _function(db, f"Finance {uid()}")
    db.add(RoleTemplate(tenant_id=1, name=f"Finance Manager {uid()}", display_name="Finance Manager",
                        specialization=finance.name, hierarchy_level=9, org_level_access=True))
    recruiting = _function(db, f"Recruitment {uid()}")
    db.commit()

    shown = _listed(api, world.org_user, finance.id)
    assert shown["access_template_name"].startswith("Finance Manager") and shown["access_org_level"] is True
    assert _listed(api, world.org_user, recruiting.id)["access_template_id"] is None

    for _ in range(2):  # idempotent
        created = api.post(world.org_user, f"/api/v1/org/departments/{recruiting.id}/access-template")
        assert created.status_code == 200, created.text
    template = db.query(RoleTemplate).filter_by(specialization=recruiting.name).one()
    assert template.id == created.json()["access_template_id"] and template.name == recruiting.name
    from app.models.role_template import RoleTemplatePermission
    assert db.query(RoleTemplatePermission).filter_by(role_template_id=template.id).count() == 0  # nobody gains access


def test_two_templates_for_one_function_are_reported_not_guessed(db, api):
    world = two_bu_world(db)
    sales = _function(db, f"Sales {uid()}")
    db.add_all([RoleTemplate(tenant_id=1, name=f"Sales A {uid()}", display_name="A", specialization=sales.name),
                RoleTemplate(tenant_id=1, name=f"Sales B {uid()}", display_name="B", specialization=sales.name)])
    db.commit()
    shown = _listed(api, world.org_user, sales.id)
    assert shown["access_template_id"] is None and "keep one" in shown["access_note"]
