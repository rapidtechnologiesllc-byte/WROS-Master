"""
Phase 1 B3 -- MFA enrollment and verification.

Reached only via the mfa_pending short-lived token issued by
POST /auth/login when MFA gating applies (see auth.py's unified_login).
A normal full access token does NOT work here (get_current_mfa_pending_user
requires the mfa_pending claim specifically), and an mfa_pending token
does NOT work on any other route (every other dependency in
app.core.dependencies rejects it via _reject_if_mfa_pending) -- the two
token types are deliberately non-interchangeable.
"""
import json
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    get_current_candidate,
    get_current_candidate_otp_pending,
    get_current_mfa_pending_user,
)
from app.core.mfa import (
    EMAIL_OTP_TTL_MINUTES,
    generate_backup_codes,
    generate_email_otp_code,
    generate_totp_secret,
    get_provisioning_uri,
    hash_backup_code,
    hash_email_otp_code,
    verify_and_consume_backup_code,
    verify_email_otp_code,
    verify_totp_code,
)
from app.core.security import create_access_token
from app.models.candidate import Candidate
from app.models.user import Users
from app.services.email_service import EmailService

router = APIRouter(prefix="/auth/mfa", tags=["mfa"])


class MfaSetupResponse(BaseModel):
    provisioning_uri: str
    secret: str
    backup_codes: List[str]  # shown exactly once -- caller must store these


class MfaCodeRequest(BaseModel):
    code: Optional[str] = None
    backup_code: Optional[str] = None


class MfaVerifiedResponse(BaseModel):
    access_token: str
    user_role: str
    user_name: str
    user_email: str


@router.post("/setup", response_model=MfaSetupResponse)
def setup_mfa(
    user: Users = Depends(get_current_mfa_pending_user),
    db: Session = Depends(get_db),
):
    """
    Generates a fresh TOTP secret + backup codes and stores them --
    mfa_enabled stays False until /setup/confirm proves the user can
    actually produce a valid code from it. Safe to call again before
    confirming (e.g. the user's first QR scan failed) -- overwrites the
    unconfirmed secret rather than accumulating stale ones.
    """
    if user.mfa_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA is already enabled for this account")

    secret = generate_totp_secret()
    plain_backup_codes = generate_backup_codes()
    hashed_backup_codes = [hash_backup_code(c) for c in plain_backup_codes]

    user.mfa_secret = secret
    user.mfa_backup_codes = json.dumps(hashed_backup_codes)
    db.add(user)
    db.commit()

    return MfaSetupResponse(
        provisioning_uri=get_provisioning_uri(secret, user.UserEmail),
        secret=secret,
        backup_codes=plain_backup_codes,
    )


@router.post("/setup/confirm", response_model=MfaVerifiedResponse)
def confirm_mfa_setup(
    body: MfaCodeRequest,
    user: Users = Depends(get_current_mfa_pending_user),
    db: Session = Depends(get_db),
):
    """First successful code proves enrollment worked -- flips mfa_enabled
    on and issues a real, full access token."""
    if not user.mfa_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Call /setup first")
    if not body.code or not verify_totp_code(user.mfa_secret, body.code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code")

    user.mfa_enabled = True
    db.add(user)
    db.commit()

    return _issue_full_token(user)


@router.post("/verify", response_model=MfaVerifiedResponse)
def verify_mfa(
    body: MfaCodeRequest,
    user: Users = Depends(get_current_mfa_pending_user),
    db: Session = Depends(get_db),
):
    """For subsequent logins once MFA is already enabled -- accepts
    either a fresh TOTP code or a single-use backup code."""
    if not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA is not enabled for this account")

    if body.code and verify_totp_code(user.mfa_secret, body.code):
        return _issue_full_token(user)

    if body.backup_code:
        hashed_codes = json.loads(user.mfa_backup_codes or "[]")
        matched, remaining = verify_and_consume_backup_code(body.backup_code, hashed_codes)
        if matched:
            user.mfa_backup_codes = json.dumps(remaining)
            db.add(user)
            db.commit()
            return _issue_full_token(user)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code")


class EmailOtpVerifyRequest(BaseModel):
    code: str


@router.post("/email/resend", response_model=dict)
def resend_email_otp(
    user: Users = Depends(get_current_mfa_pending_user),
    db: Session = Depends(get_db),
):
    """Backlog item, 2026-08-05 (wros_email_2fa_backlog): re-issues a
    fresh code and invalidates the previous one -- same posture as
    /auth/mfa/setup being safe to call again before confirming."""
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
                f"It expires in {EMAIL_OTP_TTL_MINUTES} minutes."
            ),
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not send verification email. Please try again.")

    return {"sent": True}


@router.post("/email/verify", response_model=MfaVerifiedResponse)
def verify_email_otp(
    body: EmailOtpVerifyRequest,
    user: Users = Depends(get_current_mfa_pending_user),
    db: Session = Depends(get_db),
):
    """Backlog item, 2026-08-05 (wros_email_2fa_backlog): the email-OTP
    counterpart to /auth/mfa/verify. Fail closed on expiry -- an
    expired code is treated exactly like a wrong one, not silently
    accepted."""
    if not user.email_otp_code_hash or not user.email_otp_expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No verification code was issued. Call /auth/mfa/email/resend first.")
    if datetime.utcnow() > user.email_otp_expires_at:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Verification code has expired. Request a new one.")
    if not verify_email_otp_code(body.code, user.email_otp_code_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code")

    # Single-use: clear it the moment it's consumed, whether or not the
    # user has any other MFA factor -- same "never a reusable stored
    # secret" posture as mfa_backup_codes' single-use consumption.
    user.email_otp_code_hash = None
    user.email_otp_expires_at = None
    db.add(user)
    db.commit()

    return _issue_full_token(user)


def _issue_full_token(user: Users) -> MfaVerifiedResponse:
    access_token = create_access_token(
        data={
            "sub": user.UserID,
            "email": user.UserEmail,
            "type": "user",
            "name": user.UserName,
        }
    )
    return MfaVerifiedResponse(
        access_token=access_token,
        user_role=user.UserRole,
        user_name=user.UserName or "",
        user_email=user.UserEmail,
    )


# ============================================
# Backlog item, 2026-08-05 (wros_email_2fa_backlog) -- candidate half.
# Opt-in, not enforced: a candidate chooses via the popup their first
# normal login shows (UnifiedLoginResponse.show_2fa_opt_in_popup), and
# from then on every login challenges them for an emailed code, same
# mechanics as the internal-user email OTP above, just Candidate- not
# Users-scoped and gated by the candidate's own choice instead of an
# env flag.
# ============================================

class CandidateOtpOptInRequest(BaseModel):
    opted_in: bool


class CandidateOtpOptInResponse(BaseModel):
    email_2fa_opted_in: bool


class CandidateOtpVerifiedResponse(BaseModel):
    access_token: str
    candidate_id: str
    candidate_role: str
    candidate_email: str


def _candidate_name(candidate: Candidate) -> str:
    parts = [candidate.candidateFirstName, candidate.candidateMiddleName, candidate.candidateLastName]
    return " ".join(p for p in parts if p) or candidate.candidateEmail


def _issue_full_candidate_token(candidate: Candidate) -> CandidateOtpVerifiedResponse:
    access_token = create_access_token(data={"sub": candidate.candidateID, "type": "candidate"})
    return CandidateOtpVerifiedResponse(
        access_token=access_token,
        candidate_id=candidate.candidateID,
        candidate_role=candidate.candidateRole or "Candidate",
        candidate_email=candidate.candidateEmail,
    )


@router.post("/candidate/opt-in", response_model=CandidateOtpOptInResponse)
def set_candidate_email_2fa_opt_in(
    body: CandidateOtpOptInRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
):
    """Called from the opt-in popup (or a future settings screen) by an
    ALREADY-logged-in candidate -- a normal full candidate token, not a
    pending one; there's nothing to verify here, just a preference."""
    candidate.email_2fa_opted_in = body.opted_in
    db.add(candidate)
    db.commit()
    return CandidateOtpOptInResponse(email_2fa_opted_in=candidate.email_2fa_opted_in)


@router.post("/candidate/email/resend")
def resend_candidate_email_otp(
    candidate: Candidate = Depends(get_current_candidate_otp_pending),
    db: Session = Depends(get_db),
):
    code = generate_email_otp_code()
    candidate.email_otp_code_hash = hash_email_otp_code(code)
    candidate.email_otp_expires_at = datetime.utcnow() + timedelta(minutes=EMAIL_OTP_TTL_MINUTES)
    db.add(candidate)
    db.commit()

    try:
        EmailService.send_event_notification(
            to_email=candidate.candidateEmail,
            recipient_name=_candidate_name(candidate),
            event_type="action_required",
            heading="Your BlitzenX verification code",
            message=(
                f"Your one-time verification code is <strong>{code}</strong>. "
                f"It expires in {EMAIL_OTP_TTL_MINUTES} minutes."
            ),
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not send verification email. Please try again.")

    return {"sent": True}


@router.post("/candidate/email/verify", response_model=CandidateOtpVerifiedResponse)
def verify_candidate_email_otp(
    body: EmailOtpVerifyRequest,
    candidate: Candidate = Depends(get_current_candidate_otp_pending),
    db: Session = Depends(get_db),
):
    if not candidate.email_otp_code_hash or not candidate.email_otp_expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No verification code was issued. Call /auth/mfa/candidate/email/resend first.")
    if datetime.utcnow() > candidate.email_otp_expires_at:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Verification code has expired. Request a new one.")
    if not verify_email_otp_code(body.code, candidate.email_otp_code_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code")

    candidate.email_otp_code_hash = None
    candidate.email_otp_expires_at = None
    db.add(candidate)
    db.commit()

    return _issue_full_candidate_token(candidate)
