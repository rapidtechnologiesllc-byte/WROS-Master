"""
HRMS-1105 (canonical S-320) Resource Management Agent
(app.services.resource_management_agent_service).

No real Gemini call is made -- ChatGoogleGenerativeAI is mocked, same
convention as test_thunder_test_chat.py / test_ai_conversation_prompt_safety.py.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.client import Client
from app.models.core_pull import CorePullEvent, SpecialtyPoolReplacementPlan
from app.models.demand import Demand, DemandHistory
from app.models.employee import Employee, EmployeeEmploymentHistory, EmployeeEngineHistory
from app.models.employee_allocation import EmployeeAllocation
from app.models.notification import Notification
from app.models.orchestration import ConflictRule, OrchestrationEvent
from app.models.resource_agent import BenchAllocationRecommendation
from app.models.resource_management import (
    AllocationConflictLogEntry,
    BenchPoolEntry,
    EmployeeUtilizationMetric,
)
from app.models.tenant import Tenant
from app.models.user import Users

import app.services.resource_management_agent_service as svc
from app.services.core_pull_service import SPECIALTY_POOL_MINIMUM
from app.services.orchestration_router_service import seed_default_conflict_rules
from app.services.resource_management_service import mark_employee_on_bench


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setattr(svc, "GEMINI_API_KEY", "fake-key-for-test")


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, Client.__table__,
        Demand.__table__, DemandHistory.__table__,
        Employee.__table__, EmployeeEmploymentHistory.__table__, EmployeeEngineHistory.__table__,
        EmployeeAllocation.__table__, Notification.__table__,
        ConflictRule.__table__, OrchestrationEvent.__table__,
        CorePullEvent.__table__, SpecialtyPoolReplacementPlan.__table__,
        BenchPoolEntry.__table__, EmployeeUtilizationMetric.__table__, AllocationConflictLogEntry.__table__,
        BenchAllocationRecommendation.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _make_employee(db, tenant, *, core_certified=False, delivery_engine="SPECIALITY", skills=None, suffix="1", status="BENCH"):
    employee = Employee(
        tenant_id=tenant.id, first_name=f"Sam{suffix}", last_name="Lee",
        email=f"sam{suffix}@blitzenx.com", joining_date=date(2025, 1, 1),
        status=status, core_certified=core_certified, delivery_engine=delivery_engine,
        current_skills=skills or '["Guidewire PolicyCenter", "Java"]',
    )
    db.add(employee)
    db.commit()
    return employee


def _make_demand(db, tenant, client, *, delivery_engine="SPECIALITY", skills=None, suffix="1", status="OPEN"):
    demand = Demand(
        tenant_id=tenant.id, client_id=client.id, job_title=f"Role {suffix}",
        required_skills=skills or '["Guidewire PolicyCenter", "Java"]',
        min_experience_years=3.0, work_location="REMOTE",
        status=status, billing_rate_usd_cents=15000, delivery_engine=delivery_engine,
    )
    db.add(demand)
    db.commit()
    return demand


@pytest.fixture()
def fixtures(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    client = Client(tenant_id=tenant.id, company_name="Acme Insurance")
    db_session.add(client)
    db_session.commit()

    seed_default_conflict_rules(db_session, tenant_id=tenant.id)
    db_session.commit()

    return tenant, client


def _mock_gemini(response_text):
    mock_response = MagicMock()
    mock_response.content = response_text
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    return patch.object(svc, "ChatGoogleGenerativeAI", return_value=mock_llm)


# ---------------------------------------------------------------------------
# skill_match_score / find_open_demand_matches
# ---------------------------------------------------------------------------

def test_skill_match_score_full_overlap():
    score = svc.skill_match_score('["Java", "Guidewire"]', '["Java", "Guidewire"]')
    assert score == 1.0


def test_skill_match_score_partial_overlap():
    score = svc.skill_match_score('["Java"]', '["Java", "Guidewire"]')
    assert score == 0.5


def test_skill_match_score_no_requirements_is_zero():
    assert svc.skill_match_score('["Java"]', '[]') == 0.0


def test_find_open_demand_matches_respects_threshold(db_session, fixtures):
    tenant, client = fixtures
    employee = _make_employee(db_session, tenant, skills='["Java"]')
    _make_demand(db_session, tenant, client, skills='["Java", "Guidewire", "SQL", "AWS"]')  # 25% match

    matches = svc.find_open_demand_matches(db_session, employee, min_score=0.5)
    assert matches == []


def test_find_open_demand_matches_excludes_ineligible_buddy_program(db_session, fixtures):
    tenant, client = fixtures
    employee = _make_employee(db_session, tenant, skills='["Java", "Guidewire PolicyCenter"]')
    employee.buddy_program_status = "IN_PROGRESS"
    db_session.add(employee)
    db_session.commit()
    _make_demand(db_session, tenant, client)

    matches = svc.find_open_demand_matches(db_session, employee)
    assert matches == []


def test_find_open_demand_matches_excludes_core_demand_without_certification(db_session, fixtures):
    tenant, client = fixtures
    employee = _make_employee(db_session, tenant, core_certified=False)
    _make_demand(db_session, tenant, client, delivery_engine="CORE")

    matches = svc.find_open_demand_matches(db_session, employee)
    assert matches == []


def test_find_open_demand_matches_returns_sorted_by_score(db_session, fixtures):
    tenant, client = fixtures
    employee = _make_employee(db_session, tenant, skills='["Java", "Guidewire", "SQL"]')
    weak = _make_demand(db_session, tenant, client, skills='["Java", "Guidewire", "SQL", "AWS"]', suffix="weak")
    strong = _make_demand(db_session, tenant, client, skills='["Java", "Guidewire"]', suffix="strong")

    matches = svc.find_open_demand_matches(db_session, employee, min_score=0.5)
    assert [d.id for d, _ in matches] == [strong.id, weak.id]


# ---------------------------------------------------------------------------
# detect_core_pull_triggers -- delegates to S-353, never a local conditional
# ---------------------------------------------------------------------------

def test_detect_core_pull_triggers_for_speciality_deployed_employee(db_session, fixtures):
    tenant, client = fixtures
    employee = _make_employee(db_session, tenant, core_certified=True, status="ALLOCATED")
    speciality_demand = _make_demand(db_session, tenant, client, delivery_engine="SPECIALITY", suffix="spec")
    core_demand = _make_demand(db_session, tenant, client, delivery_engine="CORE", suffix="core")
    db_session.add(EmployeeAllocation(
        tenant_id=tenant.id, employee_id=employee.id, demand_id=speciality_demand.id,
        client_id=client.id, status="ACTIVE", start_date=date(2026, 1, 1), utilization_pct=100,
    ))
    db_session.commit()

    events = svc.detect_core_pull_triggers(db_session, tenant_id=tenant.id)

    assert len(events) == 1
    assert events[0].employee_id == employee.id
    assert events[0].core_demand_id == core_demand.id


def test_detect_core_pull_triggers_empty_for_pure_bench_employee(db_session, fixtures):
    """A bench (unallocated) employee has nothing active to pull FROM --
    detect_core_pull_conflict() correctly no-ops for them even though
    they're Core-Certified and a CORE demand is open."""
    tenant, client = fixtures
    employee = _make_employee(db_session, tenant, core_certified=True, status="BENCH")
    mark_employee_on_bench(db_session, employee)
    _make_demand(db_session, tenant, client, delivery_engine="CORE")
    db_session.commit()

    events = svc.detect_core_pull_triggers(db_session, tenant_id=tenant.id)
    assert events == []


def test_detect_core_pull_triggers_none_when_no_open_core_demand(db_session, fixtures):
    tenant, client = fixtures
    employee = _make_employee(db_session, tenant, core_certified=True, status="ALLOCATED")
    speciality_demand = _make_demand(db_session, tenant, client, delivery_engine="SPECIALITY")
    db_session.add(EmployeeAllocation(
        tenant_id=tenant.id, employee_id=employee.id, demand_id=speciality_demand.id,
        client_id=client.id, status="ACTIVE", start_date=date(2026, 1, 1), utilization_pct=100,
    ))
    db_session.commit()

    events = svc.detect_core_pull_triggers(db_session, tenant_id=tenant.id)
    assert events == []


# ---------------------------------------------------------------------------
# run_bench_scan -- full cycle
# ---------------------------------------------------------------------------

def test_run_bench_scan_creates_recommendations_for_bench_employee(db_session, fixtures):
    tenant, client = fixtures
    employee = _make_employee(db_session, tenant, status="BENCH")
    mark_employee_on_bench(db_session, employee)
    demand = _make_demand(db_session, tenant, client)
    db_session.commit()

    patcher = _mock_gemini(f'[{{"demand_id": "{demand.id}", "confidence_pct": 87, "rationale": "Strong skill match"}}]')
    with patcher:
        result = svc.run_bench_scan(db_session, tenant_id=tenant.id)
    db_session.commit()

    assert result["recommendations_created"] == 1
    rec = db_session.query(BenchAllocationRecommendation).first()
    assert rec.employee_id == employee.id
    assert rec.demand_id == demand.id
    assert float(rec.confidence_pct) == 87
    assert rec.rationale == "Strong skill match"
    assert rec.status == "PENDING_RM_REVIEW"


def test_run_bench_scan_never_creates_allocation_directly(db_session, fixtures):
    """BR-1105-02 / AC-2."""
    tenant, client = fixtures
    employee = _make_employee(db_session, tenant, status="BENCH")
    mark_employee_on_bench(db_session, employee)
    demand = _make_demand(db_session, tenant, client)
    db_session.commit()

    patcher = _mock_gemini(f'[{{"demand_id": "{demand.id}", "confidence_pct": 90, "rationale": "x"}}]')
    with patcher:
        svc.run_bench_scan(db_session, tenant_id=tenant.id)
    db_session.commit()

    assert db_session.query(EmployeeAllocation).count() == 0


def test_run_bench_scan_falls_back_without_api_key(db_session, fixtures, monkeypatch):
    tenant, client = fixtures
    employee = _make_employee(db_session, tenant, status="BENCH", skills='["Java", "Guidewire PolicyCenter"]')
    mark_employee_on_bench(db_session, employee)
    _make_demand(db_session, tenant, client, skills='["Java", "Guidewire PolicyCenter"]')
    db_session.commit()
    monkeypatch.setattr(svc, "GEMINI_API_KEY", "")

    result = svc.run_bench_scan(db_session, tenant_id=tenant.id)
    db_session.commit()

    assert result["recommendations_created"] == 1
    rec = db_session.query(BenchAllocationRecommendation).first()
    assert float(rec.confidence_pct) == 100.0  # raw skill-match fallback
    assert rec.rationale is None


def test_run_bench_scan_triggers_core_pull_and_ranks_separately(db_session, fixtures):
    tenant, client = fixtures
    # Speciality-deployed employee -- should trigger Core-Pull, not get ranked.
    deployed = _make_employee(db_session, tenant, core_certified=True, status="ALLOCATED", suffix="deployed")
    speciality_demand = _make_demand(db_session, tenant, client, delivery_engine="SPECIALITY", suffix="spec")
    core_demand = _make_demand(db_session, tenant, client, delivery_engine="CORE", suffix="core")
    db_session.add(EmployeeAllocation(
        tenant_id=tenant.id, employee_id=deployed.id, demand_id=speciality_demand.id,
        client_id=client.id, status="ACTIVE", start_date=date(2026, 1, 1), utilization_pct=100,
    ))
    # Bench employee -- should get ranked.
    bench_employee = _make_employee(db_session, tenant, status="BENCH", suffix="bench")
    mark_employee_on_bench(db_session, bench_employee)
    open_demand = _make_demand(db_session, tenant, client, suffix="open")
    db_session.commit()

    patcher = _mock_gemini(f'[{{"demand_id": "{open_demand.id}", "confidence_pct": 75, "rationale": "ok fit"}}]')
    with patcher:
        result = svc.run_bench_scan(db_session, tenant_id=tenant.id)
    db_session.commit()

    assert result["core_pull_events_triggered"] == 1
    assert result["recommendations_created"] == 1

    event = db_session.query(CorePullEvent).first()
    assert event.employee_id == deployed.id
    assert event.core_demand_id == core_demand.id

    rec = db_session.query(BenchAllocationRecommendation).first()
    assert rec.employee_id == bench_employee.id


# ---------------------------------------------------------------------------
# RM review queue -- approve/reject
# ---------------------------------------------------------------------------

def test_approve_recommendation_creates_allocation_via_real_gate(db_session, fixtures):
    tenant, client = fixtures
    employee = _make_employee(db_session, tenant, status="BENCH")
    mark_employee_on_bench(db_session, employee)
    demand = _make_demand(db_session, tenant, client)
    db_session.commit()

    rec = BenchAllocationRecommendation(
        tenant_id=tenant.id, employee_id=employee.id, demand_id=demand.id,
        confidence_pct=90, rationale="great fit", status="PENDING_RM_REVIEW",
    )
    db_session.add(rec)
    db_session.commit()

    allocation = svc.approve_bench_recommendation(db_session, rec, actor_user_id="U-RM")
    db_session.commit()

    assert allocation.employee_id == employee.id
    assert allocation.demand_id == demand.id
    assert allocation.status == "ACTIVE"
    assert rec.status == "APPROVED"
    assert rec.reviewed_by == "U-RM"
    assert employee.status == "ALLOCATED"


def test_reject_recommendation_creates_no_allocation(db_session, fixtures):
    tenant, client = fixtures
    employee = _make_employee(db_session, tenant, status="BENCH")
    mark_employee_on_bench(db_session, employee)
    demand = _make_demand(db_session, tenant, client)
    db_session.commit()

    rec = BenchAllocationRecommendation(
        tenant_id=tenant.id, employee_id=employee.id, demand_id=demand.id,
        confidence_pct=40, status="PENDING_RM_REVIEW",
    )
    db_session.add(rec)
    db_session.commit()

    result = svc.reject_bench_recommendation(db_session, rec, actor_user_id="U-RM")
    db_session.commit()

    assert result.status == "REJECTED"
    assert db_session.query(EmployeeAllocation).count() == 0


def test_cannot_approve_already_reviewed_recommendation(db_session, fixtures):
    tenant, client = fixtures
    employee = _make_employee(db_session, tenant, status="BENCH")
    mark_employee_on_bench(db_session, employee)
    demand = _make_demand(db_session, tenant, client)
    db_session.commit()

    rec = BenchAllocationRecommendation(
        tenant_id=tenant.id, employee_id=employee.id, demand_id=demand.id,
        confidence_pct=90, status="PENDING_RM_REVIEW",
    )
    db_session.add(rec)
    db_session.commit()
    svc.reject_bench_recommendation(db_session, rec, actor_user_id="U-RM")
    db_session.commit()

    with pytest.raises(svc.RecommendationNotPending):
        svc.approve_bench_recommendation(db_session, rec, actor_user_id="U-RM")


def test_get_recommendation_queue_sorted_by_confidence_desc(db_session, fixtures):
    tenant, client = fixtures
    employee = _make_employee(db_session, tenant, status="BENCH")
    d1 = _make_demand(db_session, tenant, client, suffix="1")
    d2 = _make_demand(db_session, tenant, client, suffix="2")
    db_session.add_all([
        BenchAllocationRecommendation(tenant_id=tenant.id, employee_id=employee.id, demand_id=d1.id, confidence_pct=40, status="PENDING_RM_REVIEW"),
        BenchAllocationRecommendation(tenant_id=tenant.id, employee_id=employee.id, demand_id=d2.id, confidence_pct=90, status="PENDING_RM_REVIEW"),
    ])
    db_session.commit()

    queue = svc.get_recommendation_queue(db_session, tenant_id=tenant.id)
    assert [float(r.confidence_pct) for r in queue] == [90, 40]
