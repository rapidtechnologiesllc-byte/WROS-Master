"""
S-011/HRMS-0411 -- AI Recruiter Assignment Engine.

Real Thunder identity config: resolve_thunder_config() reads per-tenant
ai_agent_name/persona from the tenant's own Users row (this codebase's
real tenant_id semantics -- see the function's docstring), falling
back to "Thunder" + a default persona when unset (BR-02: never blank).
assign_ai_agent()'s CandidateAIAssignment record stores the resolved
config, not the internal AI_AGENT_NAME/AI_AGENT_PERSONA ownership
tokens (which stay untouched to avoid regressing R-08 logic).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.notification import Notification
from app.models.user import Users

import app.services.ai_conversation_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__,
        CandidateAIAssignment.__table__, Notification.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture(autouse=True)
def _stub_missing_fields_email(monkeypatch):
    """assign_ai_agent() tries to send a real missing-fields email via
    MS Graph -- stub it out, unrelated to what these tests check."""
    monkeypatch.setattr(svc, "_send_missing_fields_email", lambda *a, **kw: False)


def test_resolve_thunder_config_defaults_when_no_tenant_row(db_session):
    config = svc.resolve_thunder_config(db_session, "nonexistent-tenant")
    assert config["name"] == svc.DEFAULT_THUNDER_DISPLAY_NAME
    assert config["persona"] == svc.DEFAULT_THUNDER_PERSONA_TEXT


def test_resolve_thunder_config_uses_tenant_override(db_session):
    tenant = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h",
                    ai_agent_name="Zappy", ai_agent_persona="I am Zappy, your custom recruiter bot.")
    db_session.add(tenant)
    db_session.commit()

    config = svc.resolve_thunder_config(db_session, "U-ORG")
    assert config["name"] == "Zappy"
    assert config["persona"] == "I am Zappy, your custom recruiter bot."


def test_resolve_thunder_config_blank_name_falls_back_to_default(db_session):
    """BR-02: an agent name must never reach a candidate blank."""
    tenant = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h",
                    ai_agent_name="   ", ai_agent_persona="some persona")
    db_session.add(tenant)
    db_session.commit()

    config = svc.resolve_thunder_config(db_session, "U-ORG")
    assert config["name"] == svc.DEFAULT_THUNDER_DISPLAY_NAME


def test_assign_ai_agent_stores_resolved_config_on_assignment(db_session):
    tenant = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate = Candidate(candidateID="C-100", candidateEmail="c@example.com", candidatePassword="h")
    db_session.add_all([tenant, candidate])
    db_session.commit()

    result = svc.assign_ai_agent(candidate_id="C-100", tenant_id="U-ORG", assigned_by=None, db=db_session)

    assignment = db_session.query(CandidateAIAssignment).filter(CandidateAIAssignment.id == result["assignment_id"]).first()
    assert assignment.ai_agent_name == "Thunder"
    assert assignment.is_active is True


def test_assign_ai_agent_uses_tenant_custom_name(db_session):
    tenant = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h",
                    ai_agent_name="Nova", ai_agent_persona="I am Nova.")
    candidate = Candidate(candidateID="C-100", candidateEmail="c@example.com", candidatePassword="h")
    db_session.add_all([tenant, candidate])
    db_session.commit()

    result = svc.assign_ai_agent(candidate_id="C-100", tenant_id="U-ORG", assigned_by=None, db=db_session)
    assignment = db_session.query(CandidateAIAssignment).filter(CandidateAIAssignment.id == result["assignment_id"]).first()
    assert assignment.ai_agent_name == "Nova"
    assert assignment.ai_agent_persona == "I am Nova."


def test_reassign_ai_agent_deactivates_old_creates_new(db_session):
    tenant = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate = Candidate(candidateID="C-100", candidateEmail="c@example.com", candidatePassword="h")
    db_session.add_all([tenant, candidate])
    db_session.commit()

    first = svc.assign_ai_agent(candidate_id="C-100", tenant_id="U-ORG", assigned_by=None, db=db_session)

    # Tenant updates config, wants to push it to the existing candidate.
    tenant.ai_agent_name = "Blaze"
    db_session.commit()

    second = svc.reassign_ai_agent(candidate_id="C-100", tenant_id="U-ORG", assigned_by="U-REC", db=db_session)

    old_assignment = db_session.query(CandidateAIAssignment).filter(CandidateAIAssignment.id == first["assignment_id"]).first()
    new_assignment = db_session.query(CandidateAIAssignment).filter(CandidateAIAssignment.id == second["assignment_id"]).first()

    assert old_assignment.is_active is False
    assert new_assignment.is_active is True
    assert new_assignment.ai_agent_name == "Blaze"


def test_tenant_config_change_does_not_retroactively_update_existing_assignment(db_session):
    """AC: 'Tenant config change after assignment does NOT auto-update
    existing candidate assignments' -- the point-in-time copy stays put
    unless reassign_ai_agent() is explicitly called again."""
    tenant = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate = Candidate(candidateID="C-100", candidateEmail="c@example.com", candidatePassword="h")
    db_session.add_all([tenant, candidate])
    db_session.commit()

    result = svc.assign_ai_agent(candidate_id="C-100", tenant_id="U-ORG", assigned_by=None, db=db_session)

    tenant.ai_agent_name = "ChangedLater"
    db_session.commit()

    assignment = db_session.query(CandidateAIAssignment).filter(CandidateAIAssignment.id == result["assignment_id"]).first()
    assert assignment.ai_agent_name == "Thunder"  # unchanged despite the tenant config edit


def test_get_active_ai_assignment_returns_only_active(db_session):
    tenant = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate = Candidate(candidateID="C-100", candidateEmail="c@example.com", candidatePassword="h")
    db_session.add_all([tenant, candidate])
    db_session.commit()

    svc.assign_ai_agent(candidate_id="C-100", tenant_id="U-ORG", assigned_by=None, db=db_session)
    svc.reassign_ai_agent(candidate_id="C-100", tenant_id="U-ORG", assigned_by=None, db=db_session)

    active = svc.get_active_ai_assignment(db_session, "C-100", "U-ORG")
    all_assignments = db_session.query(CandidateAIAssignment).filter(CandidateAIAssignment.candidate_id == "C-100").all()

    assert len(all_assignments) == 2
    assert active.id == max(a.id for a in all_assignments)
    assert active.is_active is True
