# 2026-08-17: Fixed PostgreSQL column quoting in unified_login
from datetime import datetime
import logging
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials
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
    create_refresh_token,
    get_password_hash,
    security,
    decode_access_token
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
from app.services.role_template_permission_service import RoleTemplatePermissionService
from app.models.candidate import Candidate
from app.models.user import Users
from app.schemas.auth import SignupRequest, SignupResponse
from app.contracts import UnifiedLoginRequest, UnifiedLoginResponse, ValidateEmailRequest, validate_login_request, validate_login_response
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

    PUBLIC ENDPOINT - no authentication required (see auth_middleware.PUBLIC_ROUTES)

    Args:
        request: SignupRequest containing user details
        db: Database session

    Returns:
        SignupResponse with success message

    Raises:
        HTTPException: If user with email already exists
    """
    # Check if user already exists (defensive: check both ways)
    existing = check_user(db, request.user_email)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Account already exists with email {request.user_email}"
        )

    # Double-check with direct query to ensure user doesn't exist
    try:
        duplicate = db.query(Users).filter(Users.UserEmail == request.user_email.lower()).first()
        if duplicate:
            raise HTTPException(
                status_code=400,
                detail=f"Account already exists with email {request.user_email}"
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error(f"Failed to check user existence: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to process signup. Please try again."
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

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to create user account. Please try again later."
        )

    return SignupResponse(response="User created successfully")
    
@router.post("/validate-email")
def validate_email(request: ValidateEmailRequest, db: Session = Depends(get_db)):
    """
    Validate if an email exists as an employee user.
    Returns {exists: true/false} so frontend can show appropriate error.
    Password field is optional (only used if provided for Step 2).

    PUBLIC ENDPOINT - no authentication required (see auth_middleware.PUBLIC_ROUTES)
    """
    from sqlalchemy import text

    if not request or not request.email:
        raise HTTPException(
            status_code=400,
            detail="Email is required"
        )

    email = request.email.strip().lower()
    user = check_user(db, email)

    # Reject users without a role template (must have permissions)
    if user:
        # Explicitly query for role_template_id to ensure it's loaded
        try:
            role_template_id = db.execute(
                text('SELECT role_template_id FROM users WHERE "UserEmail" = :email'),
                {"email": email}
            ).scalar()

            if role_template_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="Your user account doesn't have permissions loaded. Please reach out to help desk.",
                )
        except Exception as e:
            logger.error(f"Error validating email {email}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Failed to validate email. Please try again later."
            )

    return {"exists": bool(user)}

@router.post("/login", response_model=UnifiedLoginResponse)
def unified_login(request: UnifiedLoginRequest, db: Session = Depends(get_db)):
    """
    Unified login endpoint.

    Accepts a single email + password and automatically determines whether
    the credentials belong to a **User** (HR / Admin / etc.) or a **Candidate**.
    The response includes an `entity_type` field ("user" or "candidate") so
    the frontend can route accordingly.

    PUBLIC ENDPOINT - no authentication required (see auth_middleware.PUBLIC_ROUTES)

    Raises:
        HTTPException 401: If credentials do not match any user or candidate.
    """
    if not request or not request.email or not request.password:
        raise HTTPException(
            status_code=400,
            detail="Email and password are required"
        )
    from app.core.logging import logger
    import os

    db_url = os.getenv("DATABASE_URL", "NOT SET")
    logger.warning(f"[LOGIN] === START === email='{request.email}' | DATABASE_URL='{db_url[:50]}...'")
    logger.warning(f"[LOGIN] unified_login attempt for email='{request.email}'")

    # ── 1. Try authenticating as a User first ───────────────────
    user = None
    try:
        logger.warning(f"[LOGIN] Calling authenticate_user with email='{request.email}'")
        user = authenticate_user(db, request.email, request.password)
        logger.warning(f"[LOGIN] authenticate_user returned: {type(user).__name__ if user else 'None'}")
        if user:
            logger.warning(f"[LOGIN] User authenticated: {user.UserEmail}, role_template_id={user.role_template_id}")
    except Exception as e:
        logger.error(f"[LOGIN] authenticate_user threw exception: {str(e)}", exc_info=True)
        # Continue to candidate auth below
        user = None
    if user:
        # Defensive null check: user must have required attributes
        if not user or not user.UserID or not user.UserEmail:
            raise HTTPException(
                status_code=500,
                detail="User record incomplete. Please contact help desk."
            )

        # MANDATORY PERMISSION ENFORCEMENT: User MUST have a role_template_id to proceed
        # This permission check happens immediately after authentication (not optional)
        logger.warning(f"[LOGIN] Checking role_template_id: hasattr={hasattr(user, 'role_template_id')}, value={getattr(user, 'role_template_id', 'MISSING')}")

        if not hasattr(user, 'role_template_id'):
            logger.error(f"[LOGIN] PERMISSION CHECK FAILED: role_template_id attribute missing")
            raise HTTPException(
                status_code=403,
                detail="ERROR-001: role_template_id attribute missing"
            )

        if not user.role_template_id:
            logger.error(f"[LOGIN] PERMISSION CHECK FAILED: role_template_id is falsy: {user.role_template_id}")
            raise HTTPException(
                status_code=403,
                detail="ERROR-002: role_template_id is falsy"
            )

        # role_template_id is mandatory and already validated above
        # Use the validated value from authenticated user object
        from sqlalchemy import text
        from app.models.role_template import RoleTemplate

        # Assign from already-validated user attribute
        role_template_id = user.role_template_id

        # Get role template name - user MUST have a valid role_template
        user_role = "User"
        try:
            rt = db.query(RoleTemplate).filter(RoleTemplate.id == role_template_id).first()
            if not rt:
                logger.error(f"[LOGIN] Role template {role_template_id} not found in DB")
                raise HTTPException(
                    status_code=403,
                    detail="ERROR-003: RoleTemplate not found"
                )
            if not hasattr(rt, 'name'):
                logger.error(f"[LOGIN] RoleTemplate {role_template_id} has no name attribute")
                raise HTTPException(
                    status_code=403,
                    detail="ERROR-004: RoleTemplate has no name attr"
                )
            if not rt.name:
                logger.error(f"[LOGIN] RoleTemplate {role_template_id} has empty name: '{rt.name}'")
                raise HTTPException(
                    status_code=403,
                    detail="ERROR-005: RoleTemplate name is empty"
                )
            user_role = rt.name
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[LOGIN] Failed to fetch role template: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=403,
                detail="Your user account doesn't have permissions loaded. Please reach out to help desk."
            )

        # Fallback role check for legacy compatibility (user.UserRole as backup)
        if user and hasattr(user, 'UserRole') and user.UserRole and user_role == "User":
            user_role = user.UserRole
        # Phase 1 B3 -- gate is off by default (mfa_enforcement_enabled())
        # and only applies to MFA_REQUIRED_ROLES even when on. See
        # app.core.mfa's module docstring: do not enable the env flag
        # until the frontend has a screen for this, or every Super
        # User / BU Head account gets locked out with no way through.
        from datetime import timedelta
        totp_gate = mfa_enforcement_enabled() and role_requires_mfa(user_role)
        # Backlog item, 2026-08-05: email OTP is a SEPARATE, independently-
        # off-by-default gate that SUPPLEMENTS the TOTP one above -- see
        # app.core.mfa's EMAIL_OTP_* section for why this isn't just a
        # wider MFA_REQUIRED_ROLES. Either gate alone is enough to route
        # into the mfa_pending flow.
        email_otp_gate = email_otp_enforcement_enabled() and role_requires_email_otp(user_role)
        if totp_gate or email_otp_gate:
            pending_token = create_access_token(
                data={
                    "sub": user.UserID,
                    "email": user.UserEmail,
                    "type": "user",
                    "mfa_pending": True
                },
                expires_delta=timedelta(minutes=MFA_PENDING_TOKEN_MINUTES),
            )

            if email_otp_gate:
                # Unlike TOTP (user generates their own code from an
                # already-enrolled authenticator app), an email code
                # must be proactively issued and sent by us right now --
                # there's nothing for the user to produce on their own.
                code = generate_email_otp_code()
                try:
                    user.email_otp_code_hash = hash_email_otp_code(code)
                    user.email_otp_expires_at = datetime.utcnow() + timedelta(minutes=EMAIL_OTP_TTL_MINUTES)
                    db.add(user)
                    db.commit()
                except Exception as e:
                    db.rollback()
                    logger.error(f"[LOGIN] Failed to store email OTP: {str(e)}", exc_info=True)
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to generate verification code. Please try again."
                    )

                try:
                    user_email = user.UserEmail if user and hasattr(user, 'UserEmail') else request.email
                    user_name = user.UserName if user and hasattr(user, 'UserName') and user.UserName else user_email
                    EmailService.send_event_notification(
                        to_email=user_email,
                        recipient_name=user_name,
                        event_type="action_required",
                        heading="Your BlitzenX WROS verification code",
                        message=(
                            f"Your one-time verification code is <strong>{code}</strong>. "
                            f"It expires in {EMAIL_OTP_TTL_MINUTES} minutes. If you didn't "
                            f"just try to sign in, you can ignore this email."
                        ),
                    )
                except Exception:
                    # A failed send must never leak the code into the API
                    # response or logs -- the user can request a resend
                    # via /auth/mfa/email/resend instead of blocking login.
                    pass

            # Get user permissions for frontend navigation
            user_permissions = []
            try:
                user_permissions = RoleTemplatePermissionService.get_user_permissions(
                    db, user.UserID, user.tenant_id if hasattr(user, 'tenant_id') else None
                )
            except Exception as e:
                logger.error(f"[LOGIN] Error fetching permissions: {str(e)}", exc_info=True)
                if "no role template" in str(e).lower():
                    raise HTTPException(
                        status_code=403,
                        detail="Your user account doesn't have permissions loaded. Please reach out to help desk.",
                    )
                # Non-critical: continue with empty permissions
                user_permissions = []

            return UnifiedLoginResponse(
                entity_type="user",
                access_token=pending_token,
                is_first_time=False,
                user_role=user_role,
                user_name=user.UserName if (user and hasattr(user, 'UserName') and user.UserName) else "",
                user_email=user.UserEmail if (user and hasattr(user, 'UserEmail')) else request.email,
                permissions=user_permissions,
                mfa_required=bool(user.mfa_enabled) if (user and hasattr(user, 'mfa_enabled') and totp_gate) else False,
                mfa_setup_required=(not bool(user.mfa_enabled)) if (user and hasattr(user, 'mfa_enabled') and totp_gate) else False,
                email_otp_required=email_otp_gate,
            )

        # Standard (non-MFA) login flow
        access_token = create_access_token(
            data={
                "sub": user.UserID,
                "email": user.UserEmail,
                "type": "user",
                "name": user.UserName if (hasattr(user, 'UserName') and user.UserName) else "",
            }
        )

        # Create refresh token for automatic token renewal
        refresh_token = create_refresh_token(
            data={
                "sub": user.UserID,
                "email": user.UserEmail,
                "type": "refresh",
            }
        )

        # Get user permissions for frontend navigation
        user_permissions = []
        try:
            user_permissions = RoleTemplatePermissionService.get_user_permissions(
                db, user.UserID, user.tenant_id if hasattr(user, 'tenant_id') else None
            )
        except Exception as e:
            logger.error(f"[LOGIN] Error fetching permissions: {str(e)}", exc_info=True)
            if "no role template" in str(e).lower():
                raise HTTPException(
                    status_code=403,
                    detail="Your user account doesn't have permissions loaded. Please reach out to help desk.",
                )
            # Non-critical: continue with empty permissions
            user_permissions = []

        # Check if password reset is required (first login with system-generated password)
        force_password_reset = getattr(user, 'password_reset_required', False)

        return UnifiedLoginResponse(
            entity_type="user",
            access_token=access_token,
            refresh_token=refresh_token,
            is_first_time=False,
            user_role=user_role,
            user_name=user.UserName if (user and hasattr(user, 'UserName') and user.UserName) else "",
            user_email=user.UserEmail if (user and hasattr(user, 'UserEmail')) else request.email,
            permissions=user_permissions,
            force_password_reset=force_password_reset,
        )

    # ── 2. Fall back to Candidate ────────────────────────────────
    candidate = None
    try:
        candidate = authenticate_candidate(db, request.email, request.password)
    except Exception as e:
        logger.error(f"[LOGIN] authenticate_candidate threw exception: {str(e)}", exc_info=True)
        candidate = None

    if candidate:
        # Defensive null checks
        if not candidate or not candidate.candidateID or not candidate.candidateEmail:
            raise HTTPException(
                status_code=500,
                detail="Candidate record incomplete. Please contact help desk."
            )

        # Build candidate name from parts - defensive access
        name_parts = []
        if candidate and hasattr(candidate, 'candidateFirstName') and candidate.candidateFirstName:
            name_parts.append(candidate.candidateFirstName)
        if candidate and hasattr(candidate, 'candidateMiddleName') and candidate.candidateMiddleName:
            name_parts.append(candidate.candidateMiddleName)
        if candidate and hasattr(candidate, 'candidateLastName') and candidate.candidateLastName:
            name_parts.append(candidate.candidateLastName)
        candidate_name = " ".join(filter(None, name_parts)) or ""

        is_first_time = (
            not candidate.candidateIsVerified
            if (candidate and hasattr(candidate, 'candidateIsVerified') and candidate.candidateIsVerified is not None)
            else True
        )

        # Backlog item, 2026-08-05 (wros_email_2fa_backlog, candidate
        # half): opted-in candidates get a pending token + emailed code
        # instead of a full session, same shape as the internal-user
        # email-OTP gate in the branch above but candidate-scoped.
        if candidate and hasattr(candidate, 'email_2fa_opted_in') and candidate.email_2fa_opted_in:
            from datetime import timedelta as _timedelta
            code = generate_email_otp_code()
            try:
                candidate.email_otp_code_hash = hash_email_otp_code(code)
                candidate.email_otp_expires_at = datetime.utcnow() + _timedelta(minutes=EMAIL_OTP_TTL_MINUTES)
                db.add(candidate)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"[LOGIN] Failed to store candidate OTP: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Failed to generate verification code. Please try again."
                )

            try:
                candidate_email = candidate.candidateEmail if (candidate and hasattr(candidate, 'candidateEmail')) else request.email
                EmailService.send_event_notification(
                    to_email=candidate_email,
                    recipient_name=candidate_name or candidate_email,
                    event_type="action_required",
                    heading="Your BlitzenX verification code",
                    message=(
                        f"Your one-time verification code is <strong>{code}</strong>. "
                        f"It expires in {EMAIL_OTP_TTL_MINUTES} minutes."
                    ),
                )
            except Exception:
                pass  # see the internal-user branch above -- never leak the code into logs/response on send failure

            pending_token = create_access_token(
                data={"sub": candidate.candidateID, "type": "candidate", "candidate_otp_pending": True},
                expires_delta=_timedelta(minutes=MFA_PENDING_TOKEN_MINUTES),
            )
            return UnifiedLoginResponse(
                entity_type="candidate",
                access_token=pending_token,
                is_first_time=is_first_time,
                candidate_id=candidate.candidateID,
                candidate_role=candidate.candidateRole if (hasattr(candidate, 'candidateRole') and candidate.candidateRole) else "Candidate",
                candidate_name=candidate_name,
                candidate_email=candidate.candidateEmail,
                candidate_mobile=candidate.candidateMobile if (hasattr(candidate, 'candidateMobile')) else None,
                candidate_otp_required=True,
            )

        # Standard candidate login (non-OTP)
        access_token = create_access_token(
            data={
                "sub": candidate.candidateID,
                "type": "candidate",
            }
        )

        # Create refresh token for automatic token renewal
        refresh_token = create_refresh_token(
            data={
                "sub": candidate.candidateID,
                "type": "refresh",
            }
        )

        return UnifiedLoginResponse(
            entity_type="candidate",
            access_token=access_token,
            refresh_token=refresh_token,
            is_first_time=is_first_time,
            candidate_id=candidate.candidateID,
            candidate_role=candidate.candidateRole if (hasattr(candidate, 'candidateRole') and candidate.candidateRole) else "Candidate",
            candidate_name=candidate_name,
            candidate_email=candidate.candidateEmail,
            candidate_mobile=candidate.candidateMobile if (hasattr(candidate, 'candidateMobile')) else None,
            show_2fa_opt_in_popup=(not (hasattr(candidate, 'email_2fa_opted_in') and candidate.email_2fa_opted_in is not None)),
        )

    # ── 3. Neither matched ───────────────────────────────────────
    raise HTTPException(
        status_code=401,
        detail="Invalid email or password",
    )

@router.post("/v1/refresh", response_model=UnifiedLoginResponse)
def refresh_token_endpoint(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin)
):
    """
    Refresh an access token using a refresh token.

    Accepts: Authorization: Bearer {refresh_token}
    Returns: New access token + new refresh token

    Raises:
        HTTPException 401: If refresh token is invalid or expired
    """
    from app.core.security_local import verify_token

    if not credentials:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    refresh_token_str = credentials.credentials
    if not refresh_token_str:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    # Verify refresh token
    payload = None
    try:
        from app.core.security import verify_token as verify_jwt
        payload = verify_jwt(refresh_token_str)
    except Exception as e:
        logger.error(f"[REFRESH] Token verification failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Verify it's actually a refresh token (has type: refresh)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token is not a refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Determine if this is a user or candidate
    user = None
    candidate = None
    try:
        user = check_user(db, None, user_id)
        candidate = check_candidate(db, None, user_id) if not user else None
    except Exception as e:
        logger.error(f"[REFRESH] Failed to lookup user/candidate: {str(e)}", exc_info=True)
        raise HTTPException(status_code=401, detail="User not found")

    if user:
        # Defensive null checks
        if not user or not user.UserID or not user.UserEmail:
            raise HTTPException(
                status_code=500,
                detail="User record incomplete. Please contact help desk."
            )

        # MANDATORY: User MUST have a role_template_id (cannot refresh without permissions)
        if not hasattr(user, 'role_template_id') or not user.role_template_id:
            raise HTTPException(
                status_code=403,
                detail="Your user account doesn't have permissions loaded. Please reach out to help desk."
            )

        # Create new access token for user
        access_token = create_access_token(
            data={
                "sub": user.UserID,
                "email": user.UserEmail,
                "type": "user",
                "name": user.UserName if (hasattr(user, 'UserName') and user.UserName) else "",
            }
        )

        # Create new refresh token (rotate the refresh token for security)
        new_refresh_token = create_refresh_token(
            data={
                "sub": user.UserID,
                "email": user.UserEmail,
                "type": "refresh",
            }
        )

        # Get user permissions
        user_permissions = []
        try:
            user_permissions = RoleTemplatePermissionService.get_user_permissions(
                db, user.UserID, user.tenant_id if hasattr(user, 'tenant_id') else None
            )
        except Exception as e:
            logger.error(f"[REFRESH] Error fetching permissions: {str(e)}", exc_info=True)
            user_permissions = []

        # Get user role
        user_role = "User"
        if user and hasattr(user, 'UserRole') and user.UserRole:
            user_role = user.UserRole

        if user and hasattr(user, 'role_template_id') and user.role_template_id:
            try:
                from app.models.role_template import RoleTemplate
                rt = db.query(RoleTemplate).filter(RoleTemplate.id == user.role_template_id).first()
                if rt and hasattr(rt, 'name') and rt.name:
                    user_role = rt.name
            except Exception as e:
                logger.error(f"[REFRESH] Failed to fetch role template: {str(e)}", exc_info=True)

        logger.info(f"[REFRESH] Successfully refreshed token for user {user.UserID}")

        return UnifiedLoginResponse(
            entity_type="user",
            access_token=access_token,
            refresh_token=new_refresh_token,
            is_first_time=False,
            user_role=user_role,
            user_name=user.UserName if (user and hasattr(user, 'UserName') and user.UserName) else "",
            user_email=user.UserEmail,
            permissions=user_permissions,
        )

    elif candidate:
        # Defensive null checks
        if not candidate or not candidate.candidateID or not candidate.candidateEmail:
            raise HTTPException(
                status_code=500,
                detail="Candidate record incomplete. Please contact help desk."
            )

        # Create new access token for candidate
        access_token = create_access_token(
            data={
                "sub": candidate.candidateID,
                "type": "candidate",
            }
        )

        # Create new refresh token
        new_refresh_token = create_refresh_token(
            data={
                "sub": candidate.candidateID,
                "type": "refresh",
            }
        )

        # Build candidate name - defensive access
        name_parts = []
        if candidate and hasattr(candidate, 'candidateFirstName') and candidate.candidateFirstName:
            name_parts.append(candidate.candidateFirstName)
        if candidate and hasattr(candidate, 'candidateMiddleName') and candidate.candidateMiddleName:
            name_parts.append(candidate.candidateMiddleName)
        if candidate and hasattr(candidate, 'candidateLastName') and candidate.candidateLastName:
            name_parts.append(candidate.candidateLastName)
        candidate_name = " ".join(filter(None, name_parts)) or ""

        logger.info(f"[REFRESH] Successfully refreshed token for candidate {candidate.candidateID}")

        return UnifiedLoginResponse(
            entity_type="candidate",
            access_token=access_token,
            refresh_token=new_refresh_token,
            is_first_time=False,
            candidate_id=candidate.candidateID,
            candidate_role=candidate.candidateRole if (hasattr(candidate, 'candidateRole') and candidate.candidateRole) else "Candidate",
            candidate_name=candidate_name,
            candidate_email=candidate.candidateEmail,
            candidate_mobile=candidate.candidateMobile if (hasattr(candidate, 'candidateMobile')) else None,
        )

    else:
        raise HTTPException(status_code=401, detail="User or candidate not found")

@router.post("/reset-password")
def reset_password(
    request: dict,
    current_user: Users = Depends(get_current_hr_or_admin),
    db: Session = Depends(get_db)
):
    """
    Reset user password (first login or regular password change).
    Requires access token and new password.

    Protected endpoint - requires authentication and HR/Admin role
    """

    if not request:
        raise HTTPException(status_code=400, detail="Request body is required")

    user_id = request.get("user_id")
    new_password = request.get("new_password")

    if not user_id or not new_password:
        raise HTTPException(status_code=400, detail="user_id and new_password required")

    if not isinstance(new_password, str) or len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Get user
    user = None
    try:
        user = db.query(Users).filter(Users.UserID == user_id).first()
    except Exception as e:
        logger.error(f"[RESET_PASSWORD] Failed to query user: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error. Please try again later.")

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Defensive check for required attributes
    if not hasattr(user, 'UserPassword'):
        logger.error(f"[RESET_PASSWORD] User record incomplete (missing UserPassword)")
        raise HTTPException(status_code=500, detail="User record incomplete. Please contact help desk.")

    # Update password
    try:
        user.UserPassword = get_password_hash(new_password)
        user.password_reset_required = False  # Mark password reset as complete
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error(f"[RESET_PASSWORD] Failed to update password: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to reset password. Please try again later.")

    return {"status": "success", "message": "Password reset successfully"}
