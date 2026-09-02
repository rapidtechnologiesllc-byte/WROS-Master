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


# ── CONSOLIDATED LOGIN FLOW - Step 1: Validate Email, Step 2: Login with Password ────
# All legacy login models (LoginRequest, LoginResponse, CandidateLoginRequest, CandidateLoginResponse)
# have been deleted. Use UnifiedLoginRequest + UnifiedLoginResponse for both users and candidates.
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

    # Backlog item, 2026-08-05 -- email OTP, supplements the TOTP fields
    # above rather than replacing them (see app.core.mfa's EMAIL_OTP_*
    # section). When True, a one-time code has ALREADY been emailed to
    # the user as part of this same login call -- call
    # POST /auth/mfa/email/verify with that code against the same
    # access_token (mfa_pending) to complete login.
    email_otp_required: bool = False

    # Backlog item, 2026-08-05 (wros_email_2fa_backlog, candidate half).
    # candidate_otp_required: this candidate has opted in -- a code has
    # already been emailed as part of this same login call, same
    # pattern as email_otp_required above but candidate-side. Call
    # POST /auth/mfa/candidate/email/verify with that code against the
    # same access_token (candidate_otp_pending) to complete login.
    # show_2fa_opt_in_popup: this candidate has never been asked
    # (email_2fa_opted_in is NULL) -- login completes normally
    # (access_token below is already a full candidate token), the
    # frontend should show the opt-in popup once, non-blocking.
    candidate_otp_required: bool = False
    show_2fa_opt_in_popup: bool = False

    # User-specific (None for candidates)
    user_role: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[EmailStr] = None
    permissions: Optional[dict] = None  # Role template permissions {resource: {can_view, can_create, can_edit, can_delete}}

    # Candidate-specific (None for users)
    candidate_id: Optional[str] = None
    candidate_role: Optional[str] = None
    candidate_name: Optional[str] = None
    candidate_email: Optional[EmailStr] = None
    candidate_mobile: Optional[str] = None
