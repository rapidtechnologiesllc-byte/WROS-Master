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
from app.core.security_local import (
    verify_password,
    create_access_token,
    create_refresh_token,
    get_password_hash,
)
from app.core.dependencies import get_current_candidate, get_current_hr_or_admin
from app.core.security import security, decode_access_token
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
    
@router.post("/validate-email")
def validate_email(request: ValidateEmailRequest, db: Session = Depends(get_db)):
    """
    Validate if an email exists as an employee user.
    Returns {exists: true/false} so frontend can show appropriate error.
    Password field is optional (only used if provided for Step 2).
    """
    email = request.email.strip().lower()
    user = check_user(db, email)
    return {"exists": bool(user)}


@router.post("/login", response_model=UnifiedLoginResponse)
def unified_login(request: UnifiedLoginRequest, db: Session = Depends(get_db)):
    """
    Unified login endpoint.

    Accepts a single email + password and automatically determines whether
    the credentials belong to a **User** (HR / Admin / etc.) or a **Candidate**.
    The response includes an `entity_type` field ("user" or "candidate") so
    the frontend can route accordingly.

    Raises:
        HTTPException 401: If credentials do not match any user or candidate.
    """
    from app.core.logging import logger
    import os

    db_url = os.getenv("DATABASE_URL", "NOT SET")
    logger.warning(f"[LOGIN] === START === email='{request.email}' | DATABASE_URL='{db_url[:50]}...'")
    logger.warning(f"[LOGIN] unified_login attempt for email='{request.email}'")

    # ── 1. Try authenticating as a User first ───────────────────
    user = authenticate_user(db, request.email, request.password)
    logger.info(f"[LOGIN] authenticate_user returned: {type(user).__name__ if user else 'False'}")
    if user:
        # Get authoritative role_template_id from database (ORM not loading correctly)
        from sqlalchemy import text
        role_template_id = db.execute(text('SELECT role_template_id FROM users WHERE "UserEmail" = :email'), {"email": request.email}).scalar()

        # Get role template name
        user_role = user.UserRole or "User"  # Fall back to UserRole field or "User"
        if role_template_id:
            from app.models.role_template import RoleTemplate
            rt = db.query(RoleTemplate).filter(RoleTemplate.id == role_template_id).first()
            if rt:
                user_role = rt.name
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
                user.email_otp_code_hash = hash_email_otp_code(code)
                user.email_otp_expires_at = datetime.utcnow() + timedelta(minutes=EMAIL_OTP_TTL_MINUTES)
                db.add(user)
                db.commit()
                try:
                    EmailService.send_event_notification(
                        to_email=user.UserEmail,
                        recipient_name=user.UserName or user.UserEmail,
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
            try:
                user_permissions = RoleTemplatePermissionService.get_user_permissions(
                    db, user.UserID, user.tenant_id
                )
            except Exception as e:
                logger.error(f"Error: {str(e)}", exc_info=True)
                if "no role template" in str(e).lower():
                    raise HTTPException(
                        status_code=403,
                        detail="Your user account doesn't have permissions loaded. Please reach out to help desk.",
                    )
                raise

            return UnifiedLoginResponse(
                entity_type="user",
                access_token=pending_token,
                is_first_time=False,
                user_role=user_role,
                user_name=user.UserName or "",
                user_email=user.UserEmail,
                permissions=user_permissions,
                mfa_required=bool(user.mfa_enabled) if totp_gate else False,
                mfa_setup_required=(not bool(user.mfa_enabled)) if totp_gate else False,
                email_otp_required=email_otp_gate,
            )

        access_token = create_access_token(
            data={
                "sub": user.UserID,
                "email": user.UserEmail,
                "type": "user",
                "name": user.UserName,
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
        try:
            user_permissions = RoleTemplatePermissionService.get_user_permissions(
                db, user.UserID, user.tenant_id
            )
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            if "no role template" in str(e).lower():
                raise HTTPException(
                    status_code=403,
                    detail="Your user account doesn't have permissions loaded. Please reach out to help desk.",
                )
            raise

        return UnifiedLoginResponse(
            entity_type="user",
            access_token=access_token,
            refresh_token=refresh_token,
            is_first_time=False,
            user_role=user_role,
            user_name=user.UserName or "",
            user_email=user.UserEmail,
            permissions=user_permissions,
        )

    # ── 2. Fall back to Candidate ────────────────────────────────
    candidate = authenticate_candidate(db, request.email, request.password)
    if candidate:
        name_parts = [
            candidate.candidateFirstName,
            candidate.candidateMiddleName,
            candidate.candidateLastName,
        ]
        candidate_name = " ".join(filter(None, name_parts)) or ""
        is_first_time = (
            not candidate.candidateIsVerified
            if candidate.candidateIsVerified is not None
            else True
        )

        # Backlog item, 2026-08-05 (wros_email_2fa_backlog, candidate
        # half): opted-in candidates get a pending token + emailed code
        # instead of a full session, same shape as the internal-user
        # email-OTP gate in the branch above but candidate-scoped.
        if candidate.email_2fa_opted_in:
            from datetime import timedelta as _timedelta
            code = generate_email_otp_code()
            candidate.email_otp_code_hash = hash_email_otp_code(code)
            candidate.email_otp_expires_at = datetime.utcnow() + _timedelta(minutes=EMAIL_OTP_TTL_MINUTES)
            db.add(candidate)
            db.commit()
            try:
                EmailService.send_event_notification(
                    to_email=candidate.candidateEmail,
                    recipient_name=candidate_name or candidate.candidateEmail,
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
                candidate_role=candidate.candidateRole or "Candidate",
                candidate_name=candidate_name,
                candidate_email=candidate.candidateEmail,
                candidate_mobile=candidate.candidateMobile,
                candidate_otp_required=True,
            )

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
            candidate_role=candidate.candidateRole or "Candidate",
            candidate_name=candidate_name,
            candidate_email=candidate.candidateEmail,
            candidate_mobile=candidate.candidateMobile,
            show_2fa_opt_in_popup=candidate.email_2fa_opted_in is None,
        )

    # ── 3. Neither matched ───────────────────────────────────────
    raise HTTPException(
        status_code=401,
        detail="Invalid email or password",
    )


@router.post("/v1/refresh", response_model=UnifiedLoginResponse)
def refresh_token_endpoint(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """
    Refresh an access token using a refresh token.

    Accepts: Authorization: Bearer {refresh_token}
    Returns: New access token + new refresh token

    Raises:
        HTTPException 401: If refresh token is invalid or expired
    """
    from app.core.security_local import verify_token
    from app.core.logging import logger

    if not credentials:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    refresh_token_str = credentials.credentials

    # Verify refresh token
    payload = verify_token(refresh_token_str)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Verify it's actually a refresh token (has type: refresh)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token is not a refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Determine if this is a user or candidate
    user = check_user(db, None, user_id)
    candidate = check_candidate(db, None, user_id) if not user else None

    if user:
        # Create new access token for user
        access_token = create_access_token(
            data={
                "sub": user.UserID,
                "email": user.UserEmail,
                "type": "user",
                "name": user.UserName,
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
        user_permissions = RoleTemplatePermissionService.get_user_permissions(
            db, user.UserID, user.tenant_id
        )

        # Get user role
        user_role = user.UserRole or "User"
        if user.role_template_id:
            from app.models.role_template import RoleTemplate
            rt = db.query(RoleTemplate).filter(RoleTemplate.id == user.role_template_id).first()
            if rt:
                user_role = rt.name

        logger.info(f"[REFRESH] Successfully refreshed token for user {user.UserID}")

        return UnifiedLoginResponse(
            entity_type="user",
            access_token=access_token,
            refresh_token=new_refresh_token,
            is_first_time=False,
            user_role=user_role,
            user_name=user.UserName or "",
            user_email=user.UserEmail,
            permissions=user_permissions,
        )

    elif candidate:
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

        name_parts = [
            candidate.candidateFirstName,
            candidate.candidateMiddleName,
            candidate.candidateLastName,
        ]
        candidate_name = " ".join(filter(None, name_parts)) or ""

        logger.info(f"[REFRESH] Successfully refreshed token for candidate {candidate.candidateID}")

        return UnifiedLoginResponse(
            entity_type="candidate",
            access_token=access_token,
            refresh_token=new_refresh_token,
            is_first_time=False,
            candidate_id=candidate.candidateID,
            candidate_role=candidate.candidateRole or "Candidate",
            candidate_name=candidate_name,
            candidate_email=candidate.candidateEmail,
            candidate_mobile=candidate.candidateMobile,
        )

    else:
        raise HTTPException(status_code=401, detail="User or candidate not found")
