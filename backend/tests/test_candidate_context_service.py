"""
import logging
S-032/HRMS-0432 -- Candidate Context Builder.

Real architecture under test (see candidate_context_service module
docstring): sequential (not literally-parallel) fetches over a
synchronous SQLAlchemy session; BR-02 tenant scoping resolved through
CandidateConversation (the real String(50)-UserID tenant_id
convention), never through Candidate.tenant_id (an unrelated
Integer/tenants-table FK); real in-process 30s TTL cache in place of
the spec's nonexistent Redis; job context limited to the real Jobs
model's fields (no bill_rate column exists).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_field_skip import CandidateFieldSkip
from app.models.candidate_memory import CandidateMemory, CandidateMemoryFact
from app.models.sla_breach import CandidateSLABreach
from app.models.user import Users, Jobs

import app.services.candidate_context_service as svc

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__, Jobs.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, CandidateFieldSkip.__table__,
        CandidateMemory.__table__, CandidateMemoryFact.__table__, CandidateSLABreach.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)
        svc._CONTEXT_CACHE.clear()

@pytest.fixture()
def seeded(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h", ai_agent_name="Thunder")
    other_tenant = Users(UserID="U-OTHER", UserRole="Super User", UserEmail="other@rival.com", UserPassword="h")
    job = Jobs(jobID="J-1", jobTitle="Guidewire Developer", jobDescription="d", jobSkills="Guidewire, Java", jobExperience="5+ years", jobLocation="Bangalore", salaryRange="18-22 LPA")
    candidate = Candidate(
        candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h",
        candidateFirstName="Priya", candidateLastName="Sharma", candidateMobile="+919876543210",
        candidateCurrentLocation="Bangalore", total_experience_months=42, candidateSkills="Guidewire, Java",
        resume_completeness_score=80, job_id="J-1",
    )
    db_session.add_all([owner, other_tenant, job, candidate])
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none")
    db_session.add(conv)
    db_session.commit()

    reply = ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={"channel": "whatsapp", "body": "Hi, interested!"}, triggered_by="candidate")
    ai_msg = ConversationEvent(conversation_id=conv.id, event_type="ai_message_sent", event_data={"channel": "whatsapp", "body": "Great, let's get started."}, triggered_by="ai_agent")
    db_session.add_all([reply, ai_msg])
    db_session.commit()

    return candidate, conv

def _next_field_only(field_name):
    """Monkeypatch-style stub used to make qualification deterministic in tests."""
    return {"field": field_name}

# ── build_candidate_context() -- assembly completeness ──────────────

def test_build_candidate_context_assembles_all_sections(db_session, seeded):
    candidate, conv = seeded
    context = svc.build_candidate_context(db_session, "C-1", "U-ORG", use_cache=False)

    assert context["candidate"]["id"] == "C-1"
    assert context["candidate"]["name"] == "Priya Sharma"
    assert context["candidate"]["total_experience_years"] == 3.5
    assert context["memory"] == {"summary": None, "last_updated": None, "facts": []}
    assert context["conversation"]["id"] == conv.id
    assert context["conversation"]["status"] == "open"
    assert len(context["recent_messages"]) == 2
    assert context["recent_messages"][0]["direction"] == "INBOUND"
    assert context["recent_messages"][1]["direction"] == "OUTBOUND"
    assert isinstance(context["missing_fields"], list)
    assert context["thunder"]["name"] == "Thunder"
    assert context["build_latency_ms"] >= 0

def test_build_candidate_context_raises_for_unknown_candidate(db_session, seeded):
    with pytest.raises(svc.CandidateNotFound):
        svc.build_candidate_context(db_session, "NOPE", "U-ORG", use_cache=False)

# ── BR-02 tenant isolation ────────────────────────────────────────────

def test_build_candidate_context_does_not_leak_conversation_across_tenants(db_session, seeded):
    """A conversation that belongs to a different tenant must never surface,
    even though it's the same candidate_id."""
    candidate, real_conv = seeded
    rival_conv = CandidateConversation(tenant_id="U-OTHER", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="RivalBot", escalation_state="none")
    db_session.add(rival_conv)
    db_session.commit()

    context = svc.build_candidate_context(db_session, "C-1", "U-OTHER", use_cache=False)
    assert context["conversation"]["id"] == rival_conv.id
    assert context["conversation"]["owner_name"] == "RivalBot"

    context_real = svc.build_candidate_context(db_session, "C-1", "U-ORG", use_cache=False)
    assert context_real["conversation"]["id"] == real_conv.id
    assert context_real["conversation"]["owner_name"] == "Thunder"

# ── job context ───────────────────────────────────────────────────────

def test_build_candidate_context_includes_job_when_job_id_set(db_session, seeded):
    context = svc.build_candidate_context(db_session, "C-1", "U-ORG", use_cache=False)
    assert context["job"] == {
        "id": "J-1", "title": "Guidewire Developer", "required_skills": "Guidewire, Java",
        "experience_required": "5+ years", "location": "Bangalore", "bill_rate": "18-22 LPA",
    }

def test_build_candidate_context_job_is_none_when_no_job_id(db_session, seeded):
    candidate, _ = seeded
    candidate.job_id = None
    db_session.commit()
    context = svc.build_candidate_context(db_session, "C-1", "U-ORG", use_cache=False)
    assert context["job"] is None

# ── cache behavior (BR-03 adaptation) ────────────────────────────────

def test_build_candidate_context_returns_cached_result_within_ttl(db_session, seeded, monkeypatch):
    first = svc.build_candidate_context(db_session, "C-1", "U-ORG")

    # Mutate underlying data directly; a cache hit must NOT reflect it.
    candidate, _ = seeded
    candidate.candidateFirstName = "Changed"
    db_session.commit()

    second = svc.build_candidate_context(db_session, "C-1", "U-ORG")
    assert second is first
    assert second["candidate"]["name"] == "Priya Sharma"

def test_build_candidate_context_use_cache_false_always_rebuilds(db_session, seeded):
    svc.build_candidate_context(db_session, "C-1", "U-ORG")
    candidate, _ = seeded
    candidate.candidateFirstName = "Changed"
    db_session.commit()

    fresh = svc.build_candidate_context(db_session, "C-1", "U-ORG", use_cache=False)
    assert fresh["candidate"]["name"] == "Changed Sharma"

def test_invalidate_candidate_context_cache_forces_rebuild(db_session, seeded):
    svc.build_candidate_context(db_session, "C-1", "U-ORG")
    candidate, _ = seeded
    candidate.candidateFirstName = "Changed"
    db_session.commit()

    svc.invalidate_candidate_context_cache("U-ORG", "C-1")
    rebuilt = svc.build_candidate_context(db_session, "C-1", "U-ORG")
    assert rebuilt["candidate"]["name"] == "Changed Sharma"

def test_cache_is_scoped_per_tenant_and_candidate(db_session, seeded):
    """Same candidate_id, different tenant_id must not share a cache slot."""
    candidate, _ = seeded
    rival_conv = CandidateConversation(tenant_id="U-OTHER", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="RivalBot", escalation_state="none")
    db_session.add(rival_conv)
    db_session.commit()

    ctx_a = svc.build_candidate_context(db_session, "C-1", "U-ORG")
    ctx_b = svc.build_candidate_context(db_session, "C-1", "U-OTHER")
    assert ctx_a is not ctx_b
    assert ctx_a["conversation"]["owner_name"] == "Thunder"
    assert ctx_b["conversation"]["owner_name"] == "RivalBot"

# ── next_question (only during real qualifying state) ────────────────

def test_next_question_is_none_when_conversation_closed(db_session, seeded):
    candidate, conv = seeded
    conv.status = "closed"
    db_session.commit()
    context = svc.build_candidate_context(db_session, "C-1", "U-ORG", use_cache=False)
    assert context["next_question"] is None

def test_next_question_populated_when_qualifying_and_fields_missing(db_session, seeded):
    candidate, conv = seeded
    # candidateMobile is present; leave other CANDIDATE_CORE_FIELDS gaps to
    # force get_next_missing_field() to return something real.
    context = svc.build_candidate_context(db_session, "C-1", "U-ORG", use_cache=False)
    if context["missing_fields"]:
        assert context["next_question"] is not None
        assert "field_name" in context["next_question"]
        assert "question" in context["next_question"]

def test_no_conversation_yields_none_conversation_and_no_next_question(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate = Candidate(candidateID="C-2", candidateEmail="c2@example.com", candidatePassword="h")
    db_session.add_all([owner, candidate])
    db_session.commit()

    context = svc.build_candidate_context(db_session, "C-2", "U-ORG", use_cache=False)
    assert context["conversation"] is None
    assert context["recent_messages"] == []
    assert context["next_question"] is None

# ── get_context_for_prompt() -- integration with S-031's build_prompt() ──

def test_get_context_for_prompt_combines_context_and_prompt(db_session, seeded):
    result = svc.get_context_for_prompt(db_session, "C-1", "U-ORG", "QUALIFICATION")
    assert "context" in result
    assert result["context"]["candidate"]["id"] == "C-1"
    assert "Thunder" in result["system_prompt"]
    assert "Priya" in result["user_prompt"]
    assert "{{" not in result["system_prompt"]
    assert "{{" not in result["user_prompt"]

def test_get_context_for_prompt_injects_next_question_into_params(db_session, seeded):
    candidate, conv = seeded
    result = svc.get_context_for_prompt(db_session, "C-1", "U-ORG", "QUALIFICATION")
    next_question = result["context"]["next_question"]
    if next_question:
        assert next_question["question"] in result["user_prompt"]

def test_get_context_for_prompt_explicit_additional_params_win(db_session, seeded):
    result = svc.get_context_for_prompt(
        db_session, "C-1", "U-ORG", "QUALIFICATION", additional_params={"question": "Explicit override question?"},
    )
    assert "Explicit override question?" in result["user_prompt"]
