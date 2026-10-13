from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token, security
from app.core.logging import logger
from app.models.user import Users
from app.models.candidate import Candidate
from app.services.role_template_permission_service import RoleTemplatePermissionService

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
        payload = decode_access_token(token)

        _reject_if_mfa_pending(payload)
        _reject_if_candidate_otp_pending(payload)

        user_id: str = payload.get("sub")
        user_type: str = payload.get("type", "candidate")

        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        if user_type == "user":
            # "sub" contains UserID; a deactivated user's tokens stop working at once
            user = db.query(Users).filter(Users.UserID == user_id, Users.terminated_at.is_(None)).first()
        else:
            user = db.query(Candidate).filter(Candidate.candidateID == user_id).first()

        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth failed in get_current_user: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")

async def get_current_candidate(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get the current authenticated candidate from JWT token.
    """
    try:

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
        logger.error(f"Error: {str(e)}", exc_info=True)
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
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[get_current_candidate_otp_pending] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Authentication failed: {str(e)}")

async def get_current_internal_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Users:
    """
    Resolve any internal (non-candidate) user from JWT. Used as a base for RBAC guards.
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

        user = db.query(Users).filter(Users.UserID == user_id, Users.terminated_at.is_(None)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # DISABLED - Single company deployment, no tenant scoping needed
        # from app.core.tenant_context import activate_tenant_scope
        # activate_tenant_scope(user.tenant_id)

        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[get_current_internal_user] Error: {e}", exc_info=True)
        # never echo internals (SQL, stack text) to the caller of an auth check
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Authentication failed.")

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
    user = db.query(Users).filter(Users.UserID == user_id, Users.terminated_at.is_(None)).first()
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
    @router.post("/path", dependencies=[Depends(require_role_template_permission("candidates", "can_create"))])
    """
    async def _check(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db),
    ):
        token = credentials.credentials
        payload = decode_access_token(token)
        _reject_if_mfa_pending(payload)
        user_id: str = payload.get("sub", "")

        user = db.query(Users).filter(Users.UserID == user_id, Users.terminated_at.is_(None)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # Use new role template permission service


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
    DEPRECATED: Use require_role_template_permission() instead.

    Legacy compatibility wrapper. Maps action names to column names and delegates to role templates.
    """
    return require_role_template_permission(resource_name, action)

def require_role_template_permission(resource_name: str, field_name: str = "can_view"):
    """Data-driven role template permission check. Queries database, no hard-coded permissions.

    field_name accepts either spelling ("view" or "can_view", etc.) - callers using
    Permissions.X tuples pass "can_view"-style names, require_resource_permission's
    callers pass plain "view"-style names. field_to_action normalizes the can_-prefixed
    form; the .get(..., field_name) fallback passes the plain form through unchanged.
    """
    field_to_action = {
        "can_view": "view",
        "can_create": "create",
        "can_edit": "edit",
        "can_delete": "delete",
    }

    action = field_to_action.get(field_name, field_name)

    async def _check(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db),
    ):
        token = credentials.credentials
        payload = decode_access_token(token)
        _reject_if_mfa_pending(payload)
        user_id: str = payload.get("sub", "")

        user = db.query(Users).filter(Users.UserID == user_id, Users.terminated_at.is_(None)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # PRODUCTION SAFETY: User MUST have tenant_id assigned
        if not user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User has no tenant assigned"
            )


        # Query role template permissions from database (DYNAMIC, not hard-coded)
        if not RoleTemplatePermissionService.has_permission(db, user.UserID, resource_name, action, user.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {field_name} access to '{resource_name}' required",
            )
        return user

    _check.__wros_permission__ = f"{resource_name}.{field_name}"
    _check.__wros_authn__ = "role_template_permission_check"
    return _check

