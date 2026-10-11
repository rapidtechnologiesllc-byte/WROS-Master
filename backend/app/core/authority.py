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
FINANCE_SPECIALIZATIONS = ("finance", "accounts", "accounting")


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
    """The role's specialization (or the user's department) is Finance."""
    role = role_of(db, user)
    if role is None:
        return False
    texts = [role.specialization]
    department = getattr(user, "department", None)
    if department is not None:
        texts.append(department.name)
    return any(word in (t or "").lower() for t in texts for word in FINANCE_SPECIALIZATIONS)


def is_finance_leader(db: Session, user: Optional[Users]) -> bool:
    """Finance at Senior Manager level or above (Senior Manager, Director, VP, CFO)."""
    return level(db, user) >= settings.SENIOR_MANAGER_MIN_LEVEL and in_finance(db, user)


def is_revenue_bu_scoped(db: Session, user: Optional[Users]) -> bool:
    """BU leaders see revenue for their own BU only; org-level roles see all of it."""
    return is_bu_leader(db, user) and not is_org_level(db, user)


def requires_totp(db: Session, user: Optional[Users]) -> bool:
    return level(db, user) >= settings.MFA_TOTP_MIN_LEVEL


def requires_email_otp(db: Session, user: Optional[Users]) -> bool:
    """Every internal user with a role (candidates sign in separately)."""
    return role_of(db, user) is not None


def summary(db: Session, user: Optional[Users]) -> dict:
    """What the client needs to shape its UI -- the same flags the server enforces with."""
    role = role_of(db, user)
    return {"org_level_access": is_org_level(db, user),
            "hierarchy_level": int(role.hierarchy_level or 0) if role else 0,
            "specialization": role.specialization if role else None,
            "is_bu_leader": is_bu_leader(db, user),
            "is_finance_leader": is_finance_leader(db, user)}


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
