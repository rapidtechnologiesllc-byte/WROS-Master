"""Roles (job titles) and the org level each sits at -- data, not code (CEO 2026-10-12).

The default list seeds a new tenant; afterwards roles are added, renamed and retired on
the Organizational Hierarchy screen. A user's Job Title is one of these roles and sets
their org level; the level maps to the org position (CEO / Partner / BU Head ...) through
app.services.org_hierarchy_validator.LEVEL_POSITION_CODES.
"""
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.org_structure import OrgRole

# Designations code treats specially, and the level each must sit at
DESIGNATION_LEVELS = {"ceo": 17, "cfo": 16}

# (role name, org level). Names of the firm's positions where one exists at that level.
DEFAULT_ROLE_TITLES = (
    ("CEO", 17), ("Partner", 16), ("CFO", 16), ("Senior Vice President", 15), ("BU Head", 14),
    ("Vice President", 14), ("Assistant Vice President", 13), ("Senior Director", 12), ("Director", 11),
    ("Assistant Director", 10), ("Senior Manager", 9), ("Manager", 8), ("Associate Manager", 7),
    ("Lead Consultant", 6), ("Senior Consultant", 5), ("Consultant", 4), ("Senior Associate", 3),
    ("Associate", 2), ("Intern", 1),
)


def role_for_title(db: Session, tenant_id: int, title: Optional[str]) -> Optional[OrgRole]:
    """The active role a Job Title names (case-insensitive), or None."""
    if not title or not title.strip():
        return None
    return db.query(OrgRole).filter(
        OrgRole.tenant_id == tenant_id, OrgRole.active.is_(True),
        func.lower(OrgRole.name) == title.strip().lower(),
    ).first()


DEFAULT_DESIGNATIONS = {"CEO": "ceo", "CFO": "cfo"}


# A person's Job Title holds the role name (Users.job_title is String(150))
ROLE_NAME_MAX = 150


def validate_role(db: Session, tenant_id: int, name: str, hierarchy_level: int,
                  role_id: Optional[int] = None, designation: Optional[str] = None) -> str:
    """Raise ValueError unless the name is unique for the tenant, the level is 1-17, and a
    designation sits at its level (CEO 17, CFO 16) with only one CEO role per tenant."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Role name is required")
    if len(name) > ROLE_NAME_MAX:
        raise ValueError(f"Role name is limited to {ROLE_NAME_MAX} characters")
    if not isinstance(hierarchy_level, int) or not 1 <= hierarchy_level <= 17:
        raise ValueError("Level must be 1-17")
    clash = db.query(OrgRole).filter(OrgRole.tenant_id == tenant_id, func.lower(OrgRole.name) == name.lower())
    if role_id is not None:
        clash = clash.filter(OrgRole.id != role_id)
    if clash.first():
        raise ValueError(f"A role named {name!r} already exists")
    if designation:
        if designation not in DESIGNATION_LEVELS:
            raise ValueError(f"Designation must be one of {sorted(DESIGNATION_LEVELS)}")
        if hierarchy_level != DESIGNATION_LEVELS[designation]:
            raise ValueError(f"The {designation.upper()} role must be level {DESIGNATION_LEVELS[designation]}")
        if designation == "ceo":
            other = db.query(OrgRole).filter(OrgRole.tenant_id == tenant_id, OrgRole.designation == "ceo")
            if role_id is not None:
                other = other.filter(OrgRole.id != role_id)
            if other.first():
                raise ValueError("The organization already has a CEO role")
    return name


def holders_count(db: Session, role: OrgRole) -> int:
    from app.models.user import Users

    return db.query(Users).filter(Users.tenant_id == role.tenant_id, func.lower(func.trim(Users.job_title)) == role.name.strip().lower()).count()


def require_role(db: Session, tenant_id: int, title: Optional[str]) -> OrgRole:
    """The active role a Job Title must name (ValueError otherwise)."""
    role = role_for_title(db, tenant_id, title)
    if role is None:
        raise ValueError(f"Job title {title!r} is not a role - pick one from the list "
                         "(roles are managed under Organizational Hierarchy > Manage Roles)")
    return role


def ensure_single_holder(db: Session, role: OrgRole, user_id: Optional[str] = None) -> None:
    """A CEO-designated role is held by one person."""
    from app.models.user import Users

    if role.designation != "ceo":
        return
    other = db.query(Users).filter(Users.tenant_id == role.tenant_id,
                                   func.lower(Users.job_title) == role.name.lower())
    if user_id is not None:
        other = other.filter(Users.UserID != user_id)
    holder = other.first()
    if holder:
        raise ValueError(f"{holder.UserName or holder.UserEmail} already holds the {role.name} role")


def ensure_permission_set(db: Session, role: OrgRole):
    """The role's permission set (a non-system RoleTemplate owned by the role), created EMPTY
    the first time so that giving someone a role never widens their access by itself; an
    admin then grants what the role should allow in the Role Templates editor. Keeps the
    template's name and level in step with the role (authority reads the role's level).
    Flushes; the caller commits."""
    from app.models.role_template import RoleTemplate

    template = db.get(RoleTemplate, role.role_template_id) if role.role_template_id else None
    if template is None:
        template = RoleTemplate(name=f"{role.name} (role)", display_name=role.name,
                                description=f"What every {role.name} may see and do",
                                hierarchy_level=role.hierarchy_level, specialization="General",
                                org_level_access=False, is_system=False, enabled=True,
                                tenant_id=role.tenant_id)
        db.add(template)
        db.flush()
        role.role_template_id = template.id
    elif template.display_name != role.name or template.hierarchy_level != role.hierarchy_level:
        template.name, template.display_name = f"{role.name} (role)", role.name
        template.hierarchy_level = role.hierarchy_level
    db.flush()
    return template


def owning_role(db: Session, template_id: int) -> Optional[OrgRole]:
    """The Manage Role whose permission set this template is, or None (a function add-on)."""
    return db.query(OrgRole).filter(OrgRole.role_template_id == template_id).first()
