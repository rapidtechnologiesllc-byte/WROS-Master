"""The access model (CEO 2026-10-13): what a person may do =
    the Manage Role their Job Title names (its permission set, org_roles.role_template_id)
  U their function add-on (users.role_template_id)
  then personal overrides.
Their level is the Manage Role's. A new role's permission set starts empty, so giving
someone a role never widens their access by itself; every layer (API checks, menu,
authority, pickers) reads the same union."""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.core import authority
from app.core.visibility import is_org_level_user
from app.models.org_structure import OrgRole
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.models.user import UserCustomPermission, Users
from app.services.org_roles_service import ensure_permission_set
from app.services.role_template_permission_service import (RoleTemplatePermissionService as Perms,
                                                           validate_addon_template)
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import ApiClient


def uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    full_access_role(session)  # makes sure the contract's resources exist in tenant 1
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def fresh_cache():
    from app.services.role_template_permission_service import invalidate_permissions
    invalidate_permissions()
    yield
    invalidate_permissions()


def resource(db, name):
    return Perms.get_resource_by_name(db, name, 1)


def template(db, grants=(), *, level=5, specialization="General", org=False):
    t = RoleTemplate(tenant_id=1, name=f"t-{uid()}", display_name="T", hierarchy_level=level,
                     specialization=specialization, org_level_access=org, enabled=True)
    db.add(t)
    db.flush()
    for name, flags in dict(grants).items():
        db.add(RoleTemplatePermission(role_template_id=t.id, resource_id=resource(db, name).id, tenant_id=1,
                                      **{f"can_{a}": True for a in flags}))
    db.flush()
    return t


def manage_role(db, level, grants=(), org=False):
    role = OrgRole(tenant_id=1, name=f"Role {uid()}", hierarchy_level=level)
    db.add(role)
    db.flush()
    role_set = ensure_permission_set(db, role)
    role_set.org_level_access = org
    for name, flags in dict(grants).items():
        db.add(RoleTemplatePermission(role_template_id=role_set.id, resource_id=resource(db, name).id, tenant_id=1,
                                      **{f"can_{a}": True for a in flags}))
    db.flush()
    return role


def person(db, addon, title=None):
    u = Users(UserID=f"U-{uid()}", UserName="P", UserEmail=f"{uid()}@access.test", UserPassword="x",
              UserRole="x", tenant_id=1, role_template_id=addon.id, job_title=title)
    db.add(u)
    db.flush()
    return u


def test_a_new_role_starts_empty_so_taking_it_changes_nothing(db):
    addon = template(db, {"candidates": ("view", "edit")})
    user = person(db, addon)
    before = Perms._fetch_user_permissions_internal(db, user.UserID, 1)
    role = manage_role(db, 8)
    assert db.query(RoleTemplatePermission).filter_by(role_template_id=role.role_template_id).count() == 0
    user.job_title = role.name
    db.flush()
    assert Perms._fetch_user_permissions_internal(db, user.UserID, 1) == before


def test_access_is_the_role_set_united_with_the_add_on(db):
    addon = template(db, {"candidates": ("view",)})
    role = manage_role(db, 8, {"jobs": ("view", "create")})
    user = person(db, addon, role.name)
    assert Perms.has_permission(db, user.UserID, "jobs", "create", 1)       # from the role
    assert Perms.has_permission(db, user.UserID, "candidates", "view", 1)   # from the add-on
    assert not Perms.has_permission(db, user.UserID, "jobs", "delete", 1)
    menu = Perms._fetch_user_permissions_internal(db, user.UserID, 1)
    assert menu["jobs"]["can_create"] and menu["candidates"]["can_view"]

    user.job_title = None  # leaves the role: its set goes with it
    db.flush()
    assert not Perms.has_permission(db, user.UserID, "jobs", "view", 1)


def test_an_override_restricts_or_grants_and_the_menu_agrees_with_the_check(db):
    addon = template(db, {"candidates": ("view",)})
    user = person(db, addon)
    db.add_all([
        UserCustomPermission(user_id=user.UserID, resource_id=resource(db, "candidates").id, can_view=False),
        UserCustomPermission(user_id=user.UserID, resource_id=resource(db, "invoices").id, can_view=True),
    ])
    db.flush()
    menu = Perms._fetch_user_permissions_internal(db, user.UserID, 1)
    assert not Perms.has_permission(db, user.UserID, "candidates", "view", 1)
    assert Perms.has_permission(db, user.UserID, "invoices", "view", 1)
    assert menu["invoices"]["can_view"] and menu["invoices"]["overridden"]  # grant-only override is listed
    assert not menu["candidates"]["can_view"]


def test_level_comes_from_the_role_and_totp_never_drops(db):
    head = person(db, template(db, level=5), manage_role(db, 14).name)
    assert authority.level(db, head) == 14 and authority.is_bu_leader(db, head)

    # A senior add-on keeps its second factor even under a junior title
    senior_addon = person(db, template(db, level=15), manage_role(db, 4).name)
    assert authority.level(db, senior_addon) == 4
    assert authority.requires_totp(db, senior_addon)

    untitled = person(db, template(db, level=6))
    assert authority.level(db, untitled) == 6

    disabled = template(db, level=9)
    disabled.enabled = False
    assert authority.level(db, person(db, disabled, manage_role(db, 12).name)) == 0  # fails closed


def test_org_level_and_function_come_from_either_template(db):
    user = person(db, template(db), manage_role(db, 17, org=True).name)
    assert authority.is_org_level(db, user) and is_org_level_user(user)

    finance = person(db, template(db, specialization="Finance"), manage_role(db, 9).name)
    assert authority.in_finance(db, finance) and authority.is_finance_leader(db, finance)


def test_invoice_approvers_follow_the_role_level(db):
    from app.services.invoice_service import invoice_approvers

    approver = person(db, template(db, {"invoices": ("view", "edit")}, specialization="Finance"),
                      manage_role(db, 9).name)
    junior = person(db, template(db, {"invoices": ("view", "edit")}, specialization="Finance"),
                    manage_role(db, 6).name)
    ids = {u.UserID for u in invoice_approvers(db, 1)}
    assert approver.UserID in ids and junior.UserID not in ids


def test_a_grant_on_a_legacy_duplicate_resource_moves_to_the_canonical_one(db):
    from app.core.db_contract import _initialize_canonical_resources

    legacy_module = Module(tenant_id=1, name=f"legacy_{uid()}", display_name="Legacy")
    db.add(legacy_module)
    db.flush()
    dup = Resource(tenant_id=1, module_id=legacy_module.id, name="candidates", display_name="Candidates (old)")
    db.add(dup)
    db.flush()
    addon = template(db)
    db.add(RoleTemplatePermission(role_template_id=addon.id, resource_id=dup.id, tenant_id=1, can_view=True))
    user = person(db, addon)
    db.flush()
    assert resource(db, "candidates").id != dup.id                      # the contract row is canonical
    assert not Perms.has_permission(db, user.UserID, "candidates", "view", 1)  # the old grant never counted

    _initialize_canonical_resources(db)
    db.expire_all()
    assert Perms.has_permission(db, user.UserID, "candidates", "view", 1)
    assert db.get(Resource, dup.id).enabled is False                    # disabled, not deleted


def test_an_add_on_must_be_an_enabled_function_template_of_the_tenant(db):
    role = manage_role(db, 8)
    with pytest.raises(ValueError, match="permission set"):
        validate_addon_template(db, role.role_template_id, 1)
    with pytest.raises(ValueError, match="not found"):
        validate_addon_template(db, template(db).id, 2)
    off = template(db)
    off.enabled = False
    with pytest.raises(ValueError, match="disabled"):
        validate_addon_template(db, off.id, 1)


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def test_a_role_set_cannot_be_deleted_or_disabled_and_nobody_edits_their_own_access(db, api):
    admin = person(db, full_access_role(db))
    role = manage_role(db, 8)
    db.commit()
    assert api.delete(admin, f"/api/v1/admin/role-templates/{role.role_template_id}").status_code == 400
    toggled = api.post(admin, f"/api/v1/admin/role-templates/{role.role_template_id}/toggle-status",
                       json={"is_active": False})
    assert toggled.status_code == 400

    own = api.put(admin, f"/api/v1/hr/users/{admin.UserID}", json={"job_title": role.name})
    assert own.status_code == 403
    other = person(db, template(db))
    db.commit()
    assert api.put(admin, f"/api/v1/hr/users/{other.UserID}", json={"job_title": role.name}).status_code == 200
    assert api.put(admin, f"/api/v1/hr/users/{other.UserID}",
                   json={"role_template_id": role.role_template_id}).status_code == 422


def test_changing_a_role_set_needs_manage_roles_rights_and_writes_the_tenant(db, api):
    editor = person(db, template(db, {"role-templates": ("view", "edit")}))
    admin = person(db, full_access_role(db))
    role = manage_role(db, 8)
    db.commit()
    body = {"resource_name": "jobs", "action": "view"}
    url = f"/api/v1/admin/role-templates/{role.role_template_id}/grant-permission"
    assert api.post(editor, url, json=body).status_code == 403   # role-templates edit alone is not enough
    assert api.post(admin, url, json=body).status_code == 200
    row = db.query(RoleTemplatePermission).filter_by(role_template_id=role.role_template_id,
                                                     resource_id=resource(db, "jobs").id).one()
    assert row.tenant_id == 1 and row.can_view
