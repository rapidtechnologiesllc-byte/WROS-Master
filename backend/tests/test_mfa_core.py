"""
Proves app.core.mfa's TOTP and backup-code mechanics directly, no HTTP
layer involved. Real cryptographic round-trips (pyotp), no mocking of
the thing actually being tested.
"""
import pyotp

from app.core.mfa import (
    generate_totp_secret,
    get_provisioning_uri,
    verify_totp_code,
    generate_backup_codes,
    hash_backup_code,
    verify_and_consume_backup_code,
    mfa_enforcement_enabled,
    generate_email_otp_code,
    hash_email_otp_code,
    verify_email_otp_code,
    email_otp_enforcement_enabled,
)

def test_generated_secret_is_usable_by_pyotp():
    secret = generate_totp_secret()
    totp = pyotp.TOTP(secret)
    code = totp.now()
    assert verify_totp_code(secret, code) is True

def test_wrong_code_is_rejected():
    secret = generate_totp_secret()
    other_secret = generate_totp_secret()
    wrong_code = pyotp.TOTP(other_secret).now()
    assert verify_totp_code(secret, wrong_code) is False

def test_empty_or_missing_code_is_rejected():
    secret = generate_totp_secret()
    assert verify_totp_code(secret, "") is False
    assert verify_totp_code(secret, None) is False

def test_provisioning_uri_is_a_standard_otpauth_uri():
    secret = generate_totp_secret()
    uri = get_provisioning_uri(secret, "priya@blitzenx.com")
    assert uri.startswith("otpauth://totp/")
    assert "priya%40blitzenx.com" in uri or "priya@blitzenx.com" in uri
    assert "BlitzenX" in uri

def test_backup_codes_are_unique_and_high_entropy():
    codes = generate_backup_codes(10)
    assert len(codes) == 10
    assert len(set(codes)) == 10  # no duplicates
    assert all(len(c) == 8 for c in codes)  # 4 bytes hex-encoded

def test_backup_code_round_trip_and_single_use():
    codes = generate_backup_codes(3)
    hashed = [hash_backup_code(c) for c in codes]

    matched, remaining = verify_and_consume_backup_code(codes[0], hashed)
    assert matched is True
    assert len(remaining) == 2
    assert hash_backup_code(codes[0]) not in remaining

    # Negative case: the same code cannot be used twice.
    matched_again, remaining_again = verify_and_consume_backup_code(codes[0], remaining)
    assert matched_again is False
    assert len(remaining_again) == 2

def test_wrong_backup_code_is_rejected():
    codes = generate_backup_codes(3)
    hashed = [hash_backup_code(c) for c in codes]
    matched, remaining = verify_and_consume_backup_code("not-a-real-code", hashed)
    assert matched is False
    assert remaining == hashed

def test_who_needs_mfa_is_decided_by_role_template_level_not_name():
    """TOTP: BU-Head level (hierarchy 14) and above; email OTP: every internal role. A role
    called "Super User" or "BU Head" gets nothing from its name (app.core.authority)."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from app.core import authority

    def role(level):
        return SimpleNamespace(hierarchy_level=level, enabled=True, tenant_id=1, org_level_access=False)

    with patch.object(authority, "role_of", side_effect=lambda db, u: role(u.level) if u.level else None):
        assert authority.requires_totp(None, SimpleNamespace(level=14))
        assert not authority.requires_totp(None, SimpleNamespace(level=13))
        assert authority.requires_email_otp(None, SimpleNamespace(level=2))
        assert not authority.requires_email_otp(None, SimpleNamespace(level=0))  # no role: e.g. a candidate

def test_enforcement_is_off_by_default(monkeypatch):
    monkeypatch.delenv("MFA_ENFORCEMENT_ENABLED", raising=False)
    assert mfa_enforcement_enabled() is False

def test_enforcement_can_be_turned_on_via_env(monkeypatch):
    monkeypatch.setenv("MFA_ENFORCEMENT_ENABLED", "true")
    assert mfa_enforcement_enabled() is True

# ---------------------------------------------------------------------------
# Email OTP -- backlog item, 2026-08-05 (wros_email_2fa_backlog).
# Supplements the TOTP mechanics above; a separate role set + separate
# enforcement flag, proven separate here too.
# ---------------------------------------------------------------------------

def test_email_otp_code_is_six_digits():
    code = generate_email_otp_code()
    assert len(code) == 6
    assert code.isdigit()

def test_email_otp_round_trip():
    code = generate_email_otp_code()
    hashed = hash_email_otp_code(code)
    assert verify_email_otp_code(code, hashed) is True

def test_email_otp_wrong_code_rejected():
    hashed = hash_email_otp_code(generate_email_otp_code())
    assert verify_email_otp_code("000000", hashed) is False

def test_email_otp_empty_or_missing_rejected():
    hashed = hash_email_otp_code(generate_email_otp_code())
    assert verify_email_otp_code("", hashed) is False
    assert verify_email_otp_code(None, hashed) is False
    assert verify_email_otp_code("123456", None) is False

def test_email_otp_enforcement_is_off_by_default(monkeypatch):
    monkeypatch.delenv("EMAIL_OTP_ENFORCEMENT_ENABLED", raising=False)
    assert email_otp_enforcement_enabled() is False

def test_email_otp_enforcement_can_be_turned_on_via_env(monkeypatch):
    monkeypatch.setenv("EMAIL_OTP_ENFORCEMENT_ENABLED", "true")
    assert email_otp_enforcement_enabled() is True
