"""Who may do what -- decided ONLY by role templates and Manage Roles (CEO rules 2026-10-10,
2026-10-13), never by a name string:

  permissions                      the Manage Role's permission set U the function add-on
                                   (users.role_template_id) U personal overrides --
                                   app.services.role_template_permission_service
  level                            1 (Intern) .. 17 (CEO): the Manage Role the Job Title names
                                   (org_roles.hierarchy_level); the add-on template's level for
                                   people without one
  RoleTemplate.org_level_access    sees every business unit: either template carries it
  RoleTemplate.specialization      e.g. Finance, Recruitment: either template, or the department

Never by a role's name or the legacy Users.UserRole string: renaming a role must not
change what its holders can do. The level thresholds are configuration (settings), so a
different ladder needs no code change. Every function fails closed: no role, a disabled
role or a role from another tenant grants nothing.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.role_template import RoleTemplate
from app.models.user import Users

logger = logging.getLogger(__name__)

ACTIONS = ("view", "create", "edit", "delete")

# One request asks the same questions about the same person many times (every permission check,
# scope filter and authority flag re-read their role, Manage Role and templates: 20-30 queries per
# call). The answers are kept on the request's session, keyed by everything they depend on, and
# dropped whenever the session flushes, commits or rolls back -- a change made in the request is
# never answered from before it.
_CACHE_KEY = "authority_cache"


def _cached(db: Session, name: str, user: Optional[Users], compute):
    if user is None:
        return compute()
    info = getattr(db, "info", None)
    if info is None:
        return compute()
    key = (name, user.UserID, user.tenant_id, user.role_template_id, user.job_title)
    cache = info.setdefault(_CACHE_KEY, {})
    if key not in cache:
        cache[key] = compute()
    return cache[key]


def _drop_cache(session, *args) -> None:
    session.info.pop(_CACHE_KEY, None)


from sqlalchemy import event as _event  # noqa: E402
from sqlalchemy.orm import Session as _Session  # noqa: E402

for _name in ("after_flush", "after_commit", "after_rollback", "after_soft_rollback"):
    _event.listen(_Session, _name, _drop_cache)


def role_of(db: Session, user: Optional[Users]) -> Optional[RoleTemplate]:
    return _cached(db, "role_of", user, lambda: _role_of(db, user))


def _role_of(db: Session, user: Optional[Users]) -> Optional[RoleTemplate]:
    if user is None or not user.role_template_id:
        return None
    role = db.query(RoleTemplate).filter(RoleTemplate.id == user.role_template_id,
                                         RoleTemplate.enabled.is_(True)).first()
    if role is None or (user.tenant_id is not None and role.tenant_id not in (None, user.tenant_id)):
        return None
    return role


def manage_role(db: Session, user: Optional[Users]):
    """The active Manage Role (org_roles) the user's Job Title names, or None."""
    from app.services.org_roles_service import role_for_title

    if user is None or user.tenant_id is None:
        return None
    return _cached(db, "manage_role", user, lambda: role_for_title(db, user.tenant_id, user.job_title))


def templates_of(db: Session, user: Optional[Users]) -> list:
    """[Manage Role permission set, function add-on] -- the enabled ones in the user's tenant."""
    from app.services.role_template_permission_service import RoleTemplatePermissionService

    if user is None:
        return []
    return list(_cached(db, "templates_of", user, lambda: _templates_of(db, user)))


def _templates_of(db: Session, user: Users) -> list:
    from app.services.role_template_permission_service import RoleTemplatePermissionService

    out = []
    if user.tenant_id is not None:
        role_set = RoleTemplatePermissionService.get_manage_role_template(db, user, user.tenant_id)
        if role_set is not None:
            out.append(role_set)
    addon = role_of(db, user)
    if addon is not None and all(t.id != addon.id for t in out):
        out.append(addon)
    return out


def level(db: Session, user: Optional[Users]) -> int:
    """The Manage Role's level; the add-on template's for people without a Manage Role.
    No role and no template (or a disabled template) is 0."""
    if role_of(db, user) is None:
        return 0
    role = manage_role(db, user)
    if role is not None:
        return int(role.hierarchy_level)
    return int(role_of(db, user).hierarchy_level or 0)


def is_org_level(db: Session, user: Optional[Users]) -> bool:
    """Sees every business unit."""
    return any(t.org_level_access for t in templates_of(db, user))


def is_bu_leader(db: Session, user: Optional[Users]) -> bool:
    """Heads a business unit or more (BU Head / VP and above)."""
    return level(db, user) >= settings.BU_LEADER_MIN_LEVEL


def is_partner(db: Session, user: Optional[Users]) -> bool:
    return level(db, user) >= settings.PARTNER_MIN_LEVEL


def is_ceo(db: Session, user: Optional[Users]) -> bool:
    return level(db, user) >= settings.CEO_LEVEL


def is_director(db: Session, user: Optional[Users]) -> bool:
    return level(db, user) >= settings.DIRECTOR_MIN_LEVEL


def in_function(db: Session, user: Optional[Users], function: str) -> bool:
    """One of the person's templates is for the function (specialization), or the person
    belongs to it (users.department_id -> the managed function). Names match exactly
    (case-insensitive) or by whole word, so a function renamed "Talent Acquisition" still counts
    as Recruitment (app.services.org_hierarchy_validator). Never by job title or role text."""
    from app.services.org_hierarchy_validator import function_of_department_name

    def matches(name):
        return bool(name) and (name.strip().lower() == function.lower()
                               or function_of_department_name(name) == function)

    templates = templates_of(db, user)
    if not templates:
        return False
    if any(matches(t.specialization) for t in templates):
        return True
    department = getattr(user, "department", None)
    return department is not None and department.active and matches(department.name)


def in_finance(db: Session, user: Optional[Users]) -> bool:
    return in_function(db, user, "Finance")


def is_finance_leader(db: Session, user: Optional[Users]) -> bool:
    """Finance at Senior Manager level or above (Senior Manager, Director, VP, CFO)."""
    return level(db, user) >= settings.SENIOR_MANAGER_MIN_LEVEL and in_finance(db, user)


def is_revenue_bu_scoped(db: Session, user: Optional[Users]) -> bool:
    """Only org-level role templates see every business unit's revenue; everyone else sees
    the business units they partner, head or belong to (app.core.data_scope)."""
    return not is_org_level(db, user)


def requires_totp(db: Session, user: Optional[Users]) -> bool:
    """By the higher of the Manage Role level and the add-on template's level, so moving a
    person onto a Manage Role never drops a second factor they needed before."""
    addon = role_of(db, user)
    template_level = int(addon.hierarchy_level or 0) if addon else 0
    return max(level(db, user), template_level) >= settings.MFA_TOTP_MIN_LEVEL


def requires_email_otp(db: Session, user: Optional[Users]) -> bool:
    """Every internal user with a role (candidates sign in separately)."""
    return role_of(db, user) is not None


# Home dashboard by ROLE (CEO 2026-10-12): the user's position in the firm -- the org
# position their Job Title names (OrgPosition: CEO, Partner, BU Head, ...), else the position
# of their org-chart node. Authority (what they may see and do) stays with the role template:
# a home dashboard also needs its *-dashboard view permission, else the general dashboard.
# Holding a permission never makes a dashboard home (an admin template holds them all).
# position code (OrgPosition.rbac_role_name) -> (home key, dashboard resource); a C-level
# (partner-rank) position in Finance is the CFO.
HOME_BY_POSITION = {
    "ceo": ("ceo", "ceo-dashboard"),
    "partner": ("partner", "partner-dashboard"),
    "bu_head": ("bu_head", "bu-head-dashboard"),
}
CFO_HOME = ("cfo", "cfo-dashboard")


def position(db: Session, user: Optional[Users]):
    """(position code, designation) of the user's role in the firm, or (None, None).
    The Job Title is what the Users screen shows and edits, so it wins: a managed role
    (org_roles) gives its level -> position and its designation (ceo / cfo); an org
    position name is the fallback for older titles, then the org-chart seat."""
    from app.models.org_structure import OrgNode, OrgPosition
    from app.services.org_hierarchy_validator import LEVEL_POSITION_CODES
    from app.services.org_roles_service import role_for_title

    if user is None:
        return None, None
    title = (user.job_title or "").strip()
    if title:
        role = role_for_title(db, user.tenant_id, title)
        if role is not None and LEVEL_POSITION_CODES.get(role.hierarchy_level):
            return LEVEL_POSITION_CODES[role.hierarchy_level], role.designation
        match = db.query(OrgPosition).filter(OrgPosition.name.ilike(title)).first()
        if match:
            return match.rbac_role_name, None
    node = db.query(OrgNode).filter(OrgNode.id == user.org_node_id).first() if user.org_node_id else None
    if node is not None:
        pos = db.query(OrgPosition).filter(OrgPosition.id == node.position_id).first()
        if pos:
            return pos.rbac_role_name, None
    return None, None


def heads_a_business_unit(db: Session, user: Optional[Users]) -> bool:
    """Named BU head of a business unit in some company (BusinessUnitLocationHead)."""
    from app.models.business_unit import BusinessUnitLocationHead

    return bool(user) and db.query(BusinessUnitLocationHead.id).filter(
        BusinessUnitLocationHead.head_user_id == user.UserID).first() is not None


def _home(db: Session, user: Optional[Users]):
    code, designation = position(db, user)
    home = CFO_HOME if designation == "cfo" else HOME_BY_POSITION.get(code)
    if home and home[0] == "bu_head" and not heads_a_business_unit(db, user):
        home = None
    if home and has_permission(db, user, f"{home[1]}.view"):
        return home
    return None


def home_dashboard(db: Session, user: Optional[Users]) -> str:
    """CFO is a designation on the role (never a department name); the BU Head home is for
    people who actually head a business unit (levels 13-15 share that position code)."""
    home = _home(db, user)
    return home[0] if home else "default"


def home_resource(db: Session, user: Optional[Users]) -> Optional[str]:
    """The dashboard resource that is this user's Home ("/"), or None for the general dashboard.
    The menu never lists that dashboard a second time under its own name (CEO 2026-10-17)."""
    home = _home(db, user)
    return home[1] if home else None


def summary(db: Session, user: Optional[Users]) -> dict:
    """What the client needs to shape its UI -- the same flags the server enforces with."""
    specializations = [t.specialization for t in templates_of(db, user)
                       if t.specialization and t.specialization != "General"]
    return {"org_level_access": is_org_level(db, user),
            "hierarchy_level": level(db, user),
            "specialization": specializations[0] if specializations else ("General" if role_of(db, user) else None),
            "is_bu_leader": is_bu_leader(db, user),
            "is_finance_leader": is_finance_leader(db, user),
            "position": position(db, user)[0],
            "home_dashboard": home_dashboard(db, user)}


def has_permission(db: Session, user: Optional[Users], permission: str) -> bool:
    """permission is '<resource>.<view|create|edit|delete>' on a seeded resource. Decided by the
    role's permission matrix only -- there is no super-user bypass (CEO 2026-10-11: a super
    admin sees what its role's modules and resources grant). A malformed string raises."""
    from app.services.role_template_permission_service import RoleTemplatePermissionService

    resource, _, action = (permission or "").rpartition(".")
    if not resource or action not in ACTIONS:
        raise ValueError(f"Malformed permission {permission!r}: expected '<resource>.<{'|'.join(ACTIONS)}>'")
    if user is None:
        return False
    return RoleTemplatePermissionService.has_permission(db, user.UserID, resource, action, user.tenant_id)


def has_any_permission(db: Session, user: Optional[Users], permissions) -> bool:
    return any(has_permission(db, user, p) for p in permissions)
