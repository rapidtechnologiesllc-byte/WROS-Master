from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token, security
from app.models.user import Users
from app.models.candidate import Candidate


def _reject_if_mfa_pending(payload: dict) -> None:
    """
    Phase 1 B3 -- a token issued mid-MFA-challenge (mfa_pending: true)
    must never work as a normal access token anywhere else. Without
    this check, the MFA gate in the login endpoint would be
    decorative: a caller could take the "pending" token and use it on
    any other route exactly like a real one, since every dependency
    below only checks `type`/`sub`, not this claim. Call this
    immediately after decode_access_token() in every dependency that
    resolves a user from a token.
    """
    if payload.get("mfa_pending"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA verification required before this token can be used",
        )


def _reject_if_candidate_otp_pending(payload: dict) -> None:
    """Backlog item, 2026-08-05 (wros_email_2fa_backlog, candidate
    half) -- the candidate-side counterpart to _reject_if_mfa_pending
    above. A token issued mid-email-OTP-challenge
    (candidate_otp_pending: true) must never work as a normal candidate
    session anywhere else."""
    if payload.get("candidate_otp_pending"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required before this token can be used",
        )


# ---------------------------------------------------------------------------
# Base user resolution
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get the current authenticated user (User or Candidate) from JWT token.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    _reject_if_mfa_pending(payload)
    _reject_if_candidate_otp_pending(payload)

    user_id: str = payload.get("sub")
    user_type: str = payload.get("type", "candidate")

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # If type is not "candidate", it's an internal user (role name like "Super User", "Admin", etc.)
    # "sub" contains email for internal users
    if user_type != "candidate":
        user = db.query(Users).filter(Users.UserEmail == user_id).first()
    else:
        user = db.query(Candidate).filter(Candidate.candidateID == user_id).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # DISABLED - Single company deployment, no tenant scoping needed
    # from app.core.tenant_context import activate_tenant_scope
    # activate_tenant_scope(getattr(user, "tenant_id", None))

    return user


async def get_current_candidate(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get the current authenticated candidate from JWT token.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    _reject_if_mfa_pending(payload)
    _reject_if_candidate_otp_pending(payload)

    user_id: str = payload.get("sub")
    user_type: str = payload.get("type")

    if not user_id or user_type != "candidate":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized as candidate")

    candidate = db.query(Candidate).filter(Candidate.candidateID == user_id).first()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Candidate not found")

    return candidate


async def get_current_candidate_otp_pending(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Candidate:
    """Backlog item, 2026-08-05 (wros_email_2fa_backlog, candidate
    half) -- the candidate-side counterpart to
    get_current_mfa_pending_user. ONLY accepts a token with
    candidate_otp_pending=true, resolved to the Candidate row it names.
    A normal full candidate token must not work here either -- a
    candidate can't skip straight to "verify" without having actually
    passed the password check first in the current session."""
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload.get("candidate_otp_pending"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a candidate email-verification-pending session")

    candidate_id: str = payload.get("sub", "")
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Candidate not found")
    return candidate


async def get_current_hr_or_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get the current authenticated internal user from JWT token.
    Allows any user found in the Users table (any role). Candidates are excluded.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    _reject_if_mfa_pending(payload)

    user_id: str = payload.get("sub")
    user_type: str = payload.get("type", "").lower()

    if not user_id or user_type == "candidate":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # For Microsoft SSO users, 'sub' contains email
    user = db.query(Users).filter(Users.UserEmail == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # DISABLED - Single company deployment, no tenant scoping needed
    # from app.core.tenant_context import activate_tenant_scope
    # activate_tenant_scope(user.tenant_id)

    return user


async def get_current_internal_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Users:
    """
    Resolve any internal (non-candidate) user from JWT. Used as a base for RBAC guards.
    Allows any user found in the Users table (any role). Candidates are excluded.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    _reject_if_mfa_pending(payload)

    user_id: str = payload.get("sub")
    user_type: str = payload.get("type", "").lower()

    if not user_id or user_type == "candidate":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    user = db.query(Users).filter(Users.UserEmail == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # DISABLED - Single company deployment, no tenant scoping needed
    # from app.core.tenant_context import activate_tenant_scope
    # activate_tenant_scope(user.tenant_id)

    return user


async def get_current_mfa_pending_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Users:
    """
    The inverse of _reject_if_mfa_pending: ONLY accepts a token with
    mfa_pending=true, resolved to the Users row it names. Used
    exclusively by the MFA setup/verify endpoints -- a normal full
    access token must not work here either, so a user can't skip
    straight to "verify" without having actually gone through login's
    password check first in the current session.
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload.get("mfa_pending"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an MFA-pending session")

    user_email: str = payload.get("sub", "")
    user = db.query(Users).filter(Users.UserEmail == user_email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# HRMS-0114 — these three establish a real, explicit identity boundary
# (candidate-self-service-only, or any-authenticated-internal-user)
# even though they're not fine-grained RBAC permissions. Marked so
# route_security_audit.py counts them as a deliberate declaration
# rather than "no auth at all" -- the audit still separately reports
# which routes only have one of these coarse checks vs a specific
# require_permission()/require_attribute(), since the latter is the
# tighter, preferred pattern for anything beyond pure self-service.
get_current_user.__wros_authn__ = "any_authenticated_user_or_candidate"
get_current_candidate.__wros_authn__ = "candidate_self_service"
get_current_hr_or_admin.__wros_authn__ = "any_internal_user"
get_current_internal_user.__wros_authn__ = "any_internal_user"
get_current_mfa_pending_user.__wros_authn__ = "mfa_pending_session"
get_current_candidate_otp_pending.__wros_authn__ = "candidate_otp_pending_session"


# ---------------------------------------------------------------------------
# RBAC — permission and attribute guards
# ---------------------------------------------------------------------------

def require_permission(permission: str):
    """
    FastAPI dependency factory that enforces a named RBAC permission.

    Usage:
        @router.get("/path", dependencies=[Depends(require_permission("candidate.view"))])

    Returns 403 if the authenticated user's role does not include the permission.
    Falls back gracefully if the user has no RBAC role assigned (denies access).
    """
    async def _check(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db),
    ):
        from app.services.rbac_service import RBACService

        token = credentials.credentials
        payload = decode_access_token(token)
        _reject_if_mfa_pending(payload)
        user_email: str = payload.get("sub", "")

        user = db.query(Users).filter(Users.UserEmail == user_email).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # DISABLED - Single company deployment, no tenant scoping needed
        # from app.core.tenant_context import activate_tenant_scope
        # activate_tenant_scope(user.tenant_id)

        # Super User bypass — CEO, Admin, and Super User roles have all permissions
        # This applies to all endpoints, present and future, without requiring manual configuration
        # Check: (1) legacy UserRole, (2) single role relationship, (3) user_roles junction table
        from app.models.user import UserRole as UserRoleModel

        super_user_roles = {"super user", "admin", "ceo", "cfo"}
        is_super_user = False

        # Check legacy UserRole string
        if user.UserRole and user.UserRole.lower() in super_user_roles:
            is_super_user = True

        # Check single role relationship
        if not is_super_user and user.role and user.role.name:
            if user.role.name.lower() in super_user_roles:
                is_super_user = True

        # Check user_roles junction table (multi-role support)
        if not is_super_user:
            user_roles = db.query(UserRoleModel).filter(UserRoleModel.user_id == user.UserID).all()
            for ur in user_roles:
                if ur.role and ur.role.name.lower() in super_user_roles:
                    is_super_user = True
                    break

        if is_super_user:
            return user

        if not RBACService.has_permission(db, user.UserID, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: '{permission}' required",
            )
        return user

    # HRMS-0114 — marks this closure as a permission declaration so
    # app.core.route_security_audit can find it on a route at startup.
    _check.__wros_permission__ = permission
    return _check


def require_attribute(attribute: str, expected: bool = True):
    """
    FastAPI dependency factory that enforces a role attribute flag.

    Usage:
        @router.post("/pipeline", dependencies=[Depends(require_attribute("pipeline_control"))])

    Returns 403 if the authenticated user's role does not have the attribute set to `expected`.
    """
    async def _check(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db),
    ):
        from app.services.rbac_service import RBACService

        token = credentials.credentials
        payload = decode_access_token(token)
        _reject_if_mfa_pending(payload)
        user_email: str = payload.get("sub", "")

        user = db.query(Users).filter(Users.UserEmail == user_email).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # DISABLED - Single company deployment, no tenant scoping needed
        # from app.core.tenant_context import activate_tenant_scope
        # activate_tenant_scope(user.tenant_id)

        # Super User bypass — check both legacy UserRole string and RBAC role relationship
        is_super_user = (
            (user.UserRole and user.UserRole.lower() == "super user")
            or (user.role and user.role.name and user.role.name.lower() == "super user")
        )
        if is_super_user:
            return user

        if not RBACService.has_attribute(db, user.UserID, attribute, expected):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: role attribute '{attribute}' required",
            )
        return user

    # HRMS-0114 — see require_permission's matching comment above.
    _check.__wros_attribute__ = attribute
    return _check


async def require_admin_role(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Users:
    """
    S-213/BR-0115-01 -- a literal "Admin role" gate, not an RBAC
    permission string (this codebase has no 'config.write' permission
    seeded, and the business rule itself is phrased as a role check, not
    a permission). "Super User" also passes, matching the bypass every
    other guard in this file already grants it.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    _reject_if_mfa_pending(payload)
    user_email: str = payload.get("sub", "")

    user = db.query(Users).filter(Users.UserEmail == user_email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # DISABLED - Single company deployment, no tenant scoping needed
    # from app.core.tenant_context import activate_tenant_scope
    # activate_tenant_scope(user.tenant_id)

    role_name = (user.UserRole or "").lower()
    if role_name not in ("admin", "super user"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


# HRMS-0114 -- same marker convention as get_current_hr_or_admin etc.
# above; without this, app.core.route_security_audit's startup gate
# treats any route using ONLY this dependency as having no declared
# auth at all and refuses to boot. A real role check, not just "any
# internal user," but not the RBAC permission-string system either
# (no 'config.write' permission is seeded) -- __wros_authn__ is the
# closer-fitting of the two marker categories.
require_admin_role.__wros_authn__ = "admin_role_only"
