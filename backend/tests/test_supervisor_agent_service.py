"""
import logging
S-066/HRMS-0466 -- Supervisor Agent, Multi-Agent Coordinator.

Real architecture under test (see supervisor_agent_service module
docstring): no Redis, no distributed lock, no 7 fictional sub-agent
classes -- this codebase's ~18 already-independent scheduled jobs
already ARE the "log and retry till complete" dispatch mechanism
Avinash asked for. run_supervisor_cycle() builds the real, missing
piece instead: a per-cycle observability rollup (agent_execution_log),
a real BR-01/BR-03 conflict audit, and Step 5's metrics via S-071's
already-built thunder-vs-human breakdown.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.agent_execution_log import AgentExecutionLog
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_joining_score import CandidateJoiningScore
from app.models.employee import Employee
from app.models.event_log import EventLog
from app.models.interview_pipeline import SubmissionInterview
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.submission import Submission
from app.models.user import Users, Jobs

import app.services.supervisor_agent_service as svc

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Jobs.__table__, Candidate.__table__, CandidateInfoForm.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, CandidateJobScore.__table__,
        CandidateJoiningScore.__table__, Employee.__table__, SubmissionInterview.__table__,
        OfferLetter.__table__, PreboardingDocument.__table__, Submission.__table__,
        AgentExecutionLog.__table__, EventLog.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

@pytest.fixture()
def tenant(db_session):
    user = Users(UserID="U-ORG", UserRole="Super User", UserEmail="org@blitzenx.com", UserPassword="h", thunder_enabled=True)
    db_session.add(user)
    db_session.commit()
    return user

def _make_candidate(db, cid, tenant_id, *, owner_type="ai_agent", escalation_state="none", is_thunder_paused=False):
    candidate = Candidate(candidateID=cid, candidateEmail=f"{cid}@example.com", candidatePassword="h", candidateFirstName="Test")
    db.add(candidate)
    db.commit()
    conv = CandidateConversation(
        tenant_id=tenant_id, candidate_id=cid, status="open", owner_type=owner_type,
        owner_id="Thunder", escalation_state=escalation_state, is_thunder_paused=is_thunder_paused,
    )
    db.add(conv)
    db.commit()
    return candidate, conv

def test_human_owned_conversation_skipped_br01(db_session, tenant):
    _, conv = _make_candidate(db_session, "C-1", "U-ORG", owner_type="hr_user")
    result = svc.run_supervisor_cycle(db_session, "U-ORG")
    logs = db_session.query(AgentExecutionLog).filter(AgentExecutionLog.candidate_id == "C-1").all()
    assert len(logs) == 1
    assert logs[0].action_taken == "SKIPPED"
    assert logs[0].action_data["reason"] == "HUMAN_OWNED"
    assert result["skipped"] == 1

def test_escalated_conversation_skipped(db_session, tenant):
    _make_candidate(db_session, "C-1", "U-ORG", escalation_state="escalated")
    svc.run_supervisor_cycle(db_session, "U-ORG")
    logs = db_session.query(AgentExecutionLog).filter(AgentExecutionLog.candidate_id == "C-1").all()
    assert logs[0].action_data["reason"] == "ESCALATED"

def test_paused_conversation_skipped_s075(db_session, tenant):
    _make_candidate(db_session, "C-1", "U-ORG", is_thunder_paused=True)
    svc.run_supervisor_cycle(db_session, "U-ORG")
    logs = db_session.query(AgentExecutionLog).filter(AgentExecutionLog.candidate_id == "C-1").all()
    assert logs[0].action_data["reason"] == "THUNDER_PAUSED"

def test_ai_owned_active_conversation_evaluated_not_skipped(db_session, tenant):
    _make_candidate(db_session, "C-1", "U-ORG")
    svc.run_supervisor_cycle(db_session, "U-ORG")
    logs = db_session.query(AgentExecutionLog).filter(AgentExecutionLog.candidate_id == "C-1").all()
    assert logs[0].action_taken == "EVALUATED"
    assert logs[0].agent_name in svc.STAGE_TO_AGENT_NAME.values()

def test_closed_conversations_excluded(db_session, tenant):
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Test")
    db_session.add(candidate)
    db_session.commit()
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="closed", owner_type="ai_agent", owner_id="Thunder", escalation_state="none")
    db_session.add(conv)
    db_session.commit()

    result = svc.run_supervisor_cycle(db_session, "U-ORG")
    logs = db_session.query(AgentExecutionLog).filter(AgentExecutionLog.candidate_id == "C-1").all()
    assert len(logs) == 0
    assert result["candidates_evaluated"] == 0

def test_cycle_emits_supervisor_cycle_completed_event(db_session, tenant):
    _make_candidate(db_session, "C-1", "U-ORG")
    svc.run_supervisor_cycle(db_session, "U-ORG")
    events = db_session.query(EventLog).filter(EventLog.event_type == "supervisor.cycle_completed").all()
    assert len(events) == 1
    assert events[0].tenant_id == "U-ORG"
    assert events[0].payload["candidates_evaluated"] == 1

def test_conflict_detected_when_ai_message_sent_on_human_owned_conversation(db_session, tenant):
    """BR-01/BR-03 real audit -- a defense-in-depth check, not a
    preventive lock (see module docstring on why locking is
    unnecessary in this single-process deployment)."""
    _, conv = _make_candidate(db_session, "C-1", "U-ORG", owner_type="hr_user")
    db_session.add(ConversationEvent(
        conversation_id=conv.id, event_type="ai_message_sent", event_data={}, triggered_by="ai_agent",
        created_at=datetime.utcnow(),
    ))
    db_session.commit()

    result = svc.run_supervisor_cycle(db_session, "U-ORG")
    assert result["conflicts_detected"] == 1

def test_no_conflict_when_ai_message_sent_on_ai_owned_conversation(db_session, tenant):
    _, conv = _make_candidate(db_session, "C-1", "U-ORG")
    db_session.add(ConversationEvent(
        conversation_id=conv.id, event_type="ai_message_sent", event_data={}, triggered_by="ai_agent",
        created_at=datetime.utcnow(),
    ))
    db_session.commit()

    result = svc.run_supervisor_cycle(db_session, "U-ORG")
    assert result["conflicts_detected"] == 0

def test_run_supervisor_cycle_across_all_tenants_when_tenant_id_omitted(db_session, tenant):
    db_session.add(Users(UserID="U-OTHER", UserRole="Super User", UserEmail="other@blitzenx.com", UserPassword="h"))
    db_session.commit()
    _make_candidate(db_session, "C-1", "U-ORG")
    _make_candidate(db_session, "C-2", "U-OTHER")

    result = svc.run_supervisor_cycle(db_session)  # no tenant_id -- all tenants
    assert result["tenants_processed"] == 2
    assert result["candidates_evaluated"] == 2

def test_one_bad_tenant_does_not_abort_the_whole_cycle(db_session, tenant, monkeypatch):
    _make_candidate(db_session, "C-1", "U-ORG")

    original = svc._run_cycle_for_tenant
    def _boom(db, tenant_id, window_start, today_start):
        if tenant_id == "U-ORG":
            raise RuntimeError("simulated failure")
        return original(db, tenant_id, window_start, today_start)
    monkeypatch.setattr(svc, "_run_cycle_for_tenant", _boom)

    result = svc.run_supervisor_cycle(db_session, "U-ORG")
    assert result["tenants_processed"] == 0  # failed tenant not counted, but no exception raised
