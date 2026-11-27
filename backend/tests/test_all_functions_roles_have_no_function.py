"""CEO 2026-11-05: from L15 (CEO, Partner, SVP) a person has no function; access is driven by their role. CEO
2026-11-27 found the CEO listed with a "Recruiter" add-on. The rule is enforced on every save, and the one-time
repair moves existing people without ever changing what they may do."""
from app.core.db_contract import _all_functions_roles_drop_function_addon
from app.models.org_structure import OrgRole
from app.models.role_template import Module, Resource, RoleTemplatePermission
from app.services.org_roles_service import align_all_functions_addon
from app.services.role_template_permission_service import RoleTemplatePermissionService
from tests import factories as f

import random

TENANT = 1  # replaced per test by a fresh tenant (role names are unique per tenant)


import pytest


@pytest.fixture(autouse=True)
def _own_tenant(db):
    global TENANT
    TENANT = random.randint(10_000, 2_000_000_000)
    f.tenant(db, TENANT)
    yield


def _resource(db, name):
    module = Module(name=f"m-{f.uid()}", display_name="M", enabled=True, tenant_id=TENANT)
    db.add(module)
    db.flush()
    resource = Resource(module_id=module.id, name=name, display_name=name, enabled=True, tenant_id=TENANT)
    db.add(resource)
    db.flush()
    return resource


def _grant(db, template, resource):
    db.add(RoleTemplatePermission(role_template_id=template.id, resource_id=resource.id, tenant_id=TENANT,
                                  can_view=True, can_edit=True))
    db.flush()


def _setup(db, *, title="CEO", level=17, designation="ceo"):
    employee = f.role(db, TENANT, name="Employee")
    recruiter = f.role(db, TENANT, name=f"Recruiter-{f.uid()}", specialization="Recruitment")
    role_set = f.role(db, TENANT, name=f"{title} set {f.uid()}", hierarchy_level=level)
    org_role = OrgRole(tenant_id=TENANT, name=title, hierarchy_level=level, designation=designation,
                       active=True, role_template_id=role_set.id)
    db.add(org_role)
    db.flush()
    return employee, recruiter, role_set, org_role


def _access(db, user):
    perms = RoleTemplatePermissionService._fetch_user_permissions_internal(db, user.UserID, user.tenant_id)
    return {(r, k) for r, flags in perms.items() for k, v in flags.items() if k.startswith("can_") and v is True}


def test_an_l15_plus_person_gets_the_no_function_addon(db):
    employee, recruiter, _, _ = _setup(db)
    ceo = f.user(db, TENANT, job_title="CEO", role_template_id=recruiter.id)
    assert align_all_functions_addon(db, ceo) is True
    assert ceo.role_template_id == employee.id and ceo.department_id is None
    assert align_all_functions_addon(db, ceo) is False  # nothing left to change


def test_below_l15_keeps_their_function(db):
    _, recruiter, _, _ = _setup(db, title="Manager", level=8, designation=None)
    manager = f.user(db, TENANT, job_title="Manager", role_template_id=recruiter.id)
    assert align_all_functions_addon(db, manager) is False
    assert manager.role_template_id == recruiter.id


def test_repair_moves_the_sole_holder_with_identical_access(db):
    employee, recruiter, role_set, _ = _setup(db)
    _grant(db, recruiter, _resource(db, f"res-{f.uid()}"))
    ceo = f.user(db, TENANT, job_title="CEO", role_template_id=recruiter.id)
    before = _access(db, ceo)

    assert _all_functions_roles_drop_function_addon(db) == 1

    db.expire_all()
    assert ceo.role_template_id == employee.id
    assert _access(db, ceo) == before  # now carried by the CEO role's own permission set
    assert db.query(RoleTemplatePermission).filter(RoleTemplatePermission.role_template_id == role_set.id).count() == 1


def test_repair_leaves_a_shared_role_alone_rather_than_widen_access(db):
    _, recruiter, role_set, _ = _setup(db, title="Partner", level=16, designation=None)
    _grant(db, recruiter, _resource(db, f"res-{f.uid()}"))
    first = f.user(db, TENANT, job_title="Partner", role_template_id=recruiter.id)
    f.user(db, TENANT, job_title="Partner", role_template_id=recruiter.id)

    assert _all_functions_roles_drop_function_addon(db) == 0

    db.expire_all()
    assert first.role_template_id == recruiter.id
    assert db.query(RoleTemplatePermission).filter(RoleTemplatePermission.role_template_id == role_set.id).count() == 0


def test_repair_carries_org_wide_visibility_for_a_sole_holder(db):
    from app.core import authority

    employee, recruiter, role_set, _ = _setup(db)
    recruiter.org_level_access = True
    ceo = f.user(db, TENANT, job_title="CEO", role_template_id=recruiter.id)
    assert authority.is_org_level(db, ceo)

    assert _all_functions_roles_drop_function_addon(db) == 1

    db.expire_all()
    db.info.pop("authority_cache", None)
    assert ceo.role_template_id == employee.id and role_set.org_level_access is True
    assert authority.is_org_level(db, ceo)


def test_repair_never_drops_org_wide_visibility_on_a_shared_role(db):
    _, recruiter, role_set, _ = _setup(db, title="Partner", level=16, designation=None)
    recruiter.org_level_access = True
    partner = f.user(db, TENANT, job_title="Partner", role_template_id=recruiter.id)
    f.user(db, TENANT, job_title="Partner", role_template_id=recruiter.id)

    assert _all_functions_roles_drop_function_addon(db) == 0
    db.expire_all()
    assert partner.role_template_id == recruiter.id and not role_set.org_level_access
