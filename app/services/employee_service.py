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

from app.models.employee import (
    ALLOWED_STATUS_TRANSITIONS,
    Employee,
    EmployeeEmploymentHistory,
)


class InvalidStatusTransition(Exception):
    pass


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
