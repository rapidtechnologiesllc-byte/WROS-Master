from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import app.schemas as schema
from app.core.database import (
    SessionLocal,
    engine,
    check_candidate,
    check_user,
    get_db,
    authenticate_user,
    authenticate_candidate
)
from app.core.security import (
    verify_password,
    create_access_token,
    get_password_hash,
)
from app.core.dependencies import get_current_candidate, get_current_hr_or_admin
from app.core.mfa import (
    EMAIL_OTP_TTL_MINUTES,
    MFA_PENDING_TOKEN_MINUTES,
    email_otp_enforcement_enabled,
    generate_email_otp_code,
    hash_email_otp_code,
    mfa_enforcement_enabled,
    role_requires_email_otp,
    role_requires_mfa,
)
from app.services.email_service import EmailService
from app.models.candidate import Candidate
from app.models.user import Users
from app.schemas.auth import SignupRequest, SignupResponse, LoginRequest, LoginResponse, CandidateLoginRequest, CandidateLoginResponse, UnifiedLoginRequest, UnifiedLoginResponse
from app.utils.uniq_id_generator import candidate_id_generator, generate_password, user_id_generator

router = APIRouter(prefix="/auth", tags=["auth"])

# 2026-07-23 -- this endpoint is public (see auth_middleware.PUBLIC_ROUTES)
# and previously trusted request.user_role verbatim, so any anonymous
# caller could POST {"user_role": "Super User"} and get a fully
# privileged account with zero approval. Every self-signup now gets
# the lowest-privilege real role regardless of what the caller asked
# for; a Super User/Admin promotes them afterward via the RBAC screen,
# same as any other privilege grant in this system. The request schema
# still accepts user_role for backward compatibility with existing
# callers, it's just never trusted.
SELF_SIGNUP_DEFAULT_ROLE = "Employee"


@router.post("/v1/signup", response_model=SignupResponse)
def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """
    Create a new user account

    Args:
        request: SignupRequest containing user details
        db: Database session

    Returns:
        SignupResponse with success message

    Raises:
        HTTPException: If user with email already exists
    """
    # Check if user already exists
    existing = check_user(db, request.user_email)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Account already exists with email {request.user_email}"
        )

    # Generate unique ID and hash password
    user_id = user_id_generator()
    hashed_password = get_password_hash(request.user_password)

    # Create new user with correct field names matching Users model.
    # UserRole is deliberately NOT request.user_role -- see
    # SELF_SIGNUP_DEFAULT_ROLE above.
    user = Users(
        UserID=user_id,
        UserName=request.user_name,
        UserEmail=request.user_email,
        UserPassword=hashed_password,
        UserRole=SELF_SIGNUP_DEFAULT_ROLE,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return SignupResponse(response="User created successfully")
    




@router.post("/login")
def unified_login(request: UnifiedLoginRequest, db: Session = Depends(get_db)):
    """Unified login endpoint - authenticate and return token"""
    from app.core.logging import logger

    try:
        logger.warning(f"[LOGIN] Step 1: Calling authenticate_user for {request.email}")
        # Try authenticating as a User
        user = authenticate_user(db, request.email, request.password)
        logger.warning(f"[LOGIN] Step 2: authenticate_user returned: {type(user).__name__ if user else 'False'}")

        if user:
            logger.warning(f"[LOGIN] Step 3: User authenticated, type={type(user).__name__}")
            logger.warning(f"[LOGIN] Step 4: User object attributes: {dir(user)[:5]}")  # First 5 attributes

            logger.warning(f"[LOGIN] Step 5: Getting user_role via getattr")
            user_role = getattr(user, 'UserRole', 'Employee')
            logger.warning(f"[LOGIN] Step 6: user_role={user_role}")

            logger.warning(f"[LOGIN] Step 7: Fetching user roles and permissions")
            from app.models.rbac import Role, RolePermission, Permission
            from app.models.user import UserRole

            # Get all roles for this user (from user_roles junction table)
            user_roles_records = db.query(UserRole).filter(UserRole.user_id == user.UserID).all()
            roles = [{"id": ur.role.id, "name": ur.role.name} for ur in user_roles_records if ur.role]

            # Get all permissions for this user (union of all role permissions)
            permissions_set = set()
            for ur in user_roles_records:
                if ur.role:
                    role_perms = db.query(RolePermission).filter(
                        RolePermission.role_id == ur.role.id
                    ).all()
                    for rp in role_perms:
                        if rp.permission:
                            permissions_set.add(rp.permission.name)

            permissions = list(permissions_set)

            logger.warning(f"[LOGIN] Step 8: Creating access token")
            access_token = create_access_token(
                data={
                    "sub": user.UserEmail,
                    "type": user_role,
                    "name": user.UserName or "",
                    "roles": roles,
                    "permissions": permissions,
                }
            )
            logger.warning(f"[LOGIN] Step 9: Token created, length={len(access_token)}")

            logger.warning(f"[LOGIN] Step 10: Returning response with {len(roles)} roles and {len(permissions)} permissions")
            return {
                "entity_type": "user",
                "access_token": access_token,
                "is_first_time": False,
                "user_role": user_role,
                "user_name": user.UserName or "",
                "user_email": user.UserEmail,
                "roles": roles,
                "permissions": permissions,
                "business_unit_id": user.business_unit_id,
            }

        # Try authenticating as a Candidate
        candidate = authenticate_candidate(db, request.email, request.password)
        if candidate:
            name_parts = [
                getattr(candidate, 'candidateFirstName', ''),
                getattr(candidate, 'candidateMiddleName', ''),
                getattr(candidate, 'candidateLastName', ''),
            ]
            candidate_name = " ".join(filter(None, name_parts)) or ""

            access_token = create_access_token(
                data={
                    "sub": candidate.candidateID,
                    "type": "candidate",
                }
            )
            return {
                "entity_type": "candidate",
                "access_token": access_token,
                "is_first_time": False,
                "candidate_id": candidate.candidateID,
                "candidate_name": candidate_name,
                "candidate_email": candidate.candidateEmail,
            }

        # No match
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()[:500]
        }


@router.get("/me")
def get_current_user(
    current_user: Users = Depends(get_current_hr_or_admin)
):
    """
    Get the current authenticated user's information.

    Returns:
        Current user details including ID, name, email, and role
    """
    return {
        "user_id": current_user.UserID,
        "user_name": current_user.UserName,
        "user_email": current_user.UserEmail,
        "user_role": current_user.UserRole,
    }
