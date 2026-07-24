"""
S-034/HRMS-0434 -- response validation + safe fallback
(app.services.thunder_service.validate_thunder_reply /
generate_thunder_reply_with_fallback).

Doesn't touch the real Gemini call -- generate_thunder_reply() itself is
already exercised via app.services.thunder_service's other callers
(run_test_chat_turn, covered by test_thunder_chat_endpoint.py-style
tests elsewhere); here generate_thunder_reply is monkeypatched so these
tests are pure, fast, and about the validation/fallback logic only.
"""
import pytest

import app.services.thunder_service as thunder_service
from app.services.thunder_service import (
    SAFE_FALLBACK_MESSAGE,
    ThunderReplyGenerationFailed,
    generate_thunder_reply_with_fallback,
    validate_thunder_reply,
)


# ---------------------------------------------------------------------------
# validate_thunder_reply
# ---------------------------------------------------------------------------

def test_validate_rejects_none_or_empty():
    assert validate_thunder_reply(None) is False
    assert validate_thunder_reply("") is False


def test_validate_rejects_too_short():
    assert validate_thunder_reply("Hi!") is False  # 3 chars < 10


def test_validate_rejects_too_long():
    assert validate_thunder_reply("x" * 4097) is False


def test_validate_rejects_unreplaced_template_vars():
    assert validate_thunder_reply("Hi {{candidate_name}}, thanks for your reply!") is False


def test_validate_accepts_normal_reply():
    assert validate_thunder_reply("Thanks for the update, we'll review and get back to you soon!") is True


def test_validate_accepts_reply_at_min_length_boundary():
    assert validate_thunder_reply("x" * 10) is True


# ---------------------------------------------------------------------------
# generate_thunder_reply_with_fallback
# ---------------------------------------------------------------------------

def test_first_attempt_valid_returns_immediately(monkeypatch):
    monkeypatch.setattr(
        thunder_service, "generate_thunder_reply",
        lambda db, candidate, msg, **kwargs: "This is a perfectly valid Thunder reply.",
    )
    text, used_fallback = generate_thunder_reply_with_fallback(None, None, "hi")
    assert text == "This is a perfectly valid Thunder reply."
    assert used_fallback is False


def test_invalid_first_attempt_regenerates_once(monkeypatch):
    calls = iter([
        "Hi {{candidate_name}}",  # invalid: unreplaced var
        "This second attempt is a valid, properly formed reply.",
    ])
    monkeypatch.setattr(
        thunder_service, "generate_thunder_reply",
        lambda db, candidate, msg, **kwargs: next(calls),
    )
    text, used_fallback = generate_thunder_reply_with_fallback(None, None, "hi")
    assert text == "This second attempt is a valid, properly formed reply."
    assert used_fallback is False


def test_both_attempts_fail_returns_safe_fallback(monkeypatch):
    def _raise(db, candidate, msg, **kwargs):
        raise ThunderReplyGenerationFailed("Gemini down")

    monkeypatch.setattr(thunder_service, "generate_thunder_reply", _raise)
    text, used_fallback = generate_thunder_reply_with_fallback(None, None, "hi")
    assert text == SAFE_FALLBACK_MESSAGE
    assert used_fallback is True


def test_both_attempts_invalid_returns_safe_fallback(monkeypatch):
    monkeypatch.setattr(
        thunder_service, "generate_thunder_reply",
        lambda db, candidate, msg, **kwargs: "short",  # always invalid (< 10 chars)
    )
    text, used_fallback = generate_thunder_reply_with_fallback(None, None, "hi")
    assert text == SAFE_FALLBACK_MESSAGE
    assert used_fallback is True


def test_safe_fallback_message_is_never_empty_or_too_long():
    assert validate_thunder_reply(SAFE_FALLBACK_MESSAGE) is True
