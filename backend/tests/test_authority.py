"""Authority comes from the role template only (CEO rules, 2026-10-10/11): its permission
matrix (modules and resources), org_level_access, hierarchy level and specialization --
never a role name, the legacy UserRole string, or a super-user flag (a super admin sees
exactly what its role's permissions grant). Plus a static guard: every permission the code
checks names a seeded resource and a real action, so no check can silently match nothing."""
import ast
import pathlib
import uuid

import pytest
from sqlalchemy.orm import Session

from app.contracts.api_contract import MODULES_AND_RESOURCES
from app.core import authority
from app.models.role_template import RoleTemplate
from app.models.tenant import Tenant
from app.models.user import Users

APP = pathlib.Path(__file__).resolve().parent.parent / "app"
RESOURCES = {r for names in MODULES_AND_RESOURCES.values() for r in names}
ACTIONS = {"view", "create", "edit", "delete", "can_view", "can_create", "can_edit", "can_delete"}


def _uid():
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


def _user(db, *, name=None, level=5, super_user=False, org=False, specialization="General", enabled=True,
          legacy_role="Super User"):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    role = RoleTemplate(tenant_id=1, name=name or f"role-{_uid()}", display_name="R", hierarchy_level=level,
                        is_super_user=super_user, org_level_access=org, specialization=specialization,
                        enabled=enabled)
    db.add(role)
    db.flush()
    user = Users(UserID=f"U-{_uid()}", UserName="U", UserEmail=f"u{_uid()}@x.com", UserPassword="x",
                 UserRole=legacy_role, tenant_id=1, role_template_id=role.id, password_reset_required=False)
    db.add(user)
    db.flush()
    return user


def test_role_names_and_legacy_userrole_grant_nothing(db):
    impostor = _user(db, name=f"Super Admin {_uid()}", legacy_role="Super User")
    assert not authority.is_org_level(db, impostor)
    assert not authority.is_bu_leader(db, impostor) and not authority.has_permission(db, impostor, "invoices.create")


def test_the_super_user_flag_grants_nothing_only_permissions_do(db):
    from app.models.role_template import Module, Resource, RoleTemplatePermission

    flagged = _user(db, super_user=True)
    assert not authority.has_permission(db, flagged, "invoices.create") and not authority.is_org_level(db, flagged)
    resource = db.query(Resource).filter_by(tenant_id=1, name="invoices").first()
    if resource is None:
        module = Module(tenant_id=1, name=f"Finance-{_uid()}", display_name="Finance")
        db.add(module)
        db.flush()
        resource = Resource(tenant_id=1, module_id=module.id, name="invoices", display_name="Invoices")
        db.add(resource)
        db.flush()
    db.add(RoleTemplatePermission(role_template_id=flagged.role_template_id, resource_id=resource.id, tenant_id=1,
                                  can_view=True, can_create=True))
    db.flush()
    assert authority.has_permission(db, flagged, "invoices.create")
    assert not authority.has_permission(db, flagged, "invoices.delete")


def test_flags_and_levels_decide(db):
    assert authority.is_org_level(db, _user(db, org=True))
    head = _user(db, level=14)
    assert authority.is_bu_leader(db, head) and authority.is_revenue_bu_scoped(db, head)
    assert not authority.is_revenue_bu_scoped(db, _user(db, level=14, org=True))
    assert authority.is_partner(db, _user(db, level=16)) and not authority.is_partner(db, head)
    assert authority.requires_totp(db, head) and not authority.requires_totp(db, _user(db, level=9))


def test_finance_leader_is_finance_at_senior_manager_or_above(db):
    assert authority.is_finance_leader(db, _user(db, level=9, specialization="Finance"))
    assert not authority.is_finance_leader(db, _user(db, level=8, specialization="Finance"))
    assert not authority.is_finance_leader(db, _user(db, level=16, specialization="Recruitment"))
    assert not authority.is_finance_leader(db, _user(db, level=17, super_user=True))  # admins don't approve bills


def test_a_disabled_role_grants_nothing(db):
    user = _user(db, super_user=True, org=True, level=17, enabled=False)
    assert not authority.is_org_level(db, user) and authority.level(db, user) == 0


def test_malformed_permission_raises_instead_of_silently_denying(db):
    user = _user(db)
    for bad in ("admin.manage", "recruitment", "revenue.view_pnl"):
        with pytest.raises(ValueError):
            authority.has_permission(db, user, bad)


def _literal_strings(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def test_every_permission_the_code_checks_exists():
    """Static guard: a permission naming no seeded resource (or no real action) matches
    nobody, so the check silently denies -- or, worse, an `or` around it silently allows."""
    problems = []
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            where = f"{path.relative_to(APP.parent)}:{node.lineno}"
            if name in ("require_resource_permission", "require_role_template_permission") and node.args:
                resource = _literal_strings(node.args[0])
                action = _literal_strings(node.args[1]) if len(node.args) > 1 else ["view"]
                if resource and resource[0] not in RESOURCES:
                    problems.append(f"{where} unknown resource {resource[0]!r}")
                if action and action[0] not in ACTIONS:
                    problems.append(f"{where} unknown action {action[0]!r}")
            elif name in ("has_permission", "has_any_permission", "has_all_permissions"):
                for arg in node.args:
                    for value in _literal_strings(arg):
                        if "." not in value:
                            continue  # a user id or resource argument of the service-level API
                        resource, _, action = value.rpartition(".")
                        if resource not in RESOURCES or action not in ACTIONS:
                            problems.append(f"{where} bad permission {value!r}")
    assert not problems, "\n".join(problems)


def test_no_authority_by_role_name():
    """No code decides authority by comparing a role's name or the legacy UserRole."""
    offenders = []
    for path in APP.rglob("*.py"):
        if path.name in ("db_contract.py", "role_template_seed.py") or "models" in path.parts:
            continue  # seed data creates the roles by name; models hold column enums, not authority
        for lineno, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            code = line.split("#", 1)[0]
            if ("UserRole ==" in code or "UserRole in" in code or "UserRole.in_" in code
                    or ".UserRole not in" in code or "_ROLES = {" in code or "_ROLES = (" in code):
                offenders.append(f"{path.relative_to(APP.parent)}:{lineno}: {line.strip()}")
    assert not offenders, "\n".join(offenders)


def test_no_super_user_bypass_anywhere():
    """CEO 2026-10-11: a super admin is checked like everyone else -- by its permissions."""
    offenders = []
    for path in APP.rglob("*.py"):
        if "models" in path.parts or path.name in ("db_contract.py",) or path.name.startswith("architect_"):
            continue  # the column itself, its migration, and the architect's text patterns
        for lineno, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if "is_super_user" in line.split("#", 1)[0] or "is_super_admin" in line:
                offenders.append(f"{path.relative_to(APP.parent)}:{lineno}: {line.strip()}")
    assert not offenders, "\n".join(offenders)


def test_seed_gives_super_admin_and_admin_org_level_once_even_when_another_role_has_it(db):
    """Production 2026-10-11: the Finance Manager role is seeded with org_level_access, so
    the old "only while no role has it" guard never fired and Super Admin/Admin stayed
    BU-scoped. The seed now runs once per tenant (system_config marker) and never again."""
    from app.core.db_contract import _initialize_role_authority
    from app.models.system_config import SystemConfig

    tenant = Tenant(name=f"t-{_uid()}")
    db.add(tenant)
    db.flush()
    roles = {name: RoleTemplate(tenant_id=tenant.id, name=name, display_name=name, hierarchy_level=level,
                                org_level_access=org, enabled=True)
             for name, level, org in (("Super Admin", 5, False), ("Admin", 5, False), ("Finance Manager", 9, True))}
    db.add_all(roles.values())
    db.flush()

    _initialize_role_authority(db)
    for role in roles.values():
        db.refresh(role)
    assert roles["Super Admin"].org_level_access and roles["Admin"].org_level_access
    assert db.query(SystemConfig).filter_by(tenant_id=tenant.id, config_key="role_authority_seeded").count() == 1

    roles["Admin"].org_level_access = False  # an owner narrows Admin in the Role Templates editor
    db.commit()
    _initialize_role_authority(db)
    db.refresh(roles["Admin"])
    assert roles["Admin"].org_level_access is False


def _position(db, name, code, rank):
    from app.models.org_structure import OrgPosition

    pos = db.query(OrgPosition).filter_by(name=name).first()
    if pos is None:
        pos = OrgPosition(name=name, rank=rank, rbac_role_name=code)
        db.add(pos)
        db.flush()
    return pos


def _person(db, role, job_title):
    user = Users(UserID=f"U-{_uid()}", UserName="Home", UserEmail=f"{_uid()}@x.com", UserPassword="x",
                 UserRole="x", tenant_id=1, role_template_id=role.id, job_title=job_title)
    db.add(user)
    db.flush()
    return user


def _roles(db):
    """The managed roles the tests rely on (seeded by db_contract in a real database)."""
    from app.models.org_structure import OrgRole

    for name, level, designation in (("CFO", 16, "cfo"), ("Vice President", 14, None)):
        if not db.query(OrgRole).filter_by(tenant_id=1, name=name).first():
            db.add(OrgRole(tenant_id=1, name=name, hierarchy_level=level, designation=designation))
    db.flush()


def _make_head(db, user):
    from app.models.business_unit import BusinessUnit, BusinessUnitLocationHead
    from app.models.location import Location

    unit, company = BusinessUnit(name=f"bu-{_uid()}", display_name="BU"), Location(tenant_id=1, name=f"co-{_uid()}")
    db.add_all([unit, company])
    db.flush()
    db.add(BusinessUnitLocationHead(business_unit_id=unit.id, company_id=company.id, head_user_id=user.UserID))
    db.flush()


@pytest.mark.parametrize("job_title,template_level,heads_bu,expected", [
    ("CEO", 5, False, "ceo"),                       # CEO on a level-5 Super Admin template (production)
    ("Senior Consultant", 5, False, "default"),     # admin template holding every permission
    ("Senior Consultant", 17, False, "default"),    # template level never picks the dashboard
    ("Partner", 5, False, "partner"),
    ("CFO", 5, False, "cfo"),                       # CFO is the role's designation, not a department
    ("BU Head", 5, True, "bu_head"),
    ("BU Head", 5, False, "default"),               # the BU Head home needs an actual BU to head
    ("Vice President", 5, True, "bu_head"),         # managed role at a BU-head level who heads a BU
    ("", 5, False, "default"),
])
def test_home_dashboard_follows_the_role_position_not_the_template(db, job_title, template_level,
                                                                      heads_bu, expected):
    """CEO 2026-10-12: the dashboard is role driven (the position the Job Title names), while
    authority is template driven. An Admin template with every permission landed on the CEO
    dashboard, then the CEO (job title CEO, Super Admin template) landed on the general one."""
    from tests.hiring_fixtures import full_access_role

    for name, code, rank in (("CEO", "ceo", 0), ("Partner", "partner", 1), ("BU Head", "bu_head", 2),
                             ("Senior Consultant", "senior_consultant", 9)):
        _position(db, name, code, rank)
    _roles(db)
    role = full_access_role(db)
    role.hierarchy_level = template_level
    user = _person(db, role, job_title)
    if heads_bu:
        _make_head(db, user)
    assert authority.home_dashboard(db, user) == expected
    assert authority.summary(db, user)["home_dashboard"] == expected


def test_home_dashboard_still_needs_the_dashboard_permission(db):
    """A CEO position whose template cannot view the CEO dashboard gets the general one."""
    _position(db, "CEO", "ceo", 0)
    role = RoleTemplate(tenant_id=1, name=f"noperm-{_uid()}", display_name="R", hierarchy_level=5,
                        org_level_access=True, enabled=True)
    db.add(role)
    db.flush()
    assert authority.home_dashboard(db, _person(db, role, "CEO")) == "default"
