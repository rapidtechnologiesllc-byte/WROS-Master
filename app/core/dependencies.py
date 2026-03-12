from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token, security
from app.models.user import Users
from app.models.candidate import Candidate


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

    user_id: str = payload.get("sub")
    user_type: str = payload.get("type", "candidate")

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if user_type == "user":
        user = db.query(Users).filter(Users.UserID == user_id).first()
    else:
        user = db.query(Candidate).filter(Candidate.candidateID == user_id).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

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

    user_id: str = payload.get("sub")
    user_type: str = payload.get("type")

    if not user_id or user_type != "candidate":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized as candidate")

    candidate = db.query(Candidate).filter(Candidate.candidateID == user_id).first()
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

    user_id: str = payload.get("sub")
    user_type: str = payload.get("type", "").lower()

    if not user_id or user_type == "candidate":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # For Microsoft SSO users, 'sub' contains email
    user = db.query(Users).filter(Users.UserEmail == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

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

    user_id: str = payload.get("sub")
    user_type: str = payload.get("type", "").lower()

    if not user_id or user_type == "candidate":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    user = db.query(Users).filter(Users.UserEmail == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


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
        user_email: str = payload.get("sub", "")

        user = db.query(Users).filter(Users.UserEmail == user_email).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # Super User bypass — always has all permissions
        # Check both the legacy UserRole string AND the RBAC role relationship
        is_super_user = (
            (user.UserRole and user.UserRole.lower() == "super user")
            or (user.role and user.role.name and user.role.name.lower() == "super user")
        )
        if is_super_user:
            return user

        if not RBACService.has_permission(db, user.UserID, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: '{permission}' required",
            )
        return user

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
        user_email: str = payload.get("sub", "")

        user = db.query(Users).filter(Users.UserEmail == user_email).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

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

    return _check
