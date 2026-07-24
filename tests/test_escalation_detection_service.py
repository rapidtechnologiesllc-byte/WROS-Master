"""
S-035/HRMS-0435 -- Human Escalation Detection.

Real architecture under test (see escalation_detection_service module
docstring): BR-01 rules checked before any LLM call; BR-02 legal/
compliance keywords escalate immediately with dual notification; BR-03
LLM failure collapses to needs_escalation=False, never raises; BR-04
exit message sent before ownership transfers. No fictional ESCALATED
status enum -- escalation_state (conversation_state_service.escalate/
resolve_escalation) and ownership (pause_for_recruiter_queue/
resume_to_thunder) are the real, separate axes used instead.

Throwaway SQLite -- never the real database.
"""
import json
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.candidate_field_skip import CandidateFieldSkip
from app.models.candidate_memory import CandidateMemory, CandidateMemoryFact
from app.models.consent import ConsentRecord
from app.models.notification import Notification
from app.models.prompt_execution_log import PromptExecutionLog
from app.models.sla_breach import CandidateSLABreach
from app.models.user import Jobs, Users

import app.services.escalation_detection_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__, Jobs.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, CandidateFieldSkip.__table__,
        CandidateMemory.__table__, CandidateMemoryFact.__table__, CandidateSLABreach.__table__,
        CandidateAIAssignment.__table__, Notification.__table__, PromptExecutionLog.__table__,
        ConsentRecord.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)
        import app.services.candidate_context_service as ctx_svc
        ctx_svc._CONTEXT_CACHE.clear()


@pytest.fixture()
def seeded(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h", tenant_id=None, ai_agent_name="Thunder")
    db_session.add(owner)
    db_session.commit()

    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya", candidateLastName="Sharma")
    db_session.add(candidate)
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="web_chat")
    db_session.add(conv)
    db_session.add(ConsentRecord(subject_type="candidate", subject_id="C-1", consent_type="web_chat_outreach", consent_given=True, captured_by="candidate_self_service"))
    db_session.commit()

    return candidate, conv


def _llm_returning(payload_dict):
    return lambda sp, up, mt, t: json.dumps(payload_dict)


def _llm_raising(exc):
    def _raise(sp, up, mt, t):
        raise exc
    return _raise


# ── TC-001: keyword-based rule escalation ─────────────────────────────

def test_human_request_keyword_escalates_via_rule(db_session, seeded):
    candidate, conv = seeded
    result = svc.check_escalation(db_session, "U-ORG", "C-1", "I want to speak to a human please.")
    assert result["needs_escalation"] is True
    assert result["trigger_type"] == "RULE"


def test_call_me_keyword_escalates_via_rule(db_session, seeded):
    candidate, conv = seeded
    result = svc.check_escalation(db_session, "U-ORG", "C-1", "Please call me instead.")
    assert result["needs_escalation"] is True
    assert result["trigger_type"] == "RULE"


# ── BR-02 / TC: legal keyword -> immediate escalation, no LLM call ─────

def test_legal_keyword_escalates_without_calling_llm(db_session, seeded):
    candidate, conv = seeded
    calls = []
    llm = lambda sp, up, mt, t: calls.append(1) or json.dumps({"needs_escalation": False})
    result = svc.check_escalation(db_session, "U-ORG", "C-1", "I'm going to talk to my lawyer about this.", llm_call=llm)
    assert result["needs_escalation"] is True
    assert result["trigger_type"] == "RULE"
    assert "Legal/compliance" in result["reason"]
    assert calls == []  # BR-02: no LLM call at all


def test_discrimination_keyword_escalates(db_session, seeded):
    candidate, conv = seeded
    result = svc.check_escalation(db_session, "U-ORG", "C-1", "This feels like discrimination.")
    assert result["needs_escalation"] is True
    assert result["trigger_type"] == "RULE"


# ── Rule #2: repeated question ─────────────────────────────────────────

def test_repeated_question_escalates_via_rule(db_session, seeded):
    candidate, conv = seeded
    for _ in range(2):
        db_session.add(ConversationEvent(
            conversation_id=conv.id, event_type="candidate_reply",
            event_data={"channel": "web_chat", "body": "What is the salary for this role?"}, triggered_by="candidate",
        ))
    db_session.commit()

    result = svc.check_escalation(db_session, "U-ORG", "C-1", "What is the salary for this role?")
    assert result["needs_escalation"] is True
    assert result["trigger_type"] == "RULE"
    assert "same question" in result["reason"]


def test_different_questions_do_not_trigger_repeated_rule(db_session, seeded):
    candidate, conv = seeded
    db_session.add_all([
        ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={"channel": "web_chat", "body": "What is the salary?"}, triggered_by="candidate"),
        ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={"channel": "web_chat", "body": "Is this remote?"}, triggered_by="candidate"),
    ])
    db_session.commit()

    result = svc.check_escalation(db_session, "U-ORG", "C-1", "When does it start?", llm_call=_llm_returning({"needs_escalation": False}))
    assert result["needs_escalation"] is False


# ── TC-002: LLM-based escalation (no rule fired) ───────────────────────

def test_llm_escalates_on_complex_objection(db_session, seeded):
    candidate, conv = seeded
    result = svc.check_escalation(
        db_session, "U-ORG", "C-1", "I'm really unhappy with how this process is going.",
        llm_call=_llm_returning({"needs_escalation": True, "reason": "Candidate expressing distress"}),
    )
    assert result["needs_escalation"] is True
    assert result["trigger_type"] == "LLM"
    assert result["reason"] == "Candidate expressing distress"


def test_llm_no_escalation_needed(db_session, seeded):
    candidate, conv = seeded
    result = svc.check_escalation(
        db_session, "U-ORG", "C-1", "Sounds good, thanks!",
        llm_call=_llm_returning({"needs_escalation": False}),
    )
    assert result["needs_escalation"] is False
    assert result["trigger_type"] is None


# ── TC-004 / BR-03: LLM failure -> false, never raises ─────────────────

def test_llm_failure_returns_false_never_raises(db_session, seeded):
    candidate, conv = seeded
    result = svc.check_escalation(db_session, "U-ORG", "C-1", "Some ordinary message.", llm_call=_llm_raising(RuntimeError("Gemini down")))
    assert result == {"needs_escalation": False, "reason": None, "trigger_type": None}


def test_invalid_json_returns_false_never_raises(db_session, seeded):
    candidate, conv = seeded
    result = svc.check_escalation(db_session, "U-ORG", "C-1", "Some ordinary message.", llm_call=lambda sp, up, mt, t: "not json")
    assert result["needs_escalation"] is False


# ── TC-003: full escalation execution flow ─────────────────────────────

def test_execute_escalation_full_flow(db_session, seeded):
    candidate, conv = seeded
    svc.execute_escalation(db_session, conv, candidate, reason="Candidate asked for a human", trigger_type="RULE")

    db_session.refresh(conv)
    assert conv.escalation_state == "escalated"
    assert conv.owner_type == "hr_user"
    assert conv.owner_id is None  # unassigned queue -- any recruiter can pick up

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id).all()
    event_types = [e.event_type for e in events]
    assert "escalation_triggered" in event_types
    assert "ownership_changed" in event_types
    assert "ai_message_sent" in event_types  # BR-04 exit message

    exit_events = [e for e in events if e.event_type == "ai_message_sent"]
    assert exit_events[0].event_data["body"] == svc.ESCALATION_EXIT_MESSAGE

    # BR-04: exit message logged before the ownership_changed event.
    exit_event = next(e for e in events if e.event_type == "ai_message_sent")
    ownership_event = next(e for e in events if e.event_type == "ownership_changed")
    assert exit_event.id < ownership_event.id


def test_execute_escalation_notifies_recruiter(db_session, seeded):
    candidate, conv = seeded
    svc.execute_escalation(db_session, conv, candidate, reason="Candidate asked for a human", trigger_type="RULE")

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].priority_tier == "P0"
    assert "Priya Sharma" in notifications[0].message


def test_execute_escalation_legal_trigger_notifies_manager_too(db_session, seeded):
    candidate, conv = seeded
    svc.execute_escalation(db_session, conv, candidate, reason="Legal/compliance keyword detected: 'lawyer'", trigger_type="RULE")

    notifications = db_session.query(Notification).all()
    # Same recipient resolves for both "recruiter" and "manager" analog in
    # this single-owner test tenant -- see module docstring on why that
    # collapses to one recipient when they're the same real user. Assert
    # at least one P0 legal-flagged notification exists.
    assert any("LEGAL/COMPLIANCE" in n.message for n in notifications)


def test_execute_escalation_assigned_recruiter_and_manager_both_notified_when_different(db_session, seeded):
    candidate, conv = seeded
    recruiter = Users(UserID="U-RECRUITER", UserRole="Recruiter", UserEmail="r@blitzenx.com", UserPassword="h", tenant_id=None)
    db_session.add(recruiter)
    db_session.commit()
    db_session.add(CandidateAIAssignment(tenant_id="U-ORG", candidate_id="C-1", ai_agent_name="Thunder", assigned_by="U-RECRUITER"))
    db_session.commit()

    svc.execute_escalation(db_session, conv, candidate, reason="Legal/compliance keyword detected: 'lawyer'", trigger_type="RULE")

    notifications = db_session.query(Notification).all()
    recipients = {n.recipient_id for n in notifications}
    assert recipients == {"U-RECRUITER", "U-ORG"}  # recruiter + manager-analog, both notified


# ── Step 4 / TC-005: de-escalation resumes Thunder ─────────────────────

def test_resolve_and_resume_clears_escalation_and_restores_ownership(db_session, seeded):
    candidate, conv = seeded
    svc.execute_escalation(db_session, conv, candidate, reason="Candidate asked for a human", trigger_type="RULE")
    db_session.refresh(conv)
    assert conv.escalation_state == "escalated"

    result = svc.resolve_and_resume(
        db_session, conv, candidate, "U-ORG", triggered_by="hr_user",
        llm_call=lambda prompt: "Great, thanks! What is your current notice period?",
    )

    db_session.refresh(conv)
    assert conv.escalation_state == "resolved"
    assert conv.owner_type == "ai_agent"
    assert conv.owner_id == "Thunder"
    assert result["escalation_state"] == "resolved"

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "escalation_resolved").all()
    assert len(events) == 1


# ── Hand-back-from-escalation gap (real bug fixed alongside this story) ─

def test_pause_for_recruiter_queue_is_unassigned(db_session, seeded):
    candidate, conv = seeded
    import app.services.conversation_state_service as state_svc
    state_svc.pause_for_recruiter_queue(db_session, conv, reason="test")
    db_session.commit()
    db_session.refresh(conv)
    assert conv.owner_type == "hr_user"
    assert conv.owner_id is None
