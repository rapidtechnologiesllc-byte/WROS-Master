"""Simplified login endpoint for testing"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db, authenticate_user, authenticate_candidate
from app.core.security import create_access_token
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
from app.models.user import Users
from app.schemas.auth import UnifiedLoginRequest, UnifiedLoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def unified_login(request: UnifiedLoginRequest, db: Session = Depends(get_db)):
    """Simple login endpoint - authenticate and return token"""

    # Try authenticating as a User
    user = authenticate_user(db, request.email, request.password)
    if user:
        user_role = getattr(user, 'UserRole', 'Employee')
        access_token = create_access_token(
            data={
                "sub": user.UserID,
                "email": user.UserEmail,
                "type": "user",
                "name": user.UserName or "",
            }
        )
        return {
            "entity_type": "user",
            "access_token": access_token,
            "is_first_time": False,
            "user_role": user_role,
            "user_name": user.UserName or "",
            "user_email": user.UserEmail,
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
