"""
HRMS-0101 -- employee number generation and status transitions.

Per the Development & Review Standard's pattern (and this codebase's
own `transitionEmployeeStatus`-style precedent at HRMS-0418): one
sanctioned function per state machine, never a bare column UPDATE
scattered across call sites, so the transition-validity + history-
logging guarantee lives in one place.
"""
import json
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.employee import (
    ALLOWED_STATUS_TRANSITIONS,
    Employee,
    EmployeeEmploymentHistory,
    EmployeeEngineHistory,
)


class InvalidStatusTransition(Exception):
    pass


class CoreAssignmentNotAllowed(Exception):
    """S-351/HRMS-0512 BR: only set_core_delivery_engine() may assign
    CORE, and only for an already core_certified employee."""


def generate_employee_number(db: Session, tenant_id: int, tenant_code: str) -> str:
    """
    BR-02: '{TENANT_CODE}-{SEQUENCE}', e.g. 'BLX-001'. Sequence is the
    count of existing employees for this tenant + 1 -- simple and
    correct for this platform's write volume (a handful of hires per
    day, not a high-concurrency counter needing a dedicated sequence
    table). Never manually settable by a caller.
    """
    existing_count = db.query(Employee).filter(Employee.tenant_id == tenant_id).count()
    sequence = existing_count + 1
    return f"{tenant_code}-{sequence:03d}"


def transition_employee_status(
    db: Session,
    employee: Employee,
    new_status: str,
    *,
    reason: Optional[str] = None,
    changed_by: Optional[str] = None,
) -> Employee:
    """
    Validates the transition against ALLOWED_STATUS_TRANSITIONS, applies
    it, and inserts an immutable history record -- all in the caller's
    existing transaction (does not call db.commit() itself, same
    same-transaction discipline as write_audit_log()).
    """
    current = employee.status
    allowed = ALLOWED_STATUS_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise InvalidStatusTransition(
            f"Cannot transition employee from '{current}' to '{new_status}'. "
            f"Allowed from '{current}': {sorted(allowed) or 'none (terminal state)'}"
        )

    history = EmployeeEmploymentHistory(
        tenant_id=employee.tenant_id,
        employee_id=employee.id,
        change_type="STATUS",
        old_value=json.dumps({"status": current}),
        new_value=json.dumps({"status": new_status}),
        effective_date=date.today(),
        reason=reason,
        changed_by=changed_by,
    )
    employee.status = new_status
    db.add(employee)
    db.add(history)
    return employee


# ---------------------------------------------------------------------------
# S-351 / HRMS-0512 -- Delivery Engine Assignment: Speciality vs Core.
#
# HRMS-0160/HRMS-0708's fuller "Convert Candidate to Employee" story
# (offers, preboarding documents, the full onboarding handoff) is not
# built in this codebase yet -- flagged previously in this session's
# CLAUDE.md. convert_candidate_to_employee() below is the minimal slice
# this specific story actually needs (an Employee row exists, engine is
# locked to SPECIALITY), not a reimplementation of that larger story --
# a future HRMS-0708 build extends this function rather than replacing it.
# ---------------------------------------------------------------------------

def convert_candidate_to_employee(
    db: Session,
    candidate: Candidate,
    *,
    joining_date: date,
    tenant_id: Optional[int] = None,
    changed_by: Optional[str] = None,
    **employee_fields,
) -> Employee:
    """
    BR: all new hires enter SPECIALITY, zero exceptions -- delivery_engine
    is hardcoded here, never taken from a caller-supplied value. Any
    attempt to pass delivery_engine in employee_fields raises rather
    than being silently overridden, so a caller relying on a different
    value fails loudly instead of quietly getting SPECIALITY anyway.
    """
    if employee_fields.get("delivery_engine") not in (None, "SPECIALITY"):
        raise CoreAssignmentNotAllowed(
            "New hires must enter SPECIALITY delivery engine. Core assignment "
            "requires the Core Eligibility Gate (HRMS-0513) via set_core_delivery_engine()."
        )
    employee_fields.pop("delivery_engine", None)

    employee = Employee(
        tenant_id=tenant_id,
        candidate_id=candidate.candidateID,
        first_name=candidate.candidateFirstName or "",
        last_name=candidate.candidateLastName or "",
        email=candidate.candidateEmail,
        joining_date=joining_date,
        delivery_engine="SPECIALITY",
        engine_entry_date=joining_date,
        **employee_fields,
    )
    db.add(employee)
    db.flush()

    # BR: engine change audit trail starts at creation, not just at the
    # first later transition -- from_engine=None signals "initial
    # assignment," distinct from an actual SPECIALITY->CORE change.
    db.add(EmployeeEngineHistory(
        tenant_id=tenant_id, employee_id=employee.id,
        from_engine=None, to_engine="SPECIALITY",
        changed_by=changed_by, reason="Initial hire -- all new hires enter SPECIALITY.",
    ))

    return employee


def set_core_delivery_engine(
    db: Session,
    employee: Employee,
    *,
    approval_reference: str,
    changed_by: str,
    reason: str,
) -> Employee:
    """
    BR: the ONLY function that may ever set delivery_engine=CORE.
    Requires the employee to already be core_certified (the DB CHECK
    constraint enforces this independently, at the row level, even
    against a raw SQL UPDATE bypassing this function entirely) and a
    real approval_reference -- the Core Eligibility Gate ID this
    session's HRMS-0513 build (not yet implemented) would produce.
    Absent that full gate workflow, this function is the real, callable
    mutation a future HRMS-0513 build wires its BU Head approval step
    into, rather than a placeholder.
    """
    if not employee.core_certified:
        raise CoreAssignmentNotAllowed(
            f"Employee {employee.id} is not core_certified -- CORE can only be "
            f"assigned via the Core Eligibility Gate (HRMS-0513) after BU Head approval."
        )
    if not approval_reference:
        raise CoreAssignmentNotAllowed("approval_reference (Core Eligibility Gate ID) is required.")

    previous_engine = employee.delivery_engine
    employee.delivery_engine = "CORE"
    db.add(employee)

    db.add(EmployeeEngineHistory(
        tenant_id=employee.tenant_id, employee_id=employee.id,
        from_engine=previous_engine, to_engine="CORE",
        changed_by=changed_by, approval_reference=approval_reference, reason=reason,
    ))

    return employee
