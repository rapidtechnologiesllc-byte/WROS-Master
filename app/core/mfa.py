"""
Phase 1 B3 -- TOTP-based MFA for the highest-privilege roles.

ROLE MAPPING IS AN ASSUMPTION, NOT A CONFIRMED DECISION: the Phase 1
doc says "MFA required for Admin and Director roles specifically", but
this codebase's actual RBAC seed (app/services/rbac_service.py) has no
role literally named "Admin" or "Director" -- the real role list is
Super User, BU Head, Hiring Manager, HR Manager, HR Operations, HRBP,
Recruitment Manager, Recruitment Team Lead, Recruiter, Employee,
Consultant, Candidate. MFA_REQUIRED_ROLES below defaults to the closest
real analogs (Super User = full-bypass admin equivalent; BU Head = the
broadest non-Super-User role, includes rbac.manage) -- CONFIRM this
mapping with whoever owns the actual role taxonomy before relying on
it, and update this set if it's wrong.

ENFORCEMENT IS OFF BY DEFAULT (MFA_ENFORCEMENT_ENABLED). The full
enroll/verify mechanism below is real, tested, and safe to merge as-is
-- it changes nothing about existing login behavior until the flag is
turned on. Do NOT turn it on until the frontend has a screen to show a
QR code / accept a TOTP code -- flipping it on blind would lock every
Super User / BU Head account out of login with no way to complete the
challenge.
"""
import base64
import hashlib
import os
import secrets
from typing import List, Tuple

import pyotp

MFA_REQUIRED_ROLES = {"Super User", "BU Head"}
MFA_PENDING_TOKEN_MINUTES = 5


def mfa_enforcement_enabled() -> bool:
    return os.getenv("MFA_ENFORCEMENT_ENABLED", "false").lower() == "true"


def role_requires_mfa(role_name: str) -> bool:
    return bool(role_name) and role_name in MFA_REQUIRED_ROLES


# ---------------------------------------------------------------------------
# Backlog item, 2026-08-05 -- email-based one-time code, SUPPLEMENTING the
# TOTP flow above rather than replacing it. Avinash's ask: "Missing two
# step validation via email for employees and internal users" -- broader
# than MFA_REQUIRED_ROLES (Super User/BU Head only). A deliberately
# SEPARATE role set and a SEPARATE enforcement flag from the TOTP gate
# above -- expanding MFA_REQUIRED_ROLES itself would be a real,
# independent security-scope change to the existing, already-careful
# TOTP posture; this instead adds a new, independently-off-by-default
# channel for the broader "every internal role" ask. Same
# "ENFORCEMENT IS OFF BY DEFAULT, do not enable until the frontend has
# a real screen for it" posture as mfa_enforcement_enabled() above.
# ---------------------------------------------------------------------------
# Every real internal role except Candidate (candidates are the
# separate, opt-in, NOT-built-this-pass half of the same ask -- see
# wros_email_2fa_backlog memory note).
EMAIL_OTP_REQUIRED_ROLES = {
    "Super User", "Partner", "BU Head", "Hiring Manager", "HR Manager",
    "HR Operations", "HRBP", "Recruitment Manager", "Recruitment Team Lead",
    "Recruiter", "Employee", "Consultant",
}
EMAIL_OTP_TTL_MINUTES = 10


def email_otp_enforcement_enabled() -> bool:
    return os.getenv("EMAIL_OTP_ENFORCEMENT_ENABLED", "false").lower() == "true"


def role_requires_email_otp(role_name: str) -> bool:
    return bool(role_name) and role_name in EMAIL_OTP_REQUIRED_ROLES


def generate_email_otp_code() -> str:
    """6-digit numeric code, zero-padded -- easy to read aloud/type,
    same posture as every mainstream email-OTP flow. Generated via
    `secrets`, not `random` -- this is a real auth credential, however
    short-lived."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_email_otp_code(code: str) -> str:
    # Same rationale as hash_backup_code below: a short-lived,
    # high-entropy-enough (1 in a million, single 10-minute window,
    # not a long-lived user-chosen password) token -- a fast SHA-256
    # is appropriate here, not bcrypt.
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def verify_email_otp_code(code: str, hashed: str) -> bool:
    if not code or not hashed:
        return False
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest() == hashed


# ---------------------------------------------------------------------------
# TOTP secret + verification
# ---------------------------------------------------------------------------

def generate_totp_secret() -> str:
    """Base32 secret, suitable for pyotp and any standard authenticator app."""
    return pyotp.random_base32()


def get_provisioning_uri(secret: str, account_email: str, issuer: str = "BlitzenX WROS") -> str:
    """otpauth:// URI -- render as a QR code client-side, or let the user
    enter it manually into their authenticator app."""
    return pyotp.totp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=issuer)


def verify_totp_code(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    totp = pyotp.TOTP(secret)
    # valid_window=1 tolerates one 30s step of clock drift either side,
    # a standard and narrow allowance -- not a wide-open window.
    return totp.verify(code, valid_window=1)


# ---------------------------------------------------------------------------
# Backup codes (account recovery if the TOTP device is lost)
# ---------------------------------------------------------------------------

def generate_backup_codes(count: int = 10) -> List[str]:
    """Plain-text codes -- shown to the user exactly once at enrollment,
    never stored or logged in plain text (see hash_backup_code)."""
    return [secrets.token_hex(4) for _ in range(count)]


def hash_backup_code(code: str) -> str:
    # Backup codes are single-use, high-entropy (8 hex chars = 32 bits,
    # generated via secrets not guessed by a user), short-lived-in-
    # practice tokens, not passwords -- a fast, unsalted-but-unique-per-
    # code SHA-256 is an appropriate, simple choice here, distinct from
    # bcrypt's deliberately-slow design for user-chosen passwords.
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def verify_and_consume_backup_code(code: str, hashed_codes: List[str]) -> Tuple[bool, List[str]]:
    """
    Returns (matched, remaining_hashed_codes). On a match, the used
    code is removed from the returned list -- the caller is
    responsible for persisting the updated list so the code can't be
    reused (single-use, per B3's session-security posture).
    """
    if not code:
        return False, hashed_codes
    target = hash_backup_code(code.strip())
    if target in hashed_codes:
        remaining = [h for h in hashed_codes if h != target]
        return True, remaining
    return False, hashed_codes
