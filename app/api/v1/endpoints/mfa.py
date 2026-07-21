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
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_mfa_pending_user
from app.core.mfa import (
    generate_totp_secret,
    get_provisioning_uri,
    verify_totp_code,
    generate_backup_codes,
    hash_backup_code,
    verify_and_consume_backup_code,
)
from app.core.security import create_access_token
from app.models.user import Users

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


def _issue_full_token(user: Users) -> MfaVerifiedResponse:
    access_token = create_access_token(
        data={"sub": user.UserEmail, "type": user.UserRole, "name": user.UserName}
    )
    return MfaVerifiedResponse(
        access_token=access_token,
        user_role=user.UserRole,
        user_name=user.UserName or "",
        user_email=user.UserEmail,
    )
