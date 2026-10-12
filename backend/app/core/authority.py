"""Who may do what -- decided ONLY by the user's role template (CEO rule, 2026-10-10):

  RoleTemplatePermission           what the role may do: resource x view/create/edit/delete
  RoleTemplate.org_level_access    sees every business unit, not just their own
  RoleTemplate.hierarchy_level     1 (Intern) .. 17 (CEO), see org_hierarchy_validator.HIERARCHY_LEVELS
  RoleTemplate.specialization      e.g. Finance, Recruitment

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


def role_of(db: Session, user: Optional[Users]) -> Optional[RoleTemplate]:
    if user is None or not user.role_template_id:
        return None
    role = db.query(RoleTemplate).filter(RoleTemplate.id == user.role_template_id,
                                         RoleTemplate.enabled.is_(True)).first()
    if role is None or (user.tenant_id is not None and role.tenant_id not in (None, user.tenant_id)):
        return None
    return role


def level(db: Session, user: Optional[Users]) -> int:
    role = role_of(db, user)
    return int(role.hierarchy_level or 0) if role else 0


def is_org_level(db: Session, user: Optional[Users]) -> bool:
    """Sees every business unit."""
    role = role_of(db, user)
    return bool(role and role.org_level_access)


def is_bu_leader(db: Session, user: Optional[Users]) -> bool:
    """Heads a business unit or more (BU Head / VP and above)."""
    return level(db, user) >= settings.BU_LEADER_MIN_LEVEL


def is_partner(db: Session, user: Optional[Users]) -> bool:
    return level(db, user) >= settings.PARTNER_MIN_LEVEL


def is_ceo(db: Session, user: Optional[Users]) -> bool:
    return level(db, user) >= settings.CEO_LEVEL


def is_director(db: Session, user: Optional[Users]) -> bool:
    return level(db, user) >= settings.DIRECTOR_MIN_LEVEL


def in_finance(db: Session, user: Optional[Users]) -> bool:
    """The role template's specialization is Finance, or the user's department is a Finance
    department (whole-word match: app.services.org_hierarchy_validator)."""
    from app.services.org_hierarchy_validator import function_of_department_name

    role = role_of(db, user)
    if role is None:
        return False
    if function_of_department_name(role.specialization) == "Finance":
        return True
    department = getattr(user, "department", None)
    return department is not None and function_of_department_name(department.name) == "Finance"


def is_finance_leader(db: Session, user: Optional[Users]) -> bool:
    """Finance at Senior Manager level or above (Senior Manager, Director, VP, CFO)."""
    return level(db, user) >= settings.SENIOR_MANAGER_MIN_LEVEL and in_finance(db, user)


def is_revenue_bu_scoped(db: Session, user: Optional[Users]) -> bool:
    """Only org-level role templates see every business unit's revenue; everyone else sees
    the business units they partner, head or belong to (app.core.data_scope)."""
    return not is_org_level(db, user)


def requires_totp(db: Session, user: Optional[Users]) -> bool:
    return level(db, user) >= settings.MFA_TOTP_MIN_LEVEL


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


def home_dashboard(db: Session, user: Optional[Users]) -> str:
    """CFO is a designation on the role (never a department name); the BU Head home is for
    people who actually head a business unit (levels 13-15 share that position code)."""
    code, designation = position(db, user)
    home = CFO_HOME if designation == "cfo" else HOME_BY_POSITION.get(code)
    if home and home[0] == "bu_head" and not heads_a_business_unit(db, user):
        home = None
    if home and has_permission(db, user, f"{home[1]}.view"):
        return home[0]
    return "default"


def summary(db: Session, user: Optional[Users]) -> dict:
    """What the client needs to shape its UI -- the same flags the server enforces with."""
    role = role_of(db, user)
    return {"org_level_access": is_org_level(db, user),
            "hierarchy_level": int(role.hierarchy_level or 0) if role else 0,
            "specialization": role.specialization if role else None,
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
