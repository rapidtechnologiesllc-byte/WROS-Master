"""
S-034/HRMS-0434 -- response validation + safe fallback
(app.services.thunder_service.validate_thunder_reply /
import logging
generate_thunder_reply_with_fallback).

Doesn't touch the real Gemini call -- generate_thunder_reply() itself is
already exercised via app.services.thunder_service's other callers
(run_test_chat_turn, covered by test_thunder_chat_endpoint.py-style
tests elsewhere); here generate_thunder_reply is monkeypatched so these
tests are pure, fast, and about the validation/fallback logic only.

Also covers two real gaps closed against the revised S-034 canonical
spec: BR-01 ownership-first ordering (a conversation owned by a human
must never burn an LLM call, not just be caught after the fact) and
"Thunder never responds cold" (a build_candidate_context() failure
inside generate_thunder_reply() must escalate to the recruiter queue
and fall back safely, not crash or retry blindly).
"""
import logging
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.thunder_service as thunder_service
from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.user import Users
from app.services.thunder_service import (
    SAFE_FALLBACK_MESSAGE,
    ConversationOwnedByHuman,
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


# ---------------------------------------------------------------------------
# BR-01 (S-034 revised): ownership checked before any context build/LLM call
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

class _FakeConversation:
    def __init__(self, owner_type):
        self.id = 1
        self.owner_type = owner_type
        self.owner_id = "some-recruiter"


def test_human_owned_conversation_raises_before_any_llm_call(monkeypatch):
    calls = []
    monkeypatch.setattr(
        thunder_service, "generate_thunder_reply",
        lambda db, candidate, msg, **kwargs: calls.append(1) or "irrelevant, should never run",
    )
    with pytest.raises(ConversationOwnedByHuman):
        generate_thunder_reply_with_fallback(None, None, "hi", conversation=_FakeConversation("hr_user"))
    assert calls == []  # the LLM path was never touched


def test_ai_owned_conversation_generates_normally(monkeypatch):
    monkeypatch.setattr(
        thunder_service, "generate_thunder_reply",
        lambda db, candidate, msg, **kwargs: "This is a perfectly valid Thunder reply.",
    )
    text, used_fallback = generate_thunder_reply_with_fallback(None, None, "hi", conversation=_FakeConversation("ai_agent"))
    assert text == "This is a perfectly valid Thunder reply."
    assert used_fallback is False


def test_no_conversation_supplied_skips_ownership_check(monkeypatch):
    """Backward compatible: existing callers without a conversation object
    on hand are unaffected."""
    monkeypatch.setattr(
        thunder_service, "generate_thunder_reply",
        lambda db, candidate, msg, **kwargs: "This is a perfectly valid Thunder reply.",
    )
    text, used_fallback = generate_thunder_reply_with_fallback(None, None, "hi")
    assert used_fallback is False


# ---------------------------------------------------------------------------
# "Thunder never responds cold" (S-034 revised): context-build failure
# escalates and falls back, no crash, no blind retry.
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def seeded_conversation(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h")
    db_session.add_all([owner, candidate])
    db_session.commit()
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none")
    db_session.add(conv)
    db_session.commit()
    return conv


def test_context_build_failure_escalates_and_falls_back_without_retry(monkeypatch, db_session, seeded_conversation):
    calls = []

    def _raise_unexpected(db, candidate, msg, **kwargs):
        calls.append(1)
        raise RuntimeError("build_candidate_context blew up")

    monkeypatch.setattr(thunder_service, "generate_thunder_reply", _raise_unexpected)

    text, used_fallback = generate_thunder_reply_with_fallback(db_session, None, "hi", conversation=seeded_conversation)

    assert text == SAFE_FALLBACK_MESSAGE
    assert used_fallback is True
    assert len(calls) == 1  # no blind retry on an unexpected/context-build failure

    db_session.refresh(seeded_conversation)
    assert seeded_conversation.escalation_state == "escalated"

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == seeded_conversation.id, ConversationEvent.event_type == "escalation_triggered").all()
    assert len(events) == 1
    assert events[0].event_data["reason"] == "context_build_failed"


def test_generation_failed_error_still_retries_once_and_does_not_escalate(monkeypatch, db_session, seeded_conversation):
    """ThunderReplyGenerationFailed (a known, handled failure mode) keeps
    its existing retry-once behavior and must NOT be conflated with an
    unexpected context-build failure."""
    calls = []

    def _raise_known(db, candidate, msg, **kwargs):
        calls.append(1)
        raise ThunderReplyGenerationFailed("Gemini down")

    monkeypatch.setattr(thunder_service, "generate_thunder_reply", _raise_known)

    text, used_fallback = generate_thunder_reply_with_fallback(db_session, None, "hi", conversation=seeded_conversation)

    assert text == SAFE_FALLBACK_MESSAGE
    assert used_fallback is True
    assert len(calls) == 2  # retried once, as before

    db_session.refresh(seeded_conversation)
    assert seeded_conversation.escalation_state == "none"  # not escalated -- different failure class
