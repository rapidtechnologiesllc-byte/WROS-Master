"""
import logging
S-360/HRMS-P506-REV -- HTD 4-Phase Gate Structure.

Proves: no phase advance without an explicit PASS from the correct
gate owner (AC-2), the max-1-extension-per-phase cap (AC-4), COMPLETED
only reachable by passing all 4 gates in sequence (AC-6), EXIT sets
PERFORMANCE_MANAGED, and every decision writes a CERTIFICATION_GATE
event to the performance store (AC-5).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.employee import Employee, EmployeeEmploymentHistory
from app.models.htd_phase_gate import HTDPhaseGate
from app.models.performance_store import EmployeePerformanceEvent
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.htd_phase_gate_service import (
    InvalidPhaseGateDecision,
    PhaseExtensionLimitReached,
    WrongGateOwnerForPhase,
    WrongPhaseForGate,
    exit_htd_track,
    record_phase_gate_decision,
)

VALID_NOTE = "Completed all induction modules and shadowed three live client delivery sessions successfully."

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, Employee.__table__, EmployeeEmploymentHistory.__table__,
        HTDPhaseGate.__table__, EmployeePerformanceEvent.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

@pytest.fixture()
def employee(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    emp = Employee(
        tenant_id=tenant.id, first_name="HTD", last_name="Trainee", email="htd@blitzenx.com",
        joining_date=date(2026, 1, 1), status="ACTIVE", htd_track=True, htd_phase="INDUCTION",
    )
    db_session.add(emp)
    db_session.commit()
    return emp

def test_pass_advances_to_next_phase(db_session, employee):
    record_phase_gate_decision(
        db_session, employee, phase="INDUCTION", decision="PASS",
        gate_owner_user_id="U-HR", gate_owner_role="HR", notes=VALID_NOTE,
    )
    db_session.commit()
    assert employee.htd_phase == "SHADOW_DELIVERY"

def test_full_sequence_reaches_completed(db_session, employee):
    steps = [
        ("INDUCTION", "HR", "U-HR"),
        ("SHADOW_DELIVERY", "TECHNICAL_MANAGER", "U-TM"),
        ("CONTROLLED_OWNERSHIP", "PRACTICE_HEAD", "U-PH"),
        ("CORE_ELIGIBILITY_REVIEW", "HEMANT_BU_HEAD", "U-HEMANT"),
    ]
    for phase, role, owner in steps:
        record_phase_gate_decision(
            db_session, employee, phase=phase, decision="PASS",
            gate_owner_user_id=owner, gate_owner_role=role, notes=VALID_NOTE,
        )
        db_session.commit()
    assert employee.htd_phase == "COMPLETED"

def test_cannot_gate_a_phase_the_employee_is_not_in(db_session, employee):
    with pytest.raises(WrongPhaseForGate):
        record_phase_gate_decision(
            db_session, employee, phase="SHADOW_DELIVERY", decision="PASS",
            gate_owner_user_id="U-TM", gate_owner_role="TECHNICAL_MANAGER", notes=VALID_NOTE,
        )
    assert employee.htd_phase == "INDUCTION"  # no quiet advance

def test_wrong_gate_owner_role_rejected(db_session, employee):
    with pytest.raises(WrongGateOwnerForPhase):
        record_phase_gate_decision(
            db_session, employee, phase="INDUCTION", decision="PASS",
            gate_owner_user_id="U-TM", gate_owner_role="TECHNICAL_MANAGER", notes=VALID_NOTE,
        )

def test_short_notes_rejected(db_session, employee):
    with pytest.raises(InvalidPhaseGateDecision):
        record_phase_gate_decision(
            db_session, employee, phase="INDUCTION", decision="PASS",
            gate_owner_user_id="U-HR", gate_owner_role="HR", notes="too short",
        )

def test_extend_keeps_employee_in_same_phase(db_session, employee):
    record_phase_gate_decision(
        db_session, employee, phase="INDUCTION", decision="EXTEND",
        gate_owner_user_id="U-HR", gate_owner_role="HR", notes=VALID_NOTE,
    )
    db_session.commit()
    assert employee.htd_phase == "INDUCTION"

def test_second_extend_on_same_phase_blocked(db_session, employee):
    record_phase_gate_decision(
        db_session, employee, phase="INDUCTION", decision="EXTEND",
        gate_owner_user_id="U-HR", gate_owner_role="HR", notes=VALID_NOTE,
    )
    db_session.commit()

    with pytest.raises(PhaseExtensionLimitReached):
        record_phase_gate_decision(
            db_session, employee, phase="INDUCTION", decision="EXTEND",
            gate_owner_user_id="U-HR", gate_owner_role="HR", notes=VALID_NOTE,
        )

def test_after_one_extension_pass_still_allowed(db_session, employee):
    record_phase_gate_decision(
        db_session, employee, phase="INDUCTION", decision="EXTEND",
        gate_owner_user_id="U-HR", gate_owner_role="HR", notes=VALID_NOTE,
    )
    db_session.commit()
    record_phase_gate_decision(
        db_session, employee, phase="INDUCTION", decision="PASS",
        gate_owner_user_id="U-HR", gate_owner_role="HR", notes=VALID_NOTE,
    )
    db_session.commit()
    assert employee.htd_phase == "SHADOW_DELIVERY"

def test_fail_leaves_employee_in_same_phase(db_session, employee):
    record_phase_gate_decision(
        db_session, employee, phase="INDUCTION", decision="FAIL",
        gate_owner_user_id="U-HR", gate_owner_role="HR", notes=VALID_NOTE,
    )
    db_session.commit()
    assert employee.htd_phase == "INDUCTION"

def test_exit_track_sets_performance_managed(db_session, employee):
    exit_htd_track(db_session, employee, reason=VALID_NOTE, changed_by="U-BUH")
    db_session.commit()
    assert employee.htd_phase == "EXITED"
    assert employee.status == "PERFORMANCE_MANAGED"

def test_exit_track_requires_real_reason(db_session, employee):
    with pytest.raises(InvalidPhaseGateDecision):
        exit_htd_track(db_session, employee, reason="nope", changed_by="U-BUH")

def test_every_decision_writes_certification_gate_event(db_session, employee):
    record_phase_gate_decision(
        db_session, employee, phase="INDUCTION", decision="PASS",
        gate_owner_user_id="U-HR", gate_owner_role="HR", notes=VALID_NOTE,
    )
    db_session.commit()

    events = (
        db_session.query(EmployeePerformanceEvent)
        .filter(
            EmployeePerformanceEvent.employee_id == employee.id,
            EmployeePerformanceEvent.event_type == "CERTIFICATION_GATE",
        )
        .all()
    )
    assert len(events) == 1
