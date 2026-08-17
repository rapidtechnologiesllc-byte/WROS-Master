"""
S-205/HRMS-0107 -- Business Unit Entity & Context Switching.

No literal "Director" role exists in this codebase's real RBAC seed
(app.services.rbac_service) -- the real role list is Super User, BU
Head, Hiring Manager, HR Manager, HR Operations, HRBP, Recruitment
Manager, Recruitment Team Lead, Recruiter, Employee, Consultant,
Candidate (same real gap app.core.mfa's own docstring already
documents for "Admin"/"Director"). ALL_BUS_ROLES below maps the
spec's "Director" to "Super User" -- the same real analog mfa.py
already chose for the identical problem -- flagged as an assumption,
not a confirmed decision, same posture that file already took.

BR-0107-01: business_unit_id is re-validated against the user's real
bu_access rows on EVERY call via validate_active_bu() -- never trusted
from client state, even though the client is the one that supplies it
(this codebase's session model is JWT, not a server-side session
store -- see module docstring on get_active_business_unit_id in
app.api.v1.endpoints.bu_context for how a caller wires this in).
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.bu_access import BUAccess
from app.models.business_unit import BusinessUnit
from app.models.user import Users

ALL_BUS_ROLES = ("Super User",)  # see module docstring -- "Director" analog


class NotYourBusinessUnit(Exception):
    pass


class NotAuthorizedForAllBUs(Exception):
    pass


def get_user_bu_access(db: Session, user_id: str) -> List[BUAccess]:
    return db.query(BUAccess).filter(BUAccess.user_id == user_id).all()


def validate_active_bu(db: Session, user_id: str, business_unit_id: int) -> BUAccess:
    """BR-0107-01/AC-3 -- the real per-request check. Raises if this
    business_unit_id isn't one of the user's own bu_access rows."""
    access = db.query(BUAccess).filter(
        BUAccess.user_id == user_id, BUAccess.business_unit_id == business_unit_id,
    ).first()
    if not access:
        raise NotYourBusinessUnit(f"User {user_id!r} has no access to business unit {business_unit_id}.")
    return access


def switch_active_bu(db: Session, user: Users, business_unit_id: int) -> BUAccess:
    return validate_active_bu(db, user.UserID, business_unit_id)


def get_default_bu(db: Session, user_id: str) -> Optional[BUAccess]:
    access_rows = get_user_bu_access(db, user_id)
    default = next((a for a in access_rows if a.is_default), None)
    return default or (access_rows[0] if access_rows else None)


def activate_all_bus_view(db: Session, user: Users) -> AuditLog:
    """BR-0107-02/AC-4: privileged, tracked action -- exactly one real
    audit_log row per activation, reusing the existing HRMS-0110
    append-only table (never a second audit mechanism)."""
    if user.UserRole not in ALL_BUS_ROLES:
        raise NotAuthorizedForAllBUs(f"Role {user.UserRole!r} is not authorized for the unscoped All BUs view.")

    entry = AuditLog(
        tenant_id=user.tenant_id, entity_type="bu_context", entity_id="ALL_BUS",
        action="all_bus_view_activated", user_id=user.UserID,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def ensure_default_bu_access(db: Session, user: Users) -> Optional[BUAccess]:
    """Seeds the one real default row a user should always have --
    matching their existing Users.business_unit_id (Step 2's own
    default rule) -- idempotent, safe to call repeatedly (e.g. on
    login) for users who predate this story."""
    if not user.business_unit_id:
        return None
    existing = db.query(BUAccess).filter(
        BUAccess.user_id == user.UserID, BUAccess.business_unit_id == user.business_unit_id,
    ).first()
    if existing:
        return existing

    access = BUAccess(user_id=user.UserID, business_unit_id=user.business_unit_id, is_default=True)
    db.add(access)
    db.commit()
    db.refresh(access)
    return access
