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
    try:
        from app.core.logging import logger

        token = credentials.credentials
        logger.warning(f"[AUTH-DEBUG] Token: {token[:30]}...")

        payload = decode_access_token(token)
        logger.warning(f"[AUTH-DEBUG] Decoded payload: sub={payload.get('sub')}, type={payload.get('type')}, email={payload.get('email')}")

        _reject_if_mfa_pending(payload)
        _reject_if_candidate_otp_pending(payload)

        user_id: str = payload.get("sub")
        user_type: str = payload.get("type", "candidate")

        logger.warning(f"[AUTH-DEBUG] user_id={user_id}, user_type={user_type}")

        if not user_id:
            logger.error("[AUTH-DEBUG] No user_id in token")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        if user_type == "user":
            # "sub" contains UserID
            logger.warning(f"[AUTH-DEBUG] Querying Users by UserID: {user_id}")
            user = db.query(Users).filter(Users.UserID == user_id).first()
            if not user:
                logger.error(f"[AUTH-DEBUG] User not found with UserID: {user_id}")
        else:
            logger.warning(f"[AUTH-DEBUG] Querying Candidate by candidateID: {user_id}")
            user = db.query(Candidate).filter(Candidate.candidateID == user_id).first()
            if not user:
                logger.error(f"[AUTH-DEBUG] Candidate not found with ID: {user_id}")

        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        logger.warning(f"[AUTH-DEBUG] User found: {getattr(user, 'UserEmail', getattr(user, 'candidateEmail', 'N/A'))}")
        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AUTH-DEBUG] Exception in get_current_user: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Auth failed: {str(e)}")


async def get_current_candidate(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get the current authenticated candidate from JWT token.
    """
    try:
        from app.core.logging import logger

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
    except HTTPException:
        raise
    except Exception as e:
        from app.core.logging import logger
        logger.error(f"[get_current_candidate] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Authentication failed: {str(e)}")


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
    try:
        from app.core.logging import logger

        token = credentials.credentials
        payload = decode_access_token(token)

        if not payload.get("candidate_otp_pending"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a candidate email-verification-pending session")

        candidate_id: str = payload.get("sub", "")
        if not candidate_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No candidate ID in token")

        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Candidate not found")
        return candidate
    except HTTPException:
        raise
    except Exception as e:
        from app.core.logging import logger
        logger.error(f"[get_current_candidate_otp_pending] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Authentication failed: {str(e)}")


async def get_current_hr_or_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get the current authenticated internal user from JWT token.
    Allows any user found in the Users table (any role). Candidates are excluded.
    """
    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        _reject_if_mfa_pending(payload)

        user_id: str = payload.get("sub")
        user_type: str = payload.get("type", "").lower()

        if not user_id or user_type == "candidate":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        # 'sub' now contains UserID (not email)
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # DISABLED - Single company deployment, no tenant scoping needed
        # from app.core.tenant_context import activate_tenant_scope
        # activate_tenant_scope(user.tenant_id)

        return user
    except HTTPException:
        raise
    except Exception as e:
        from app.core.logging import logger
        logger.error(f"[get_current_hr_or_admin] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication failed: {str(e)}")


async def get_current_internal_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Users:
    """
    Resolve any internal (non-candidate) user from JWT. Used as a base for RBAC guards.
    Allows any user found in the Users table (any role). Candidates are excluded.
    """
    try:
        from app.core.logging import logger

        token = credentials.credentials
        payload = decode_access_token(token)
        _reject_if_mfa_pending(payload)

        user_id: str = payload.get("sub")
        user_type: str = payload.get("type", "").lower()

        if not user_id or user_type == "candidate":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # DISABLED - Single company deployment, no tenant scoping needed
        # from app.core.tenant_context import activate_tenant_scope
        # activate_tenant_scope(user.tenant_id)

        return user
    except HTTPException:
        raise
    except Exception as e:
        from app.core.logging import logger
        logger.error(f"[get_current_internal_user] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Authentication failed: {str(e)}")


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

    user_id: str = payload.get("sub", "")
    user = db.query(Users).filter(Users.UserID == user_id).first()
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
    DEPRECATED: Use require_resource_permission() instead.

    Legacy function that maps old hardcoded permission strings to new resource-based system.
    This is kept for backward compatibility during migration.

    Old Usage (deprecated):
        @router.get("/path", dependencies=[Depends(require_permission("candidate.view"))])

    New Usage (preferred):
        @router.post("/path", dependencies=[Depends(require_resource_permission("candidates", "create"))])
    """
    async def _check(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db),
    ):
        token = credentials.credentials
        payload = decode_access_token(token)
        _reject_if_mfa_pending(payload)
        user_id: str = payload.get("sub", "")

        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # Use new role template permission service
        from app.services.role_template_permission_service import RoleTemplatePermissionService

        # Super User & Admin bypass — always has all permissions
        if RoleTemplatePermissionService.is_super_user(db, user.UserID, user.tenant_id):
            return user

        # For legacy support: map old permission strings to new resource names
        # This will return False if the resource doesn't exist in the database
        if not RoleTemplatePermissionService.has_permission(db, user.UserID, permission, "view", user.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: '{permission}' required",
            )
        return user

    _check.__wros_permission__ = permission
    return _check


def require_resource_permission(resource_name: str, action: str = "view"):
    """
    NEW: FastAPI dependency factory using database-driven role templates.

    Checks if user has the specified action (view, create, edit, delete) on a resource.

    Usage:
        @router.get("/candidates", dependencies=[Depends(require_resource_permission("candidates", "view"))])
        @router.post("/candidates", dependencies=[Depends(require_resource_permission("candidates", "create"))])
        @router.put("/candidates/{id}", dependencies=[Depends(require_resource_permission("candidates", "edit"))])
        @router.delete("/candidates/{id}", dependencies=[Depends(require_resource_permission("candidates", "delete"))])

    Returns 403 if the user doesn't have the required permission.
    Super Users automatically have all permissions.
    """
    async def _check(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db),
    ):
        from app.services.role_template_permission_service import RoleTemplatePermissionService

        token = credentials.credentials
        payload = decode_access_token(token)
        _reject_if_mfa_pending(payload)
        user_id: str = payload.get("sub", "")

        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # Super User bypass
        from app.services.rbac_service import RBACService
        if RBACService.is_super_user(db, user.UserID, user.tenant_id):
            return user

        # Check resource + action permission
        if not RoleTemplatePermissionService.has_permission(db, user.UserID, resource_name, action, user.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {action} access to '{resource_name}' required",
            )
        return user

    _check.__wros_permission__ = f"{resource_name}.{action}"
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
        user_id: str = payload.get("sub", "")

        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # DISABLED - Single company deployment, no tenant scoping needed
        # from app.core.tenant_context import activate_tenant_scope
        # activate_tenant_scope(user.tenant_id)

        # Super User bypass — check via PermissionHelper
        # Super User role has all permissions; check fundamental admin.manage permission
        from app.services.permission_helper import PermissionHelper
        if PermissionHelper.is_super_admin(user.UserID, db, user.tenant_id):
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
    user_id: str = payload.get("sub", "")

    user = db.query(Users).filter(Users.UserID == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # DISABLED - Single company deployment, no tenant scoping needed
    # from app.core.tenant_context import activate_tenant_scope
    # activate_tenant_scope(user.tenant_id)

    # Check admin permission via PermissionHelper (database-driven RBAC)
    # Admin users have admin.edit (or other admin CRUD) permissions
    from app.services.permission_helper import PermissionHelper
    has_admin_perms = PermissionHelper.has_any_permission(
        user.UserID,
        ["admin.manage", "admin.edit", "admin.create", "rbac.manage"],
        db,
        user.tenant_id
    )

    if not has_admin_perms:
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
