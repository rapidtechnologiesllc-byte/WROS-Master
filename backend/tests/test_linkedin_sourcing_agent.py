"""
import logging
HRMS-1103 -- LinkedIn Sourcing Agent Loop.

Proves: BR-1103-03 (atomic OPEN->PROCESSING claim), the LLM-generation-
failure re-queue path, the search-execution-failure counter + AC-6 RM
escalation, AC-4 (confirmed duplicates excluded from staged_candidates
entirely), AC-3/BR-1103-01 (this agent never creates a real candidate
directly -- only promote_staged_candidate(), the explicit human path,
does), and the Router hand-off call.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.client import Client
from app.models.consent import ConsentRecord
from app.models.demand import Demand
from app.models.notification import Notification
from app.models.sourcing import SourcingAlert, SourcingSearchRun, StagedCandidate
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.linkedin_sourcing_service import (
    StagedCandidateAlreadyPromoted,
    claim_alert,
    process_sourcing_alert,
    promote_staged_candidate,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, Client.__table__, Demand.__table__,
        SourcingAlert.__table__, SourcingSearchRun.__table__, StagedCandidate.__table__,
        Candidate.__table__, ConsentRecord.__table__, Notification.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def alert(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    client = Client(company_name="Acme Carrier", tenant_id=tenant.id)
    db_session.add(client)
    db_session.commit()

    demand = Demand(
        tenant_id=tenant.id, client_id=client.id, job_title="Senior PC Developer",
        required_skills='["Guidewire PolicyCenter"]', min_experience_years=5,
        work_location="REMOTE", status="OPEN",
    )
    db_session.add(demand)
    db_session.commit()

    a = SourcingAlert(
        tenant_id=tenant.id, demand_id=demand.id, severity="CRITICAL",
        rationale="zero bench match", bench_first_check_passed=True, status="OPEN",
    )
    db_session.add(a)
    db_session.commit()

    return a, demand, tenant


# ---------------------------------------------------------------------------
# BR-1103-03 -- atomic claim
# ---------------------------------------------------------------------------

def test_claim_alert_succeeds_once(db_session, alert):
    a, demand, tenant = alert
    claimed = claim_alert(db_session, a.id)
    db_session.commit()
    assert claimed is not None
    assert claimed.status == "PROCESSING"


def test_second_claim_on_already_processing_alert_fails(db_session, alert):
    a, demand, tenant = alert
    claim_alert(db_session, a.id)
    db_session.commit()

    second = claim_alert(db_session, a.id)
    db_session.commit()
    assert second is None


def test_claim_fails_for_nonexistent_or_already_sourced_alert(db_session, alert):
    a, demand, tenant = alert
    a.status = "SOURCED"
    db_session.add(a)
    db_session.commit()

    assert claim_alert(db_session, a.id) is None


# ---------------------------------------------------------------------------
# LLM query generation failure -> re-queue
# ---------------------------------------------------------------------------

def test_llm_generation_failure_marks_run_failed_and_requeues_alert(db_session, alert):
    a, demand, tenant = alert
    claim_alert(db_session, a.id)
    db_session.commit()

    run = process_sourcing_alert(db_session, a, demand)  # no llm_query_generator wired
    db_session.commit()

    assert run.status == "FAILED"
    assert a.status == "OPEN"


def test_llm_generation_exception_also_requeues(db_session, alert):
    a, demand, tenant = alert
    claim_alert(db_session, a.id)
    db_session.commit()

    def broken(payload):
        raise RuntimeError("Anthropic API down")

    run = process_sourcing_alert(db_session, a, demand, llm_query_generator=broken)
    db_session.commit()

    assert run.status == "FAILED"
    assert a.status == "OPEN"


def test_manual_override_skips_llm_generation_entirely(db_session, alert):
    a, demand, tenant = alert
    claim_alert(db_session, a.id)
    db_session.commit()

    def should_not_be_called(payload):
        raise AssertionError("LLM generator should not be called when override is supplied")

    run = process_sourcing_alert(
        db_session, a, demand, llm_query_generator=should_not_be_called,
        search_executor=lambda q: [], manual_query_override='"Custom Query"',
    )
    db_session.commit()

    assert run.boolean_query == '"Custom Query"'
    assert run.status == "COMPLETE"


# ---------------------------------------------------------------------------
# Search execution failure -> counter + AC-6 RM escalation
# ---------------------------------------------------------------------------

def _llm_ok(payload):
    return {"boolean_query": '"Guidewire" AND "5+ years"', "alt_queries": ["GW PolicyCenter"], "search_rationale": "x", "estimated_result_volume": 10}


def test_search_execution_failure_increments_counter_no_executor(db_session, alert):
    a, demand, tenant = alert
    claim_alert(db_session, a.id)
    db_session.commit()

    run = process_sourcing_alert(db_session, a, demand, llm_query_generator=_llm_ok)  # no search_executor
    db_session.commit()

    assert run.status == "FAILED"
    assert a.consecutive_search_failures == 1


def test_search_execution_exception_increments_counter(db_session, alert):
    a, demand, tenant = alert
    claim_alert(db_session, a.id)
    db_session.commit()

    def broken_executor(q):
        raise RuntimeError("LinkedIn API rate limited")

    process_sourcing_alert(db_session, a, demand, llm_query_generator=_llm_ok, search_executor=broken_executor)
    db_session.commit()
    assert a.consecutive_search_failures == 1


def test_two_consecutive_failures_page_rm(db_session, alert):
    a, demand, tenant = alert
    rm = Users(UserID="U-RM", UserRole="Recruiter", UserEmail="rm@blitzenx.com", UserPassword="h", tenant_id=tenant.id)
    db_session.add(rm)
    db_session.commit()

    claim_alert(db_session, a.id)
    db_session.commit()
    process_sourcing_alert(db_session, a, demand, llm_query_generator=_llm_ok, rm_user=rm)  # failure 1
    db_session.commit()
    assert db_session.query(Notification).count() == 0

    a.status = "PROCESSING"
    db_session.add(a)
    db_session.commit()
    process_sourcing_alert(db_session, a, demand, llm_query_generator=_llm_ok, rm_user=rm)  # failure 2
    db_session.commit()

    assert a.consecutive_search_failures == 2
    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].priority_tier == "P1"


# ---------------------------------------------------------------------------
# Successful run -- staging, dedup exclusion, router hand-off
# ---------------------------------------------------------------------------

def test_successful_run_stages_new_results_and_marks_sourced(db_session, alert):
    a, demand, tenant = alert
    claim_alert(db_session, a.id)
    db_session.commit()

    results = [
        {"email": "new1@example.com", "linkedin_profile_url": "https://linkedin.com/in/new1", "full_name": "New One"},
        {"email": "new2@example.com", "linkedin_profile_url": "https://linkedin.com/in/new2", "full_name": "New Two"},
    ]
    run = process_sourcing_alert(
        db_session, a, demand, llm_query_generator=_llm_ok, search_executor=lambda q: results,
    )
    db_session.commit()

    assert run.status == "COMPLETE"
    assert run.staged_candidate_count == 2
    assert a.status == "SOURCED"
    assert a.sourced_at is not None
    staged = db_session.query(StagedCandidate).filter(StagedCandidate.search_run_id == run.id).all()
    assert {s.dedup_status for s in staged} == {"NEW"}


def test_confirmed_duplicate_excluded_from_staged_candidates(db_session, alert):
    a, demand, tenant = alert
    db_session.add(Candidate(candidateID="C-EXIST", candidateEmail="existing@example.com", candidatePassword="h"))
    db_session.commit()

    claim_alert(db_session, a.id)
    db_session.commit()

    results = [
        {"email": "existing@example.com", "full_name": "Existing Person"},  # confirmed duplicate
        {"email": "brandnew@example.com", "full_name": "Brand New"},
    ]
    run = process_sourcing_alert(
        db_session, a, demand, llm_query_generator=_llm_ok, search_executor=lambda q: results,
    )
    db_session.commit()

    assert run.staged_candidate_count == 1
    staged = db_session.query(StagedCandidate).filter(StagedCandidate.search_run_id == run.id).all()
    assert len(staged) == 1
    assert staged[0].email == "brandnew@example.com"


def test_no_direct_candidate_row_created_by_the_agent(db_session, alert):
    """AC-3: zero INSERTs into candidates outside the promotion path."""
    a, demand, tenant = alert
    claim_alert(db_session, a.id)
    db_session.commit()

    process_sourcing_alert(
        db_session, a, demand, llm_query_generator=_llm_ok,
        search_executor=lambda q: [{"email": "fresh@example.com", "full_name": "Fresh Candidate"}],
    )
    db_session.commit()

    assert db_session.query(Candidate).count() == 0


def test_router_evaluate_called_before_marking_sourced(db_session, alert):
    a, demand, tenant = alert
    claim_alert(db_session, a.id)
    db_session.commit()

    calls = []

    def fake_router(**kwargs):
        calls.append(kwargs)

    process_sourcing_alert(
        db_session, a, demand, llm_query_generator=_llm_ok,
        search_executor=lambda q: [{"email": "fresh@example.com"}],
        router_evaluate=fake_router,
    )
    db_session.commit()

    assert len(calls) == 1
    assert calls[0]["agent_id"] == "HRMS-1103"
    assert calls[0]["entity_type"] == "staged_candidate_batch"
    assert calls[0]["risk_tier"] == "LOW"


# ---------------------------------------------------------------------------
# BR-1103-02 -- promotion is the only path to a real candidate
# ---------------------------------------------------------------------------

def _make_staged(db, tenant_id, alert_id, *, email="promote@example.com"):
    run = SourcingSearchRun(tenant_id=tenant_id, sourcing_alert_id=alert_id, status="COMPLETE")
    db.add(run)
    db.commit()
    staged = StagedCandidate(
        tenant_id=tenant_id, search_run_id=run.id, email=email,
        linkedin_profile_url="https://linkedin.com/in/promote", full_name="Promote Me",
        dedup_status="NEW", status="PENDING_REVIEW",
    )
    db.add(staged)
    db.commit()
    return staged


def test_promote_creates_real_candidate_and_consent_record(db_session, alert):
    a, demand, tenant = alert
    staged = _make_staged(db_session, tenant.id, a.id)

    candidate = promote_staged_candidate(db_session, staged, promoted_by="U-REC")
    db_session.commit()

    assert candidate.candidateEmail == "promote@example.com"
    assert staged.status == "PROMOTED"
    assert staged.promoted_to_candidate_id == candidate.candidateID
    assert staged.promoted_by == "U-REC"

    consent = db_session.query(ConsentRecord).filter(ConsentRecord.subject_id == candidate.candidateID).first()
    assert consent is not None
    assert consent.consent_given is True


def test_cannot_promote_the_same_staged_candidate_twice(db_session, alert):
    a, demand, tenant = alert
    staged = _make_staged(db_session, tenant.id, a.id)
    promote_staged_candidate(db_session, staged, promoted_by="U-REC")
    db_session.commit()

    with pytest.raises(StagedCandidateAlreadyPromoted):
        promote_staged_candidate(db_session, staged, promoted_by="U-REC")
