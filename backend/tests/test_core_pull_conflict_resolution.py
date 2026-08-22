"""
S-318/HRMS-0514 - Core-Pull Conflict Resolution Methods Tests

Tests for the three main user-required methods:
1. evaluate_core_vs_specialty - advisory evaluation with confidence
2. apply_core_pull_rule - apply Core-Wins policy
3. resolve_conflict - resolve specific conflicts

These tests use local SQLite to avoid conftest PostgreSQL setup issues.
"""
import os
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.client import Client
from app.models.core_pull import CorePullEvent, SpecialtyPoolReplacementPlan
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.tenant import Tenant
from app.models.user import Users
from app.models.notification import Notification
from app.models.orchestration import ConflictRule, OrchestrationEvent

from app.services.core_pull_service import (
    apply_core_pull_rule,
    evaluate_core_vs_specialty,
    resolve_conflict,
    detect_core_pull_conflict,
    log_replacement_plan,
    execute_core_pull,
    SPECIALTY_POOL_MINIMUM,
)
from app.services.orchestration_router_service import seed_default_conflict_rules

@pytest.fixture()
def db_session():
    engine = create_engine(f"sqlite:///{db_path}")

    # Only create the tables we need

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

@pytest.fixture()
def fixtures(db_session):
    """Setup test data."""
    tenant = Tenant(name="TestBU")
    db_session.add(tenant)
    db_session.commit()

    client = Client(tenant_id=tenant.id, company_name="TestClient")
    db_session.add(client)
    db_session.commit()

    seed_default_conflict_rules(db_session, tenant_id=tenant.id)

    # Create demands
    spec_demand = Demand(
        tenant_id=tenant.id,
        client_id=client.id,
        job_title="Specialty Role",
        required_skills="[]",
        min_experience_years=3.0,
        work_location="REMOTE",
        status="OPEN",
        delivery_engine="SPECIALITY",
    )
    core_demand = Demand(
        tenant_id=tenant.id,
        client_id=client.id,
        job_title="Core Role",
        required_skills="[]",
        min_experience_years=3.0,
        work_location="REMOTE",
        status="OPEN",
        delivery_engine="CORE",
    )
    db_session.add_all([spec_demand, core_demand])
    db_session.commit()

    # Create Core-Certified employee on Speciality allocation
    employee = Employee(
        tenant_id=tenant.id,
        first_name="Test",
        last_name="Employee",
        email="test@example.com",
        joining_date=date(2025, 1, 1),
        status="ALLOCATED",
        core_certified=True,
        delivery_engine="SPECIALITY",
    )
    db_session.add(employee)
    db_session.commit()

    spec_alloc = EmployeeAllocation(
        tenant_id=tenant.id,
        employee_id=employee.id,
        demand_id=spec_demand.id,
        client_id=client.id,
        status="ACTIVE",
        start_date=date(2026, 1, 1),
        utilization_pct=100,
    )
    db_session.add(spec_alloc)
    db_session.commit()

    return tenant, client, employee, spec_demand, core_demand, spec_alloc

# ============================================================================
# evaluate_core_vs_specialty Tests
# ============================================================================

class TestEvaluateCorePullVsSpecialty:
    """Test evaluate_core_vs_specialty() method."""

    def test_evaluate_returns_core_wins_for_conflict(self, db_session, fixtures):
        """When Core-Certified employee matches Core demand, recommend CORE."""
        tenant, client, employee, spec_demand, core_demand, spec_alloc = fixtures

        result = evaluate_core_vs_specialty(
            db_session, employee.id, core_demand.id, tenant_id=tenant.id
        )

        assert result["status"] == "conflict_detected"
        assert result["recommendation"] == "CORE"
        assert result["confidence"] == 95
        assert "Core-Pull" in result["reasoning"]

    def test_evaluate_returns_specialty_for_spec_demand(self, db_session, fixtures):
        """Specialty demand should not trigger Core-Pull."""
        tenant, client, employee, spec_demand, core_demand, spec_alloc = fixtures

        result = evaluate_core_vs_specialty(
            db_session, employee.id, spec_demand.id, tenant_id=tenant.id
        )

        assert result["status"] == "eligible"
        assert result["recommendation"] == "SPECIALITY"

    def test_evaluate_returns_ineligible_for_non_core_certified(self, db_session, fixtures):
        """Non-Core-Certified employee cannot be allocated to Core demand."""
        tenant, client, employee, spec_demand, core_demand, spec_alloc = fixtures
        employee.core_certified = False
        db_session.add(employee)
        db_session.commit()

        result = evaluate_core_vs_specialty(
            db_session, employee.id, core_demand.id, tenant_id=tenant.id
        )

        assert result["status"] == "not_eligible"
        assert result["recommendation"] is None
        assert "not Core-certified" in result["reasoning"]

    def test_evaluate_handles_missing_employee(self, db_session, fixtures):
        """Gracefully handle missing employee."""
        tenant, client, employee, spec_demand, core_demand, spec_alloc = fixtures

        result = evaluate_core_vs_specialty(
            db_session, "nonexistent_id", core_demand.id, tenant_id=tenant.id
        )

        assert result["status"] == "error"
        assert result["confidence"] == 0

    def test_evaluate_handles_missing_job(self, db_session, fixtures):
        """Gracefully handle missing job."""
        tenant, client, employee, spec_demand, core_demand, spec_alloc = fixtures

        result = evaluate_core_vs_specialty(
            db_session, employee.id, "nonexistent_id", tenant_id=tenant.id
        )

        assert result["status"] == "error"
        assert result["confidence"] == 0

# ============================================================================
# apply_core_pull_rule Tests
# ============================================================================

class TestApplyCorePullRule:
    """Test apply_core_pull_rule() method."""

    def test_apply_rule_core_wins_on_conflict(self, db_session, fixtures):
        """When conflict exists, Core-Pull rule applies."""
        tenant, client, employee, spec_demand, core_demand, spec_alloc = fixtures

        result = apply_core_pull_rule(
            db_session, employee.id, core_demand.id, tenant_id=tenant.id
        )

        assert result["status"] == "conflict_applies_core_wins"
        assert result["allocation_decision"] == "CORE_WINS"
        assert "Core-Pull" in result["reasoning"]

    def test_apply_rule_no_conflict_for_spec_demand(self, db_session, fixtures):
        """No conflict for Speciality demand."""
        tenant, client, employee, spec_demand, core_demand, spec_alloc = fixtures

        result = apply_core_pull_rule(
            db_session, employee.id, spec_demand.id, tenant_id=tenant.id
        )

        assert result["status"] == "no_conflict"
        assert result["allocation_decision"] == "ELIGIBLE"

    def test_apply_rule_creates_pending_event(self, db_session, fixtures):
        """Applying rule creates a PENDING Core-Pull event."""
        tenant, client, employee, spec_demand, core_demand, spec_alloc = fixtures

        result = apply_core_pull_rule(
            db_session, employee.id, core_demand.id, tenant_id=tenant.id
        )
        db_session.commit()

        event_count = (
            db_session.query(CorePullEvent)
            .filter(CorePullEvent.status == "PENDING")
            .count()
        )
        assert event_count == 1

    def test_apply_rule_idempotent(self, db_session, fixtures):
        """Applying rule twice creates only one event."""
        tenant, client, employee, spec_demand, core_demand, spec_alloc = fixtures

        apply_core_pull_rule(db_session, employee.id, core_demand.id, tenant_id=tenant.id)
        db_session.commit()
        first_count = db_session.query(CorePullEvent).count()

        apply_core_pull_rule(db_session, employee.id, core_demand.id, tenant_id=tenant.id)
        db_session.commit()
        second_count = db_session.query(CorePullEvent).count()

        assert first_count == second_count == 1

# ============================================================================
# resolve_conflict Tests
# ============================================================================

class TestResolveConflict:
    """Test resolve_conflict() method."""

    def test_resolve_execute_transfers_employee(self, db_session, fixtures):
        """EXECUTE resolution performs the Core-Pull transfer."""
        tenant, client, employee, spec_demand, core_demand, spec_alloc = fixtures

        # Create a conflict event
        event = detect_core_pull_conflict(db_session, employee, core_demand)
        db_session.commit()

        # Log replacement plan to satisfy pool guard
        log_replacement_plan(
            db_session,
            employee,
            "x" * 100,
            date(2026, 9, 1),
            logged_by="U-BUHEAD",
        )
        db_session.commit()

        # Create users for notifications
        rm = Users(
            UserID="U-RM",
            UserRole="Recruiter",
            UserEmail="rm@example.com",
            UserPassword="h",
            tenant_id=tenant.id,
        )
        bu_head = Users(
            UserID="U-BUHEAD",
            UserRole="BU Head",
            UserEmail="buhead@example.com",
            UserPassword="h",
            tenant_id=tenant.id,
        )
        db_session.add_all([rm, bu_head])
        db_session.commit()

        # Resolve the conflict
        result = resolve_conflict(
            db_session, event.id, "EXECUTE", tenant_id=tenant.id, acting_user=bu_head
        )
        db_session.commit()

        assert result["status"] == "success"
        assert result["event_status"] == "EXECUTED"

        # Verify the transfer happened
        db_session.refresh(spec_alloc)
        assert spec_alloc.status == "CORE_PULLED"
        db_session.refresh(employee)
        assert employee.delivery_engine == "CORE"

    def test_resolve_override_prevents_execution(self, db_session, fixtures):
        """OVERRIDE resolution delays the Core-Pull."""
        tenant, client, employee, spec_demand, core_demand, spec_alloc = fixtures

        event = detect_core_pull_conflict(db_session, employee, core_demand)
        db_session.commit()

        result = resolve_conflict(
            db_session, event.id, "OVERRIDE", tenant_id=tenant.id
        )

        assert "override endpoint" in result["message"].lower() or result["status"] == "error"

    def test_resolve_handles_nonexistent_conflict(self, db_session, fixtures):
        """Gracefully handle nonexistent conflict."""
        tenant, client, employee, spec_demand, core_demand, spec_alloc = fixtures

        result = resolve_conflict(
            db_session, "nonexistent_id", "EXECUTE", tenant_id=tenant.id
        )

        assert result["status"] == "error"

    def test_resolve_rejects_invalid_resolution_type(self, db_session, fixtures):
        """Reject invalid resolution type."""
        tenant, client, employee, spec_demand, core_demand, spec_alloc = fixtures

        event = detect_core_pull_conflict(db_session, employee, core_demand)
        db_session.commit()

        result = resolve_conflict(
            db_session, event.id, "INVALID_TYPE", tenant_id=tenant.id
        )

        assert result["status"] == "error"
        assert "Unknown resolution type" in result["message"]

    def test_resolve_cannot_execute_already_executed_event(self, db_session, fixtures):
        """Cannot resolve an event that's already been executed."""
        tenant, client, employee, spec_demand, core_demand, spec_alloc = fixtures

        event = detect_core_pull_conflict(db_session, employee, core_demand)
        db_session.commit()

        log_replacement_plan(
            db_session,
            employee,
            "x" * 100,
            date(2026, 9, 1),
            logged_by="U-BUHEAD",
        )
        db_session.commit()

        # First resolution succeeds
        bu_head = Users(
            UserID="U-BUHEAD",
            UserRole="BU Head",
            UserEmail="buhead@example.com",
            UserPassword="h",
            tenant_id=tenant.id,
        )
        db_session.add(bu_head)
        db_session.commit()

        resolve_conflict(
            db_session, event.id, "EXECUTE", tenant_id=tenant.id, acting_user=bu_head
        )
        db_session.commit()

        # Second resolution fails (event already executed)
        db_session.refresh(event)
        result = resolve_conflict(
            db_session, event.id, "EXECUTE", tenant_id=tenant.id, acting_user=bu_head
        )

        assert result["status"] == "error"

# ============================================================================
# Integration Tests
# ============================================================================

class TestCorePullWorkflow:
    """Test complete Core-Pull workflow using all three methods."""

    def test_full_workflow_evaluate_apply_resolve(self, db_session, fixtures):
        """Complete workflow: evaluate → apply → resolve."""
        tenant, client, employee, spec_demand, core_demand, spec_alloc = fixtures

        # Step 1: Evaluate
        eval_result = evaluate_core_vs_specialty(
            db_session, employee.id, core_demand.id, tenant_id=tenant.id
        )
        assert eval_result["recommendation"] == "CORE"
        assert eval_result["confidence"] == 95

        # Step 2: Apply rule
        rule_result = apply_core_pull_rule(
            db_session, employee.id, core_demand.id, tenant_id=tenant.id
        )
        assert rule_result["allocation_decision"] == "CORE_WINS"
        db_session.commit()

        # Step 3: Get the event and resolve
        event = (
            db_session.query(CorePullEvent)
            .filter(CorePullEvent.status == "PENDING")
            .first()
        )
        assert event is not None

        # Log replacement plan
        log_replacement_plan(
            db_session,
            employee,
            "x" * 100,
            date(2026, 9, 1),
            logged_by="U-BUHEAD",
        )
        db_session.commit()

        # Resolve
        bu_head = Users(
            UserID="U-BUHEAD",
            UserRole="BU Head",
            UserEmail="buhead@example.com",
            UserPassword="h",
            tenant_id=tenant.id,
        )
        db_session.add(bu_head)
        db_session.commit()

        resolve_result = resolve_conflict(
            db_session, event.id, "EXECUTE", tenant_id=tenant.id, acting_user=bu_head
        )
        db_session.commit()

        assert resolve_result["status"] == "success"
        assert resolve_result["event_status"] == "EXECUTED"

        # Verify final state
        db_session.refresh(employee)
        db_session.refresh(spec_alloc)
        assert employee.delivery_engine == "CORE"
        assert spec_alloc.status == "CORE_PULLED"
