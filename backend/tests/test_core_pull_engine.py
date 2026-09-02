"""
S-353/HRMS-0514 Core-Pull Conflict Rule Engine ("Core Wins Policy") +
S-373/HRMS-0529 Specialty Pool Minimum 40 Core-Certified Guard
import logging
(app.services.core_pull_service).

Built against `Requirements/S-353_HRMS-0514.docx` and
`Requirements/S-373_HRMS-0529.docx` directly -- see app.models.core_pull's
module docstring on why this is NOT built against "HRMS-0312" (that ID is
an unrelated story in the real requirements corpus).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, datetime, timedelta

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
from app.models.resource_management import (
    AllocationConflictLogEntry,
    BenchPeriod,
    BenchPoolEntry,
    EmployeeUtilizationMetric,
)
from app.models.tenant import Tenant
from app.models.user import Users

from app.services.core_pull_service import (
    CorePullOverrideForbidden,
    InvalidOverrideJustification,
    InvalidReplacementPlan,
    OVERRIDE_ALERT_THRESHOLD,
    SPECIALTY_POOL_MINIMUM,
    SpecialtyPoolBelowMinimum,
    check_specialty_pool_guard,
    detect_core_pull_conflict,
    execute_core_pull,
    log_replacement_plan,
    override_core_pull,
)
from app.services.orchestration_router_service import ActionBlocked, seed_default_conflict_rules


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
        BenchPoolEntry.__table__, BenchPeriod.__table__, EmployeeUtilizationMetric.__table__, AllocationConflictLogEntry.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _make_employee(db, tenant, *, core_certified=True, delivery_engine="SPECIALITY", suffix="1"):
    employee = Employee(
        tenant_id=tenant.id, first_name=f"Sam{suffix}", last_name="Lee",
        email=f"sam{suffix}@blitzenx.com", joining_date=date(2025, 1, 1),
        status="ALLOCATED", core_certified=core_certified, delivery_engine=delivery_engine,
    )
    db.add(employee)
    db.commit()
    return employee


def _make_demand(db, tenant, client, *, delivery_engine="SPECIALITY", suffix="1"):
    demand = Demand(
        tenant_id=tenant.id, client_id=client.id, job_title=f"Role {suffix}",
        required_skills="[]", min_experience_years=3.0, work_location="REMOTE",
        status="OPEN", billing_rate_usd_cents=15000, delivery_engine=delivery_engine,
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

    speciality_demand = _make_demand(db_session, tenant, client, delivery_engine="SPECIALITY", suffix="spec")
    core_demand = _make_demand(db_session, tenant, client, delivery_engine="CORE", suffix="core")

    employee = _make_employee(db_session, tenant, core_certified=True, delivery_engine="SPECIALITY")

    speciality_allocation = EmployeeAllocation(
        tenant_id=tenant.id, employee_id=employee.id, demand_id=speciality_demand.id,
        client_id=client.id, status="ACTIVE", start_date=date(2026, 1, 1), utilization_pct=100,
    )
    db_session.add(speciality_allocation)
    db_session.commit()

    return tenant, client, employee, speciality_demand, core_demand, speciality_allocation


def _fill_specialty_pool(db, tenant, count):
    """Creates `count` additional Core-Certified Specialty employees so the
    pool guard has real headroom in tests that need it above the minimum."""
    for i in range(count):
        _make_employee(db, tenant, core_certified=True, delivery_engine="SPECIALITY", suffix=f"pool{i}")


# ---------------------------------------------------------------------------
# detect_core_pull_conflict
# ---------------------------------------------------------------------------

def test_detect_no_conflict_when_demand_is_speciality(db_session, fixtures):
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    event = detect_core_pull_conflict(db_session, employee, speciality_demand)
    assert event is None


def test_detect_no_conflict_when_employee_not_core_certified(db_session, fixtures):
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    employee.core_certified = False
    db_session.add(employee)
    db_session.commit()

    event = detect_core_pull_conflict(db_session, employee, core_demand)
    assert event is None


def test_detect_no_conflict_without_active_speciality_allocation(db_session, fixtures):
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    alloc.status = "ENDED"
    db_session.add(alloc)
    db_session.commit()

    event = detect_core_pull_conflict(db_session, employee, core_demand)
    assert event is None


def test_detect_creates_pending_event_on_real_conflict(db_session, fixtures):
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    event = detect_core_pull_conflict(db_session, employee, core_demand)

    assert event is not None
    assert event.status == "PENDING"
    assert event.employee_id == employee.id
    assert event.core_demand_id == core_demand.id
    assert event.speciality_allocation_id == alloc.id


def test_detect_is_idempotent_for_same_pending_conflict(db_session, fixtures):
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    first = detect_core_pull_conflict(db_session, employee, core_demand)
    db_session.commit()
    second = detect_core_pull_conflict(db_session, employee, core_demand)

    assert first.id == second.id
    assert db_session.query(CorePullEvent).count() == 1


# ---------------------------------------------------------------------------
# check_specialty_pool_guard
# ---------------------------------------------------------------------------

def test_guard_below_minimum_when_pool_too_small(db_session, fixtures):
    tenant, client, employee, *_ = fixtures
    # Only `employee` itself is in the pool -- moving them drops it to 0.
    result = check_specialty_pool_guard(db_session, employee)
    assert result["pool_size_after_move"] == 0
    assert result["below_minimum"] is True
    assert result["gap"] == SPECIALTY_POOL_MINIMUM


def test_guard_not_below_minimum_with_enough_headroom(db_session, fixtures):
    tenant, client, employee, *_ = fixtures
    _fill_specialty_pool(db_session, tenant, SPECIALTY_POOL_MINIMUM)  # +40, employee makes 41

    result = check_specialty_pool_guard(db_session, employee)
    assert result["pool_size_after_move"] == SPECIALTY_POOL_MINIMUM
    assert result["below_minimum"] is False
    assert result["at_edge"] is True


def test_guard_excludes_exited_employees(db_session, fixtures):
    tenant, client, employee, *_ = fixtures
    _fill_specialty_pool(db_session, tenant, SPECIALTY_POOL_MINIMUM)
    exited = _make_employee(db_session, tenant, core_certified=True, delivery_engine="SPECIALITY", suffix="exited")
    exited.status = "EXITED"
    db_session.add(exited)
    db_session.commit()

    result = check_specialty_pool_guard(db_session, employee)
    assert result["pool_size_after_move"] == SPECIALTY_POOL_MINIMUM  # exited employee not counted


# ---------------------------------------------------------------------------
# log_replacement_plan
# ---------------------------------------------------------------------------

def test_replacement_plan_requires_100_char_strategy(db_session, fixtures):
    tenant, client, employee, *_ = fixtures
    with pytest.raises(InvalidReplacementPlan):
        log_replacement_plan(
            db_session, employee_being_moved=employee,
            replacement_strategy="too short", expected_replacement_date=date(2026, 9, 1),
        )


def test_replacement_plan_requires_expected_date(db_session, fixtures):
    tenant, client, employee, *_ = fixtures
    with pytest.raises(InvalidReplacementPlan):
        log_replacement_plan(
            db_session, employee_being_moved=employee,
            replacement_strategy="x" * 100, expected_replacement_date=None,
        )


def test_replacement_plan_logged_successfully(db_session, fixtures):
    tenant, client, employee, *_ = fixtures
    plan = log_replacement_plan(
        db_session, employee_being_moved=employee,
        replacement_strategy="x" * 100, expected_replacement_date=date(2026, 9, 1),
        logged_by="U-BUHEAD",
    )
    assert plan.id is not None
    assert plan.employee_id_moving == employee.id


# ---------------------------------------------------------------------------
# execute_core_pull -- full end-to-end transfer
# ---------------------------------------------------------------------------

def test_execute_core_pull_blocked_below_minimum_without_replacement_plan(db_session, fixtures):
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    event = detect_core_pull_conflict(db_session, employee, core_demand)
    db_session.commit()

    with pytest.raises(SpecialtyPoolBelowMinimum):
        execute_core_pull(db_session, event, tenant_id=tenant.id)

    assert event.status == "PENDING"
    assert alloc.status == "ACTIVE"


def test_execute_core_pull_proceeds_once_replacement_plan_logged(db_session, fixtures):
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    event = detect_core_pull_conflict(db_session, employee, core_demand)
    db_session.commit()

    log_replacement_plan(
        db_session, employee_being_moved=employee,
        replacement_strategy="x" * 100, expected_replacement_date=date(2026, 9, 1),
        logged_by="U-BUHEAD",
    )
    db_session.commit()

    result = execute_core_pull(db_session, event, tenant_id=tenant.id)
    assert result.status == "EXECUTED"


def test_execute_core_pull_full_transfer_with_enough_pool(db_session, fixtures):
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    _fill_specialty_pool(db_session, tenant, SPECIALTY_POOL_MINIMUM)  # avoid the guard entirely

    event = detect_core_pull_conflict(db_session, employee, core_demand)
    db_session.commit()

    execute_core_pull(db_session, event, tenant_id=tenant.id)
    db_session.commit()

    # Speciality allocation ended as CORE_PULLED, same day.
    assert alloc.status == "CORE_PULLED"
    assert alloc.end_date == date.today()

    # A new ACTIVE allocation exists for the Core demand.
    new_alloc = (
        db_session.query(EmployeeAllocation)
        .filter(
            EmployeeAllocation.employee_id == employee.id,
            EmployeeAllocation.demand_id == core_demand.id,
        )
        .first()
    )
    assert new_alloc is not None
    assert new_alloc.status == "ACTIVE"
    assert new_alloc.start_date == date.today()

    # Employee is now CORE.
    assert employee.delivery_engine == "CORE"

    # Engine history logged.
    history = db_session.query(EmployeeEngineHistory).filter(
        EmployeeEngineHistory.employee_id == employee.id
    ).first()
    assert history.from_engine == "SPECIALITY"
    assert history.to_engine == "CORE"
    assert history.reason == "Core-Pull"

    assert event.status == "EXECUTED"
    assert event.executed_at is not None


def test_execute_core_pull_notifies_rm_and_bu_head(db_session, fixtures):
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    _fill_specialty_pool(db_session, tenant, SPECIALTY_POOL_MINIMUM)

    rm = Users(UserID="U-RM", UserRole="Recruiter", UserEmail="rm@blitzenx.com", UserPassword="h", tenant_id=tenant.id)
    bu_head = Users(UserID="U-BUHEAD", UserRole="BU Head", UserEmail="buhead@blitzenx.com", UserPassword="h", tenant_id=tenant.id)
    db_session.add_all([rm, bu_head])
    db_session.commit()

    event = detect_core_pull_conflict(db_session, employee, core_demand)
    db_session.commit()

    execute_core_pull(db_session, event, tenant_id=tenant.id, speciality_rm=rm, bu_head=bu_head)
    db_session.commit()

    notifications = db_session.query(Notification).all()
    recipients = {n.recipient_id for n in notifications}
    assert "U-RM" in recipients
    assert "U-BUHEAD" in recipients


def test_execute_core_pull_rejects_non_pending_event(db_session, fixtures):
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    _fill_specialty_pool(db_session, tenant, SPECIALTY_POOL_MINIMUM)
    event = detect_core_pull_conflict(db_session, employee, core_demand)
    db_session.commit()
    execute_core_pull(db_session, event, tenant_id=tenant.id)
    db_session.commit()

    with pytest.raises(ValueError):
        execute_core_pull(db_session, event, tenant_id=tenant.id)


# ---------------------------------------------------------------------------
# override_core_pull
# ---------------------------------------------------------------------------

def test_override_requires_bu_head_role(db_session, fixtures):
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    event = detect_core_pull_conflict(db_session, employee, core_demand)
    db_session.commit()

    with pytest.raises(CorePullOverrideForbidden):
        override_core_pull(
            db_session, event, actor_role="Recruiter", actor_user_id="U-REC",
            justification="x" * 100, tenant_id=tenant.id,
        )


def test_override_requires_100_char_justification(db_session, fixtures):
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    event = detect_core_pull_conflict(db_session, employee, core_demand)
    db_session.commit()

    with pytest.raises(InvalidOverrideJustification):
        override_core_pull(
            db_session, event, actor_role="BU Head", actor_user_id="U-BUHEAD",
            justification="too short", tenant_id=tenant.id,
        )


def test_override_leaves_speciality_allocation_untouched(db_session, fixtures):
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    event = detect_core_pull_conflict(db_session, employee, core_demand)
    db_session.commit()

    result = override_core_pull(
        db_session, event, actor_role="BU Head", actor_user_id="U-BUHEAD",
        justification="x" * 100, tenant_id=tenant.id,
    )

    assert result.status == "OVERRIDDEN"
    assert result.override_justification == "x" * 100
    assert result.overridden_by == "U-BUHEAD"
    assert alloc.status == "ACTIVE"  # never touched


def test_override_cannot_repeat_on_already_overridden_event(db_session, fixtures):
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    event = detect_core_pull_conflict(db_session, employee, core_demand)
    db_session.commit()
    override_core_pull(
        db_session, event, actor_role="BU Head", actor_user_id="U-BUHEAD",
        justification="x" * 100, tenant_id=tenant.id,
    )
    db_session.commit()

    with pytest.raises(ValueError):
        override_core_pull(
            db_session, event, actor_role="BU Head", actor_user_id="U-BUHEAD",
            justification="y" * 100, tenant_id=tenant.id,
        )


def test_override_pattern_alerts_director_past_threshold(db_session, fixtures):
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    director = Users(UserID="U-DIR", UserRole="Director", UserEmail="dir@blitzenx.com", UserPassword="h", tenant_id=tenant.id)
    db_session.add(director)
    db_session.commit()

    # Generate OVERRIDE_ALERT_THRESHOLD + 1 overrides across distinct employees/demands.
    for i in range(OVERRIDE_ALERT_THRESHOLD + 1):
        emp = _make_employee(db_session, tenant, core_certified=True, delivery_engine="SPECIALITY", suffix=f"ov{i}")
        core_d = _make_demand(db_session, tenant, client, delivery_engine="CORE", suffix=f"ovcore{i}")
        spec_alloc = EmployeeAllocation(
            tenant_id=tenant.id, employee_id=emp.id, demand_id=speciality_demand.id,
            client_id=client.id, status="ACTIVE", start_date=date(2026, 1, 1), utilization_pct=100,
        )
        db_session.add(spec_alloc)
        db_session.commit()

        ev = detect_core_pull_conflict(db_session, emp, core_d)
        db_session.commit()
        override_core_pull(
            db_session, ev, actor_role="BU Head", actor_user_id="U-BUHEAD",
            justification="x" * 100, tenant_id=tenant.id, director=director,
        )
        db_session.commit()

    notifications = db_session.query(Notification).filter(
        Notification.recipient_id == "U-DIR"
    ).all()
    assert len(notifications) >= 1


# ---------------------------------------------------------------------------
# Orchestration Router integration -- Core-Pull still goes through it
# ---------------------------------------------------------------------------

def test_execute_core_pull_blocked_when_conversation_owned_by_human_rule_irrelevant(db_session, fixtures):
    """Sanity check that the router is genuinely consulted (not skipped) --
    a HIGH-risk-tier novel-pattern collision with another agent's event on
    the same entity_id within 5 minutes escalates but does not block,
    matching Section 4.3's 'no debate' framing: nothing in this codebase's
    seeded rules currently targets core_pull_transfer, so execution proceeds."""
    tenant, client, employee, speciality_demand, core_demand, alloc = fixtures
    _fill_specialty_pool(db_session, tenant, SPECIALTY_POOL_MINIMUM)
    event = detect_core_pull_conflict(db_session, employee, core_demand)
    db_session.commit()

    execute_core_pull(db_session, event, tenant_id=tenant.id)
    db_session.commit()

    router_event = db_session.query(OrchestrationEvent).filter(
        OrchestrationEvent.action_type == "core_pull_transfer"
    ).first()
    assert router_event is not None
    assert router_event.entity_id == alloc.id
