# 2026-08-17: Fixed PostgreSQL column quoting in unified_login
from datetime import datetime, timedelta
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
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
from app.core.dependencies import get_current_candidate, get_current_user, require_role_template_permission
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
from app.models.role_template import RoleTemplate
from app.schemas.auth import SignupRequest, SignupResponse
from app.contracts import UnifiedLoginRequest, UnifiedLoginResponse, ValidateEmailRequest
from app.utils.uniq_id_generator import user_id_generator, generate_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

SELF_SIGNUP_DEFAULT_ROLE = "Employee"


@router.post("/v1/signup", response_model=SignupResponse)
def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Create a new user account. PUBLIC ENDPOINT."""
    if not request:
        logger.error("Signup failed: request is None")
        raise HTTPException(status_code=400, detail="Request body is required")

    if not request.user_email or not request.user_name or not request.user_password:
        logger.error("Signup failed: missing required fields")
        raise HTTPException(status_code=400, detail="Email, name, and password are required")

    existing = check_user(db, request.user_email)
    if existing:
        logger.warning(f"Signup rejected: user exists {request.user_email}")
        raise HTTPException(status_code=400, detail=f"Account already exists with email {request.user_email}")

    try:
        duplicate = db.query(Users).filter(Users.UserEmail == request.user_email.lower()).first()
        if duplicate:
            logger.warning(f"Signup rejected: duplicate {request.user_email}")
            raise HTTPException(status_code=400, detail=f"Account already exists with email {request.user_email}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check user existence: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process signup. Please try again.")

    user_id = user_id_generator()
    hashed_password = get_password_hash(request.user_password)

    user = Users(
        UserID=user_id,
        UserName=request.user_name,
        UserEmail=request.user_email,
        UserPassword=hashed_password,
        UserRole=SELF_SIGNUP_DEFAULT_ROLE,
    )

    try:
        # Double-check no duplicate exists before adding
        existing = db.query(Users).filter(Users.UserEmail == user.UserEmail.lower()).first()
        if existing:
            logger.warning(f"Duplicate user detected during creation: {user.UserEmail}")
            raise HTTPException(status_code=400, detail=f"Account already exists with email {user.UserEmail}")

        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception as e:
        logger.error(f"Failed to create user: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create user account. Please try again later.")

    logger.info(f"User created successfully: {user_id}")
    return SignupResponse(response="User created successfully")


@router.post("/validate-email", response_model=dict)
def validate_email(request: ValidateEmailRequest, db: Session = Depends(get_db)):
    """Validate if an email exists as an employee user. PUBLIC ENDPOINT."""
    if not request or not request.email:
        logger.error("Email validation failed: email is required")
        raise HTTPException(status_code=400, detail="Email is required")

    email = request.email.strip().lower()
    user = None

    try:
        user = check_user(db, email)
    except Exception as e:
        logger.error(f"Failed to check user during email validation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to validate email. Please try again.")

    return {"exists": bool(user)}


@router.post("/login", response_model=UnifiedLoginResponse)
def unified_login(request: UnifiedLoginRequest, db: Session = Depends(get_db)):
    """Unified login endpoint. PUBLIC ENDPOINT."""
    if not request or not request.email or not request.password:
        logger.error("Login failed: missing email or password")
        raise HTTPException(status_code=400, detail="Email and password are required")

    logger.info(f"Login attempt for email={request.email}")

    user = None
    try:
        user = authenticate_user(db, request.email, request.password)
    except Exception as e:
        logger.error(f"User authentication failed: {e}", exc_info=True)
        user = None

    if user:
        if not user:
            logger.error("User is None after authentication")
            raise HTTPException(status_code=500, detail="User record is invalid. Please contact help desk.")

        if not hasattr(user, 'UserID') or not user.UserID:
            logger.error("User has no UserID")
            raise HTTPException(status_code=500, detail="User record incomplete. Please contact help desk.")

        if not hasattr(user, 'UserEmail') or not user.UserEmail:
            logger.error("User has no UserEmail")
            raise HTTPException(status_code=500, detail="User record incomplete. Please contact help desk.")

        if not hasattr(user, 'role_template_id') or not user.role_template_id:
            logger.error(f"Login rejected: user {user.UserID} has no role_template_id")
            raise HTTPException(
                status_code=403,
                detail="Your user account doesn't have permissions loaded. Please reach out to help desk."
            )

        role_template_id = user.role_template_id
        user_role = "User"

        try:
            rt = db.query(RoleTemplate).filter(RoleTemplate.id == role_template_id).first()
            if not rt:
                logger.error(f"Role template {role_template_id} not found")
                raise HTTPException(status_code=403, detail="Role template not found")
            if not hasattr(rt, 'name') or not rt.name:
                logger.error(f"Role template {role_template_id} has no name")
                raise HTTPException(status_code=403, detail="Role template has no name")
            user_role = rt.name
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch role template {role_template_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to load user role. Please try again.")

        totp_gate = mfa_enforcement_enabled() and role_requires_mfa(user_role)
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
                code = generate_email_otp_code()
                try:
                    user.email_otp_code_hash = hash_email_otp_code(code)
                    user.email_otp_expires_at = datetime.utcnow() + timedelta(minutes=EMAIL_OTP_TTL_MINUTES)
                    # User already in session from authenticate_user(), just commit the updates
                    db.commit()
                except Exception as e:
                    logger.error(f"Failed to store email OTP: {e}", exc_info=True)
                    db.rollback()
                    raise HTTPException(status_code=500, detail="Failed to generate verification code. Please try again.")

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
                            f"It expires in {EMAIL_OTP_TTL_MINUTES} minutes."
                        ),
                    )
                except Exception as e:
                    logger.error(f"Failed to send OTP email: {e}", exc_info=True)

            user_permissions = []
            try:
                user_permissions = RoleTemplatePermissionService.get_user_permissions(
                    db, user.UserID, user.tenant_id if hasattr(user, 'tenant_id') else None
                )
            except Exception as e:
                logger.error(f"Failed to fetch permissions: {e}", exc_info=True)
                user_permissions = []

            logger.info(f"Login MFA pending for user {user.UserID}")
            return UnifiedLoginResponse(
                entity_type="user",
                access_token=pending_token,
                is_first_time=False,
                user_role=user_role,
                user_name=user.UserName if hasattr(user, 'UserName') and user.UserName else "",
                user_email=user.UserEmail,
                permissions=user_permissions,
                mfa_required=bool(user.mfa_enabled) if hasattr(user, 'mfa_enabled') and totp_gate else False,
                mfa_setup_required=(not bool(user.mfa_enabled)) if hasattr(user, 'mfa_enabled') and totp_gate else False,
                email_otp_required=email_otp_gate,
            )

        access_token = create_access_token(
            data={
                "sub": user.UserID,
                "email": user.UserEmail,
                "type": "user",
                "name": user.UserName if hasattr(user, 'UserName') and user.UserName else "",
                "tenant_id": user.tenant_id,
                "role_template_id": user.role_template_id,
            }
        )

        refresh_token = create_refresh_token(
            data={
                "sub": user.UserID,
                "email": user.UserEmail,
                "type": "refresh",
            }
        )

        user_permissions = []
        try:
            user_permissions = RoleTemplatePermissionService.get_user_permissions(
                db, user.UserID, user.tenant_id if hasattr(user, 'tenant_id') else None
            )
        except Exception as e:
            logger.error(f"Failed to fetch permissions: {e}", exc_info=True)
            user_permissions = []

        force_password_reset = getattr(user, 'password_reset_required', False)

        logger.info(f"Login successful for user {user.UserID}")
        return UnifiedLoginResponse(
            entity_type="user",
            access_token=access_token,
            refresh_token=refresh_token,
            is_first_time=False,
            user_role=user_role,
            user_name=user.UserName if hasattr(user, 'UserName') and user.UserName else "",
            user_email=user.UserEmail,
            permissions=user_permissions,
            force_password_reset=force_password_reset,
        )

    candidate = None
    try:
        candidate = authenticate_candidate(db, request.email, request.password)
    except Exception as e:
        logger.error(f"Candidate authentication failed: {e}", exc_info=True)
        candidate = None

    if candidate:
        if not candidate:
            logger.error("Candidate is None after authentication")
            raise HTTPException(status_code=500, detail="Candidate record is invalid. Please contact help desk.")

        if not hasattr(candidate, 'candidateID') or not candidate.candidateID:
            logger.error("Candidate has no candidateID")
            raise HTTPException(status_code=500, detail="Candidate record incomplete. Please contact help desk.")

        if not hasattr(candidate, 'candidateEmail') or not candidate.candidateEmail:
            logger.error("Candidate has no candidateEmail")
            raise HTTPException(status_code=500, detail="Candidate record incomplete. Please contact help desk.")

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
            if hasattr(candidate, 'candidateIsVerified') and candidate.candidateIsVerified is not None
            else True
        )

        if hasattr(candidate, 'email_2fa_opted_in') and candidate.email_2fa_opted_in:
            code = generate_email_otp_code()
            try:
                candidate.email_otp_code_hash = hash_email_otp_code(code)
                candidate.email_otp_expires_at = datetime.utcnow() + timedelta(minutes=EMAIL_OTP_TTL_MINUTES)
                # Candidate already in session from authenticate_candidate(), just commit the updates
                db.commit()
            except Exception as e:
                logger.error(f"Failed to store candidate OTP: {e}", exc_info=True)
                db.rollback()
                raise HTTPException(status_code=500, detail="Failed to generate verification code. Please try again.")

            try:
                candidate_email = candidate.candidateEmail if hasattr(candidate, 'candidateEmail') else request.email
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
            except Exception as e:
                logger.error(f"Failed to send candidate OTP email: {e}", exc_info=True)

            pending_token = create_access_token(
                data={"sub": candidate.candidateID, "type": "candidate", "candidate_otp_pending": True},
                expires_delta=timedelta(minutes=MFA_PENDING_TOKEN_MINUTES),
            )

            logger.info(f"Login OTP pending for candidate {candidate.candidateID}")
            return UnifiedLoginResponse(
                entity_type="candidate",
                access_token=pending_token,
                is_first_time=is_first_time,
                candidate_id=candidate.candidateID,
                candidate_role=candidate.candidateRole if hasattr(candidate, 'candidateRole') and candidate.candidateRole else "Candidate",
                candidate_name=candidate_name,
                candidate_email=candidate.candidateEmail,
                candidate_mobile=candidate.candidateMobile if hasattr(candidate, 'candidateMobile') else None,
                candidate_otp_required=True,
            )

        access_token = create_access_token(
            data={
                "sub": candidate.candidateID,
                "type": "candidate",
            }
        )

        refresh_token = create_refresh_token(
            data={
                "sub": candidate.candidateID,
                "type": "refresh",
            }
        )

        logger.info(f"Login successful for candidate {candidate.candidateID}")
        return UnifiedLoginResponse(
            entity_type="candidate",
            access_token=access_token,
            refresh_token=refresh_token,
            is_first_time=is_first_time,
            candidate_id=candidate.candidateID,
            candidate_role=candidate.candidateRole if hasattr(candidate, 'candidateRole') and candidate.candidateRole else "Candidate",
            candidate_name=candidate_name,
            candidate_email=candidate.candidateEmail,
            candidate_mobile=candidate.candidateMobile if hasattr(candidate, 'candidateMobile') else None,
            show_2fa_opt_in_popup=(not (hasattr(candidate, 'email_2fa_opted_in') and candidate.email_2fa_opted_in is not None)),
        )

    logger.warning(f"Login failed: invalid credentials for {request.email}")
    raise HTTPException(status_code=401, detail="Invalid email or password")


@router.post("/v1/refresh", response_model=UnifiedLoginResponse)
def refresh_token_endpoint(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Refresh an access token using a refresh token. Protected endpoint."""
    if not credentials:
        logger.error("Token refresh failed: no credentials")
        raise HTTPException(status_code=401, detail="Missing refresh token")

    refresh_token_str = credentials.credentials
    if not refresh_token_str:
        logger.error("Token refresh failed: token string is empty")
        raise HTTPException(status_code=401, detail="Missing refresh token")

    payload = None
    try:
        from app.core.security import verify_token as verify_jwt
        payload = verify_jwt(refresh_token_str)
    except Exception as e:
        logger.error(f"Token verification failed: {e}", exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if not payload:
        logger.error("Token refresh failed: payload is None")
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        logger.error(f"Token refresh failed: token type is {payload.get('type')}")
        raise HTTPException(status_code=401, detail="Token is not a refresh token")

    user_id = payload.get("sub")
    if not user_id:
        logger.error("Token refresh failed: user_id missing")
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = None
    candidate = None
    try:
        user = check_user(db, None, user_id)
        candidate = check_candidate(db, None, user_id) if not user else None
    except Exception as e:
        logger.error(f"Failed to lookup user/candidate: {e}", exc_info=True)
        raise HTTPException(status_code=401, detail="User not found")

    if user:
        if not user or not user.UserID or not user.UserEmail:
            logger.error("User validation failed")
            raise HTTPException(status_code=500, detail="User record incomplete. Please contact help desk.")

        if not hasattr(user, 'role_template_id') or not user.role_template_id:
            logger.error(f"Token refresh rejected: user {user.UserID} has no role_template_id")
            raise HTTPException(
                status_code=403,
                detail="Your user account doesn't have permissions loaded. Please reach out to help desk."
            )

        access_token = create_access_token(
            data={
                "sub": user.UserID,
                "email": user.UserEmail,
                "type": "user",
                "name": user.UserName if hasattr(user, 'UserName') and user.UserName else "",
                "tenant_id": user.tenant_id,
                "role_template_id": user.role_template_id,
            }
        )

        new_refresh_token = create_refresh_token(
            data={
                "sub": user.UserID,
                "email": user.UserEmail,
                "type": "refresh",
            }
        )

        user_permissions = []
        try:
            user_permissions = RoleTemplatePermissionService.get_user_permissions(
                db, user.UserID, user.tenant_id if hasattr(user, 'tenant_id') else None
            )
        except Exception as e:
            logger.error(f"Failed to fetch permissions: {e}", exc_info=True)
            user_permissions = []

        user_role = "User"
        if user and hasattr(user, 'UserRole') and user.UserRole:
            user_role = user.UserRole

        if hasattr(user, 'role_template_id') and user.role_template_id:
            try:
                rt = db.query(RoleTemplate).filter(RoleTemplate.id == user.role_template_id).first()
                if rt and hasattr(rt, 'name') and rt.name:
                    user_role = rt.name
            except Exception as e:
                logger.error(f"Failed to fetch role template: {e}", exc_info=True)

        logger.info(f"Token refreshed for user {user.UserID}")
        return UnifiedLoginResponse(
            entity_type="user",
            access_token=access_token,
            refresh_token=new_refresh_token,
            is_first_time=False,
            user_role=user_role,
            user_name=user.UserName if hasattr(user, 'UserName') and user.UserName else "",
            user_email=user.UserEmail,
            permissions=user_permissions,
        )

    elif candidate:
        if not candidate or not candidate.candidateID or not candidate.candidateEmail:
            logger.error("Candidate validation failed")
            raise HTTPException(status_code=500, detail="Candidate record incomplete. Please contact help desk.")

        access_token = create_access_token(
            data={
                "sub": candidate.candidateID,
                "type": "candidate",
            }
        )

        new_refresh_token = create_refresh_token(
            data={
                "sub": candidate.candidateID,
                "type": "refresh",
            }
        )

        name_parts = []
        if candidate and hasattr(candidate, 'candidateFirstName') and candidate.candidateFirstName:
            name_parts.append(candidate.candidateFirstName)
        if candidate and hasattr(candidate, 'candidateMiddleName') and candidate.candidateMiddleName:
            name_parts.append(candidate.candidateMiddleName)
        if candidate and hasattr(candidate, 'candidateLastName') and candidate.candidateLastName:
            name_parts.append(candidate.candidateLastName)
        candidate_name = " ".join(filter(None, name_parts)) or ""

        logger.info(f"Token refreshed for candidate {candidate.candidateID}")
        return UnifiedLoginResponse(
            entity_type="candidate",
            access_token=access_token,
            refresh_token=new_refresh_token,
            is_first_time=False,
            candidate_id=candidate.candidateID,
            candidate_role=candidate.candidateRole if hasattr(candidate, 'candidateRole') and candidate.candidateRole else "Candidate",
            candidate_name=candidate_name,
            candidate_email=candidate.candidateEmail,
            candidate_mobile=candidate.candidateMobile if hasattr(candidate, 'candidateMobile') else None,
        )

    logger.error(f"Token refresh failed: user {user_id} not found")
    raise HTTPException(status_code=401, detail="User or candidate not found")


@router.post("/reset-password", dependencies=[Depends(require_role_template_permission("user", "manage"))])
async def reset_password(
    request: dict,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset user password. Protected endpoint - requires authentication and permission."""
    if not request:
        logger.error("Password reset failed: request is None")
        raise HTTPException(status_code=400, detail="Request body is required")

    user_id = request.get("user_id")
    new_password = request.get("new_password")

    if not user_id:
        logger.error("Password reset failed: user_id missing")
        raise HTTPException(status_code=400, detail="user_id is required")

    if not new_password:
        logger.error("Password reset failed: new_password missing")
        raise HTTPException(status_code=400, detail="new_password is required")

    if not isinstance(new_password, str) or len(new_password) < 8:
        logger.warning(f"Password reset failed: password too short")
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user = None
    try:
        user = db.query(Users).filter(Users.UserID == user_id).first()
    except Exception as e:
        logger.error(f"Failed to query user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error. Please try again later.")

    if not user:
        logger.warning(f"Password reset failed: user {user_id} not found")
        raise HTTPException(status_code=404, detail="User not found")

    if not hasattr(user, 'UserPassword'):
        logger.error(f"Password reset failed: user missing UserPassword")
        raise HTTPException(status_code=500, detail="User record incomplete. Please contact help desk.")

    try:
        user.UserPassword = get_password_hash(new_password)
        user.password_reset_required = False
        # User already in session from query, just commit the updates
        db.commit()
        db.refresh(user)
    except Exception as e:
        logger.error(f"Failed to update password: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to reset password. Please try again later.")

    logger.info(f"Password reset successful for user {user_id}")
    return {"status": "success", "message": "Password reset successfully"}
