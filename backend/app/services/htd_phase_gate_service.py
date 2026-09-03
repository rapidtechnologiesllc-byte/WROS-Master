"""
import logging
S-360/HRMS-P506-REV -- HTD 4-Phase Gate Structure.

record_phase_gate_decision() is the one function that ever advances
employees.htd_phase -- no time-based auto-advance exists anywhere (per
the story's own "Not In Scope": "Do NOT build automatic gate pass based
on time elapsed"). Writes every decision to the performance store
(HRMS-0515, built alongside this story) as a CERTIFICATION_GATE event,
per AC-5.

Interpretation note on "Core Review→COMPLETED: Hemant + BU Head both
log PASS": the doc's own gate_owner_role enum has exactly one value for
this phase ("HEMANT_BU_HEAD"), not two separate roles -- read here as
one gate, one sign-off, from whoever holds that named role, not two
independent approvals. Flagged as this session's interpretation, not a
confirmed reading of an internally ambiguous sentence.

Second interpretation note: htd_phase_gates.gate_decision's own CREATE
TABLE is ENUM('PASS','FAIL','EXTEND') -- "EXIT" is never a valid value
there, even though the doc's prose separately says a FAIL leads to a
BU Head decision of "EXTEND (restart) or EXIT." Read literally against
the schema (authoritative over the prose), EXIT is not a gate_decision
at all -- it's a distinct action on the employee record. exit_htd_track()
below handles it separately, outside htd_phase_gates entirely, rather
than smuggling a fourth value into an enum the doc itself defines with
three.

Not built here, flagged not silently skipped: the 72-hour gate-owner
SLA escalation to BU Head (AC-3) has no scheduler in this codebase --
same cron-wiring-is-follow-up posture as every other scheduled-job
story already in this codebase (e.g. S-365's own 48h SLA).
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.htd_phase_gate import HTD_GATE_DECISIONS, HTD_GATE_PHASES, HTDPhaseGate
from app.services.employee_service import transition_employee_status
from app.services.performance_store_service import write_performance_event

PHASE_SEQUENCE = HTD_GATE_PHASES  # INDUCTION -> SHADOW_DELIVERY -> CONTROLLED_OWNERSHIP -> CORE_ELIGIBILITY_REVIEW
PHASE_GATE_OWNERS = {
    "INDUCTION": "HR",
    "SHADOW_DELIVERY": "TECHNICAL_MANAGER",
    "CONTROLLED_OWNERSHIP": "PRACTICE_HEAD",
    "CORE_ELIGIBILITY_REVIEW": "HEMANT_BU_HEAD",
}
MIN_GATE_NOTE_LENGTH = 50
MAX_EXTENSIONS_PER_PHASE = 1

logger = logging.getLogger(__name__)

class InvalidPhaseGateDecision(Exception):
    pass


class WrongPhaseForGate(Exception):
    """BR: no skipping/backdating -- a gate can only be logged for the
    employee's CURRENT phase."""


class WrongGateOwnerForPhase(Exception):
    pass


class PhaseExtensionLimitReached(Exception):
    """BR: max 1 extension per phase -- a second EXTEND attempt must be
    PASS or EXIT instead."""


def _extension_count(db: Session, employee_id: str, phase: str) -> int:
    return (
        db.query(HTDPhaseGate)
        .filter(
            HTDPhaseGate.employee_id == employee_id,
            HTDPhaseGate.phase == phase,
            HTDPhaseGate.gate_decision == "EXTEND",
        )
        .count()
    )


def record_phase_gate_decision(
    db: Session,
    employee: Employee,
    *,
    phase: str,
    decision: str,
    gate_owner_user_id: str,
    gate_owner_role: str,
    notes: str,
    tenant_id: Optional[int] = None,
) -> HTDPhaseGate:
    if phase not in PHASE_SEQUENCE:
        raise InvalidPhaseGateDecision(f"phase must be one of {PHASE_SEQUENCE}, got '{phase}'.")
    if decision not in HTD_GATE_DECISIONS:
        raise InvalidPhaseGateDecision(f"decision must be one of {HTD_GATE_DECISIONS}, got '{decision}'.")
    if employee.htd_phase != phase:
        raise WrongPhaseForGate(
            f"Employee {employee.id} is currently in phase '{employee.htd_phase}', "
            f"not '{phase}' -- cannot log a gate for a phase they're not in."
        )
    if gate_owner_role != PHASE_GATE_OWNERS[phase]:
        raise WrongGateOwnerForPhase(
            f"Phase '{phase}' requires gate_owner_role='{PHASE_GATE_OWNERS[phase]}', got '{gate_owner_role}'."
        )
    if not notes or len(notes) < MIN_GATE_NOTE_LENGTH:
        raise InvalidPhaseGateDecision(
            f"gate_notes must be at least {MIN_GATE_NOTE_LENGTH} characters (got {len(notes) if notes else 0})."
        )
    if decision == "EXTEND" and _extension_count(db, employee.id, phase) >= MAX_EXTENSIONS_PER_PHASE:
        raise PhaseExtensionLimitReached(
            f"Phase '{phase}' has already been extended once for employee {employee.id} -- "
            f"decision must be PASS or EXIT."
        )

    gate = HTDPhaseGate(
        tenant_id=tenant_id, employee_id=employee.id, phase=phase,
        gate_owner_role=gate_owner_role, gate_owner_user_id=gate_owner_user_id,
        gate_decision=decision, gate_notes=notes,
    )
    db.add(gate)

    write_performance_event(
        db, employee_id=employee.id, event_type="CERTIFICATION_GATE", tenant_id=tenant_id,
        event_data={
            "phase": phase, "decision": decision, "gate_owner_role": gate_owner_role,
            "gate_owner_user_id": gate_owner_user_id, "notes": notes,
        },
    )

    if decision == "PASS":
        current_index = PHASE_SEQUENCE.index(phase)
        if current_index + 1 < len(PHASE_SEQUENCE):
            employee.htd_phase = PHASE_SEQUENCE[current_index + 1]
        else:
            employee.htd_phase = "COMPLETED"  # AC-6: only reachable by passing all 4 gates in order
        db.add(employee)
    # FAIL/EXTEND: htd_phase deliberately unchanged. FAIL just records the
    # failure (a human then chooses EXTEND or exit_htd_track() below);
    # EXTEND itself means "restart this phase," per the doc.

    return gate


def exit_htd_track(
    db: Session, employee: Employee, *, reason: str, changed_by: str, tenant_id: Optional[int] = None,
) -> Employee:
    """
    The BU Head's "EXIT" option after a FAIL -- not a gate_decision value
    (see module docstring on why), a direct action on the employee
    record instead. Still writes a CERTIFICATION_GATE performance event
    for the audit trail (AC-5), just not an htd_phase_gates row.
    """
    if not reason or len(reason) < MIN_GATE_NOTE_LENGTH:
        raise InvalidPhaseGateDecision(
            f"reason must be at least {MIN_GATE_NOTE_LENGTH} characters (got {len(reason) if reason else 0})."
        )

    exited_phase = employee.htd_phase
    employee.htd_phase = "EXITED"
    transition_employee_status(
        db, employee, "PERFORMANCE_MANAGED",
        reason=f"HTD track exit at phase {exited_phase}: {reason}", changed_by=changed_by,
    )

    write_performance_event(
        db, employee_id=employee.id, event_type="CERTIFICATION_GATE", tenant_id=tenant_id,
        event_data={"phase": exited_phase, "decision": "EXIT", "changed_by": changed_by, "notes": reason},
    )

    return employee
