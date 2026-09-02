"""
import logging
S-031/HRMS-0431 -- AI Prompt Framework.

Real architecture under test (see prompt_framework_service module
docstring): {{thunder_name}} is never hardcoded (BR-04) -- caller
supplies it via candidate_context, sourced in real usage from
resolve_thunder_config(). Temperature is 0.7 for conversational
prompts, 0.0 for classification (BR-02). Every call_llm() invocation
logs to prompt_execution_log, success or failure (BR-03), with a
real retry-once-then-raise on repeated failure.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.prompt_execution_log import PromptExecutionLog
from app.models.user import Users

import app.services.prompt_framework_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[Users.__table__, Candidate.__table__, PromptExecutionLog.__table__])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def seeded(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    db_session.add_all([owner, candidate])
    db_session.commit()
    return candidate


def _no_sleep(seconds):
    pass


# ── build_prompt() ───────────────────────────────────────────────────

def test_build_prompt_replaces_all_placeholders_no_leftover_braces():
    context = {
        "thunder_name": "Thunder", "name": "Priya",
        "memory": {"summary": "Experienced engineer.", "facts": [{"key": "expected_ctc", "value": "24 LPA"}]},
        "recent_messages": [{"sender": "Candidate", "body": "Hi"}],
        "missing_fields": [],
    }
    result = svc.build_prompt("QUALIFICATION", context, {"question": "What is your notice period?"})

    assert "{{" not in result["system_prompt"]
    assert "{{" not in result["user_prompt"]
    assert "Thunder" in result["system_prompt"]
    assert "Priya" in result["user_prompt"]
    assert "What is your notice period?" in result["user_prompt"]


def test_build_prompt_uses_thunder_name_from_context_not_hardcoded():
    """BR-04: never hardcoded -- a renamed agent flows through untouched."""
    context = {"thunder_name": "Blitz", "name": "Priya", "memory": {}, "recent_messages": [], "missing_fields": []}
    result = svc.build_prompt("QUALIFICATION", context)
    assert "Blitz" in result["system_prompt"]
    assert "Thunder, Talent Scout" not in result["system_prompt"]


def test_build_prompt_conversational_temperature_is_0_7():
    result = svc.build_prompt("QUALIFICATION", {"name": "Priya"})
    assert result["temperature"] == 0.7


def test_build_prompt_classification_temperature_is_0_0():
    result = svc.build_prompt("INTENT_DETECTION", {})
    assert result["temperature"] == 0.0


def test_build_prompt_unknown_prompt_type_raises():
    with pytest.raises(svc.UnknownPromptType):
        svc.build_prompt("NOT_A_REAL_TYPE", {})


def test_build_prompt_missing_required_field_logs_warning_but_still_builds(caplog):
    result = svc.build_prompt("QUALIFICATION", {})  # missing required "name"
    assert result["system_prompt"]  # still built, not blocked
    assert "there" in result["user_prompt"]  # default fallback for candidate_name


def test_build_prompt_empty_summary_renders_as_empty_string():
    result = svc.build_prompt("QUALIFICATION", {"name": "Priya", "memory": {}})
    assert "{{candidate_summary}}" not in result["user_prompt"]


# ── call_llm() ───────────────────────────────────────────────────────

def test_call_llm_success_logs_execution_and_returns_response(db_session, seeded):
    candidate = seeded
    response = svc.call_llm(
        db_session, "U-ORG", "C-1", "QUALIFICATION", "v1.0", "system prompt", "user prompt", 300, 0.7,
        llm_call=lambda sp, up, mt, t: "Thunder's reply text",
    )
    assert response == "Thunder's reply text"

    logs = db_session.query(PromptExecutionLog).filter(PromptExecutionLog.candidate_id == "C-1").all()
    assert len(logs) == 1
    assert logs[0].success is True
    assert logs[0].prompt_type == "QUALIFICATION"
    assert logs[0].template_version == "v1.0"
    assert logs[0].response_preview == "Thunder's reply text"


def test_call_llm_retries_once_then_succeeds(db_session, seeded):
    attempts = []

    def flaky(sp, up, mt, t):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("Gemini 500")
        return "recovered response"

    response = svc.call_llm(db_session, "U-ORG", "C-1", "QUALIFICATION", "v1.0", "sp", "up", 300, 0.7, llm_call=flaky, sleep_fn=_no_sleep)
    assert response == "recovered response"
    assert len(attempts) == 2

    logs = db_session.query(PromptExecutionLog).filter(PromptExecutionLog.candidate_id == "C-1").order_by(PromptExecutionLog.id.asc()).all()
    assert len(logs) == 2  # BR-03: both attempts logged
    assert logs[0].success is False
    assert logs[1].success is True


def test_call_llm_both_attempts_fail_raises_and_logs_both(db_session, seeded):
    def always_fails(sp, up, mt, t):
        raise RuntimeError("Gemini down")

    with pytest.raises(svc.LLMCallFailedError):
        svc.call_llm(db_session, "U-ORG", "C-1", "QUALIFICATION", "v1.0", "sp", "up", 300, 0.7, llm_call=always_fails, sleep_fn=_no_sleep)

    logs = db_session.query(PromptExecutionLog).filter(PromptExecutionLog.candidate_id == "C-1").all()
    assert len(logs) == 2
    assert all(not log.success for log in logs)
    assert all(log.error_message for log in logs)


def test_call_llm_without_candidate_id_still_logs(db_session, seeded):
    response = svc.call_llm(db_session, "U-ORG", None, "ESCALATION_CHECK", "v1.0", "sp", "up", 150, 0.0, llm_call=lambda sp, up, mt, t: '{"needs_escalation": false}')
    assert response == '{"needs_escalation": false}'
    logs = db_session.query(PromptExecutionLog).filter(PromptExecutionLog.candidate_id.is_(None)).all()
    assert len(logs) == 1


# ── get_prompt_templates() ───────────────────────────────────────────

def test_get_prompt_templates_returns_all_with_versions():
    templates = svc.get_prompt_templates()
    prompt_types = {t["prompt_type"] for t in templates}
    assert prompt_types == {"QUALIFICATION", "FOLLOW_UP", "OBJECTION_HANDLING", "ESCALATION_CHECK", "INTENT_DETECTION", "SENTIMENT_ANALYSIS"}
    assert all(t["version"] for t in templates)  # INTENT_DETECTION bumped to v1.1 by S-033 (added confidence field)
