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
from app.core.mfa import mfa_enforcement_enabled, role_requires_mfa, MFA_PENDING_TOKEN_MINUTES
from app.models.candidate import Candidate
from app.models.user import Users
from app.schemas.auth import SignupRequest, SignupResponse, LoginRequest, LoginResponse, CandidateLoginRequest, CandidateLoginResponse, UnifiedLoginRequest, UnifiedLoginResponse
from app.utils.uniq_id_generator import candidate_id_generator, generate_password, user_id_generator

router = APIRouter(prefix="/auth", tags=["auth"])


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
    
    # Create new user with correct field names matching Users model
    user = Users(
        UserID=user_id,
        UserName=request.user_name,
        UserEmail=request.user_email,
        UserPassword=hashed_password,
        UserRole=request.user_role
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return SignupResponse(response="User created successfully")
    




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
    # ── 1. Try authenticating as a User first ───────────────────
    user = authenticate_user(db, request.email, request.password)
    if user:
        # Phase 1 B3 -- gate is off by default (mfa_enforcement_enabled())
        # and only applies to MFA_REQUIRED_ROLES even when on. See
        # app.core.mfa's module docstring: do not enable the env flag
        # until the frontend has a screen for this, or every Super
        # User / BU Head account gets locked out with no way through.
        from datetime import timedelta
        if mfa_enforcement_enabled() and role_requires_mfa(user.UserRole):
            pending_token = create_access_token(
                data={"sub": user.UserEmail, "type": user.UserRole, "mfa_pending": True},
                expires_delta=timedelta(minutes=MFA_PENDING_TOKEN_MINUTES),
            )
            return UnifiedLoginResponse(
                entity_type="user",
                access_token=pending_token,
                is_first_time=False,
                user_role=user.UserRole,
                user_name=user.UserName or "",
                user_email=user.UserEmail,
                mfa_required=bool(user.mfa_enabled),
                mfa_setup_required=not bool(user.mfa_enabled),
            )

        access_token = create_access_token(
            data={
                "sub": user.UserEmail,
                "type": user.UserRole,
                "name": user.UserName,
            }
        )
        return UnifiedLoginResponse(
            entity_type="user",
            access_token=access_token,
            is_first_time=False,
            user_role=user.UserRole,
            user_name=user.UserName or "",
            user_email=user.UserEmail,
        )

    # ── 2. Fall back to Candidate ────────────────────────────────
    candidate = authenticate_candidate(db, request.email, request.password)
    if candidate:
        access_token = create_access_token(
            data={
                "sub": candidate.candidateID,
                "type": "candidate",
            }
        )
        name_parts = [
            candidate.candidateFirstName,
            candidate.candidateMiddleName,
            candidate.candidateLastName,
        ]
        candidate_name = " ".join(filter(None, name_parts)) or ""

        return UnifiedLoginResponse(
            entity_type="candidate",
            access_token=access_token,
            is_first_time=(
                not candidate.candidateIsVerified
                if candidate.candidateIsVerified is not None
                else True
            ),
            candidate_id=candidate.candidateID,
            candidate_role=candidate.candidateRole or "Candidate",
            candidate_name=candidate_name,
            candidate_email=candidate.candidateEmail,
            candidate_mobile=candidate.candidateMobile,
        )

    # ── 3. Neither matched ───────────────────────────────────────
    raise HTTPException(
        status_code=401,
        detail="Invalid email or password",
    )
