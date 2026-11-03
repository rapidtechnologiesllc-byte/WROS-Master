"""Retiring the legacy function add-ons (CEO 2026-11-03: "remove five" -- Manager, User and Ops held every
permission under "basic access" names; Partner and BU Head duplicated the job-title roles). Nobody's
access changes, except that someone still on a retired full-access add-on moves to Employee."""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.core.db_contract import LEADERSHIP_ROLES, RETIRED_TEMPLATES, _retire_legacy_role_templates, ensure_role
from app.models.org_structure import OrgRole
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.role_template_permission_service import RoleTemplatePermissionService, invalidate_permissions


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


def _template(db, name, resources, *, system=False):
    template = RoleTemplate(tenant_id=1, name=name, display_name=name, hierarchy_level=4, is_system=system)
    db.add(template)
    db.flush()
    db.add_all(RoleTemplatePermission(role_template_id=template.id, resource_id=r.id, tenant_id=1, can_view=True,
                                      can_create=True, can_edit=True, can_delete=False) for r in resources)
    db.flush()
    return template


def _user(db, name, template, job_title=None):
    user = Users(UserID=f"U-{uid()}", UserName=name, UserEmail=f"{name.lower()}{uid()}@blitzenx.com", UserPassword="h",
                 UserRole="x", tenant_id=1, role_template_id=template.id, job_title=job_title)
    db.add(user)
    db.flush()
    return user


def _perms(db, user):
    invalidate_permissions()
    return RoleTemplatePermissionService.get_user_permissions(db, user.UserID, 1)


def test_the_five_go_and_nobody_elses_access_changes(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    module = Module(name=f"mod-{uid()}", display_name="M", tenant_id=1)
    db.add(module)
    db.flush()
    resources = [Resource(module_id=module.id, name=f"res-{uid()}", display_name="R", enabled=True, tenant_id=1)
                 for _ in range(4)]
    db.add_all(resources)
    db.flush()
    ensure_role(db, "Employee", {**LEADERSHIP_ROLES["Employee"], "permissions": {}}, 1)
    retired_ids = [_template(db, name, resources, system=name in ("Manager", "User", "Ops")).id
                   for name in RETIRED_TEMPLATES]  # what a long-running database still has
    # the Partner job-title role keeps its own permission set; a partner holds that role + the Sales add-on
    partner_set = _template(db, f"Partner (role) {uid()}", resources[:1])
    db.add(OrgRole(tenant_id=1, name=f"Partner {uid()}", hierarchy_level=16, role_template_id=partner_set.id))
    sales = _template(db, f"Sales {uid()}", resources[1:2])
    partner = _user(db, "Partner", sales)
    on_user_template = _user(db, "Legacy", db.get(RoleTemplate, retired_ids[RETIRED_TEMPLATES.index("User")]))
    db.commit()
    before = _perms(db, partner)

    _retire_legacy_role_templates(db)
    _retire_legacy_role_templates(db)  # idempotent

    assert db.query(RoleTemplate).filter(RoleTemplate.id.in_(retired_ids)).count() == 0
    assert db.get(RoleTemplate, partner_set.id) is not None  # a job-title role's set is never touched
    assert _perms(db, partner) == before  # nobody else's access changes
    db.refresh(on_user_template)
    employee_ids = {t.id for t in db.query(RoleTemplate).filter_by(name="Employee", tenant_id=1)}
    assert on_user_template.role_template_id in employee_ids  # off the full-access template, never more access


def test_startup_no_longer_creates_them():
    assert not set(RETIRED_TEMPLATES) & set(LEADERSHIP_ROLES)


def test_job_title_permission_sets_are_named_after_the_role(db):
    """CEO 2026-11-03: "update the names by removing the (role)"."""
    from app.core.db_contract import _initialize_manage_role_permission_sets

    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    name = f"Director {uid()}"
    old = RoleTemplate(tenant_id=1, name=f"{name} (role)", display_name=name, hierarchy_level=11)
    db.add(old)
    db.flush()
    role = OrgRole(tenant_id=1, name=name, hierarchy_level=11, role_template_id=old.id)
    fresh = OrgRole(tenant_id=1, name=f"Associate {uid()}", hierarchy_level=2)
    db.add_all([role, fresh])
    db.commit()
    _initialize_manage_role_permission_sets(db)
    assert db.get(RoleTemplate, old.id).name == name  # same set, same permissions, plain name
    db.refresh(fresh)
    assert db.get(RoleTemplate, fresh.role_template_id).name == fresh.name
