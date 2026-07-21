# login schemas
from pydantic import BaseModel, EmailStr, constr
from typing import Optional, List
from datetime import datetime, date

class SignupRequest(BaseModel):
    user_name: str
    user_email: EmailStr
    user_password: str
    user_role: str


class SignupResponse(BaseModel):
    response: str = "User created successfully"


class LoginRequest(BaseModel):
    UserEmail: EmailStr
    UserPassword: str

class LoginResponse(BaseModel):
    user_role: str
    user_name: str
    user_email: EmailStr
    is_first_time: bool
    access_token: str

class CandidateLoginRequest(BaseModel):
    candidate_email: EmailStr
    candidate_password: str

class CandidateLoginResponse(BaseModel):
    candidate_id: str
    candidate_role: str
    candidate_name: str
    candidate_email: EmailStr
    candidate_mobile: str
    is_first_time: bool
    access_token: str


# ── Unified login ──────────────────────────────────────────────
class UnifiedLoginRequest(BaseModel):
    """Single login payload for both users and candidates."""
    email: EmailStr
    password: str


class UnifiedLoginResponse(BaseModel):
    """Single login response – entity_type is either 'user' or 'candidate'."""
    entity_type: str            # "user" | "candidate"
    access_token: str
    is_first_time: bool

    # Phase 1 B3 -- both default False so existing non-MFA callers see
    # zero change. When either is True, access_token is a short-lived
    # mfa_pending token (5 min) that ONLY works against POST
    # /auth/mfa/setup or /auth/mfa/verify -- it is deliberately rejected
    # by every other authenticated route (see
    # app.core.dependencies._reject_if_mfa_pending).
    mfa_required: bool = False        # MFA already enabled -> call /auth/mfa/verify
    mfa_setup_required: bool = False  # MFA never enrolled -> call /auth/mfa/setup

    # User-specific (None for candidates)
    user_role: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[EmailStr] = None

    # Candidate-specific (None for users)
    candidate_id: Optional[str] = None
    candidate_role: Optional[str] = None
    candidate_name: Optional[str] = None
    candidate_email: Optional[EmailStr] = None
    candidate_mobile: Optional[str] = None
