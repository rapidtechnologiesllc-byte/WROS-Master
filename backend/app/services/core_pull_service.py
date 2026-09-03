"""
S-353/HRMS-0514 -- Core-Pull Conflict Rule Engine ("Core Wins Policy") and
import logging
S-373/HRMS-0529 -- Specialty Pool Minimum 40 Core-Certified Guard.

Built directly from `Requirements/S-353_HRMS-0514.docx` and
`Requirements/S-373_HRMS-0529.docx` -- see app.models.core_pull's module
docstring on the HRMS-0312 mislabeling this deliberately does NOT follow.

Bundled in one file, not two, because S-373's guard has no meaningful
existence separate from being called by S-353's execute step (and by
S-372's Confirmed/Potential Demand Workflow, and any future manual
transfer) -- same "closely-coupled pieces share a module" convention as
thunder_service.py's A1 send-governance + test-chat mode.

The one rule this whole module exists to protect: Core-Pull decision
logic ("does this employee's Core demand win over their Speciality
allocation") lives in exactly one place -- detect_core_pull_conflict()
below. HRMS-1105 (Part A, not yet built) and S-372 (Part A, not yet
built) must call this, never reimplement "Core wins" themselves.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.demand import Demand
from app.models.employee import Employee, EmployeeEngineHistory
from app.models.employee_allocation import EmployeeAllocation
from app.models.core_pull import CorePullEvent, SpecialtyPoolReplacementPlan
from app.models.user import Users
from app.services.notification_service import send_notification
from app.services.orchestration_router_service import evaluate_action_intent

CORE_PULL_AGENT_ID = "core_pull_engine"
SPECIALTY_POOL_MINIMUM = 40  # S-373 BR: a hard floor, not a target
REPLACEMENT_STRATEGY_MIN_CHARS = 100
OVERRIDE_JUSTIFICATION_MIN_CHARS = 100
OVERRIDE_ALERT_THRESHOLD = 2  # more than this many overrides in 30 days pages the Director
OVERRIDE_ALERT_WINDOW_DAYS = 30

logger = logging.getLogger(__name__)

class SpecialtyPoolBelowMinimum(Exception):
    """S-373: a Core move that would drop the Specialty Core-Certified
    pool below SPECIALTY_POOL_MINIMUM is blocked until a replacement
    plan is logged for this employee."""


class CorePullOverrideForbidden(Exception):
    """S-353: only a BU Head may override a pending Core-Pull."""


class InvalidReplacementPlan(Exception):
    pass


class InvalidOverrideJustification(Exception):
    pass


# ===========================================================================
# S-373/HRMS-0529 -- Specialty Pool Minimum 40 Core-Certified Guard
# ===========================================================================

def check_specialty_pool_guard(db: Session, employee_being_moved: Employee) -> Dict:
    """
    SpecialtyPoolGuard.check() -- counts Core-Certified employees
    currently deployed in Specialty (excluding exited staff), simulates
    the pool size if employee_being_moved left it.

    The doc's own SQL sketch excludes status IN ('BUDDY_PROGRAM','EXITED')
    -- 'BUDDY_PROGRAM' isn't a real Employee.status value in this codebase
    (buddy_program_status is a separate field); EXITED is real and is
    what's actually excluded here.
    """
    count = (
        db.query(Employee)
        .filter(
            Employee.tenant_id == employee_being_moved.tenant_id,
            Employee.delivery_engine == "SPECIALITY",
            Employee.core_certified.is_(True),
            Employee.status != "EXITED",
        )
        .count()
    )
    pool_size_after_move = count - 1
    return {
        "pool_size_before_move": count,
        "pool_size_after_move": pool_size_after_move,
        "below_minimum": pool_size_after_move < SPECIALTY_POOL_MINIMUM,
        "at_edge": pool_size_after_move == SPECIALTY_POOL_MINIMUM,  # AC-6: alert at 41 -> 40
        "gap": max(0, SPECIALTY_POOL_MINIMUM - pool_size_after_move),
    }


def get_specialty_pool_status(db: Session, *, tenant_id: Optional[int] = None) -> Dict:
    """Read-only current pool size for a dashboard view -- no specific
    employee being moved, so no 'after move' simulation (that's
    check_specialty_pool_guard()'s job, called per-move by
    execute_core_pull()). Same count query, same exclusions."""
    count = (
        db.query(Employee)
        .filter(
            Employee.tenant_id == tenant_id,
            Employee.delivery_engine == "SPECIALITY",
            Employee.core_certified.is_(True),
            Employee.status != "EXITED",
        )
        .count()
    )
    return {
        "pool_size": count,
        "below_minimum": count < SPECIALTY_POOL_MINIMUM,
        "at_edge": count == SPECIALTY_POOL_MINIMUM + 1,  # one more loss would breach
        "gap": max(0, SPECIALTY_POOL_MINIMUM - count),
    }


def log_replacement_plan(
    db: Session,
    *,
    employee_being_moved: Employee,
    replacement_strategy: str,
    expected_replacement_date: date,
    logged_by: Optional[str] = None,
) -> SpecialtyPoolReplacementPlan:
    """BU Head logs this to unblock a Core move that would breach the
    40-minimum floor. 'We will hire someone' is not a plan -- both a
    100+ char strategy and an expected date are required."""
    if len(replacement_strategy or "") < REPLACEMENT_STRATEGY_MIN_CHARS:
        raise InvalidReplacementPlan(
            f"replacement_strategy must be at least {REPLACEMENT_STRATEGY_MIN_CHARS} characters."
        )
    if not expected_replacement_date:
        raise InvalidReplacementPlan("expected_replacement_date is required.")

    plan = SpecialtyPoolReplacementPlan(
        tenant_id=employee_being_moved.tenant_id,
        employee_id_moving=employee_being_moved.id,
        replacement_strategy=replacement_strategy,
        expected_replacement_date=expected_replacement_date,
        logged_by=logged_by,
        # Explicit, not the column's server_default -- must be directly
        # comparable to CorePullEvent.detected_at (also set explicitly, see
        # that constructor's comment) in _has_replacement_plan_since().
        # Mixing a Python-side microsecond-precision timestamp against a
        # SQLite server_default=func.now() value (no fractional seconds)
        # can make a plan logged AFTER detection sort as "before" it purely
        # from string-length differences -- same clock on both sides avoids
        # that regardless of backend.
        logged_at=datetime.utcnow(),
    )
    db.add(plan)
    db.flush()
    return plan


def _has_replacement_plan_since(db: Session, employee_id: str, *, since: datetime) -> bool:
    return (
        db.query(SpecialtyPoolReplacementPlan)
        .filter(
            SpecialtyPoolReplacementPlan.employee_id_moving == employee_id,
            SpecialtyPoolReplacementPlan.logged_at >= since,
        )
        .first()
        is not None
    )


# ===========================================================================
# S-353/HRMS-0514 -- CorePullEngine
# ===========================================================================

def detect_core_pull_conflict(
    db: Session, employee: Employee, core_demand: Demand,
) -> Optional[CorePullEvent]:
    """
    CorePullEngine.detect() -- the single place "does this employee have
    a genuine Core-vs-Speciality conflict" gets decided. Called per-
    candidate by whoever is proposing the Core move (HRMS-1105's scan,
    S-372's Confirmed/Potential Demand Workflow, a manual transfer) --
    not a standalone cron this module owns; the phase doc's own caller
    list is all per-employee-per-demand invocations, not a sweep.

    Returns None when there's no conflict (core_demand isn't CORE, the
    employee isn't Core-Certified, or they have no active Speciality
    allocation to pull from) -- a None return means "nothing to do",
    not an error. Idempotent: a second call for the same employee+demand
    while a PENDING event already exists returns that same event rather
    than creating a duplicate.
    """
    if core_demand.delivery_engine != "CORE":
        return None
    if not employee.core_certified:
        return None

    existing_pending = (
        db.query(CorePullEvent)
        .filter(
            CorePullEvent.employee_id == employee.id,
            CorePullEvent.core_demand_id == core_demand.id,
            CorePullEvent.status == "PENDING",
        )
        .first()
    )
    if existing_pending:
        return existing_pending

    active_speciality_allocation = (
        db.query(EmployeeAllocation)
        .join(Demand, EmployeeAllocation.demand_id == Demand.id)
        .filter(
            EmployeeAllocation.employee_id == employee.id,
            EmployeeAllocation.status == "ACTIVE",
            Demand.delivery_engine == "SPECIALITY",
        )
        .first()
    )
    if not active_speciality_allocation:
        return None

    event = CorePullEvent(
        tenant_id=employee.tenant_id,
        employee_id=employee.id,
        core_demand_id=core_demand.id,
        speciality_allocation_id=active_speciality_allocation.id,
        status="PENDING",
        # Set explicitly rather than relying on the column's server_default
        # -- execute_core_pull() compares this against
        # SpecialtyPoolReplacementPlan.logged_at, and a flush() alone
        # doesn't reliably read a server-generated default back into this
        # Python object (it can still read as None), which would silently
        # make _has_replacement_plan_since()'s `>= None` comparison always
        # false. Real wall-clock time either way, just set on this side.
        detected_at=datetime.utcnow(),
    )
    db.add(event)
    db.flush()
    return event


def execute_core_pull(
    db: Session,
    event: CorePullEvent,
    *,
    tenant_id: Optional[int] = None,
    speciality_rm: Optional[Users] = None,
    bu_head: Optional[Users] = None,
) -> CorePullEvent:
    """
    CorePullEngine.execute() -- same-day, no negotiation. Not
    allocate_employee_to_project()'s normal gate: BuddyProgramNotGraduated
    and EmployeeAlreadyAllocated don't apply here (this employee is
    already Core-Certified, and holding an active Speciality allocation
    is the very thing being transferred, not a conflict to block on).

    speciality_rm/bu_head: caller-supplied, best-effort notifications --
    this codebase has no RM/BU-Head roster resolution built (same posture
    as orchestration_router_service's own `director` param). A failed
    notification never blocks the transfer itself.

    Raises SpecialtyPoolBelowMinimum (S-373, unless a replacement plan
    was logged after this event was detected) or whatever the
    Orchestration Router raises (ActionBlocked/ActionDelayed) -- both
    mean the caller must not proceed yet.
    """
    if event.status != "PENDING":
        raise ValueError(f"CorePullEvent {event.id} is not PENDING (status={event.status}).")

    employee = db.query(Employee).filter(Employee.id == event.employee_id).first()
    speciality_allocation = (
        db.query(EmployeeAllocation).filter(EmployeeAllocation.id == event.speciality_allocation_id).first()
    )
    core_demand = db.query(Demand).filter(Demand.id == event.core_demand_id).first()

    guard = check_specialty_pool_guard(db, employee)
    if guard["below_minimum"] and not _has_replacement_plan_since(db, employee.id, since=event.detected_at):
        raise SpecialtyPoolBelowMinimum(
            f"Moving {employee.id} to Core would drop the Specialty Core-Certified pool to "
            f"{guard['pool_size_after_move']} (below the {SPECIALTY_POOL_MINIMUM} minimum). "
            f"Log a replacement plan before this move can proceed."
        )

    # Consulted as a formality/audit-trail step for this action_type (no
    # seeded ConflictRule currently targets "core_pull_transfer"), but a
    # future rule addition or router failure still gets a real chance to
    # intervene -- same governance every other risk-bearing action goes
    # through, Core-Pull isn't quietly exempted from it.
    evaluate_action_intent(
        db, agent_id=CORE_PULL_AGENT_ID, entity_type="employee_allocation",
        entity_id=speciality_allocation.id, action_type="core_pull_transfer",
        risk_tier="MEDIUM", tenant_id=tenant_id, director=bu_head,
    )

    today = date.today()
    speciality_allocation.status = "CORE_PULLED"
    speciality_allocation.end_date = today
    db.add(speciality_allocation)

    new_allocation = EmployeeAllocation(
        tenant_id=tenant_id, employee_id=employee.id, demand_id=core_demand.id,
        client_id=core_demand.client_id, start_date=today,
        utilization_pct=speciality_allocation.utilization_pct,
        billing_rate_usd_cents=core_demand.billing_rate_usd_cents,
    )
    db.add(new_allocation)
    db.flush()

    if employee.delivery_engine != "CORE":
        employee.delivery_engine = "CORE"
        db.add(employee)

    db.add(EmployeeEngineHistory(
        tenant_id=tenant_id, employee_id=employee.id, from_engine="SPECIALITY", to_engine="CORE",
        reason="Core-Pull", approval_reference=event.id,
    ))

    event.status = "EXECUTED"
    event.executed_at = datetime.utcnow()
    db.add(event)

    employee_name = f"{employee.first_name} {employee.last_name}".strip()
    if speciality_rm is not None:
        try:
            send_notification(
                db, calling_context_tenant_id=tenant_id, recipient=speciality_rm, priority_tier="P0",
                message=(
                    f"CORE PULL: {employee_name} reallocated to Core demand {core_demand.id}. "
                    f"Effective today. Please plan replacement sourcing."
                ),
            )
        except Exception:
            pass  # best-effort -- never blocks the transfer itself
    if bu_head is not None:
        try:
            send_notification(
                db, calling_context_tenant_id=tenant_id, recipient=bu_head, priority_tier="P1",
                message=(
                    f"Core-Pull executed: {employee_name} moved to Core demand {core_demand.id}. "
                    f"Specialty pool now at {guard['pool_size_after_move']} Core-Certified."
                ),
            )
        except Exception:
            pass

    return event


def override_core_pull(
    db: Session,
    event: CorePullEvent,
    *,
    actor_role: str,
    actor_user_id: str,
    justification: str,
    tenant_id: Optional[int] = None,
    director: Optional[Users] = None,
) -> CorePullEvent:
    """
    BU Head override path. Specialty allocation is never touched --
    it simply continues; the Core demand stays open for alternative
    sourcing. More than OVERRIDE_ALERT_THRESHOLD overrides in
    OVERRIDE_ALERT_WINDOW_DAYS days pages the Director (best-effort,
    caller-supplied recipient, same posture as every other roster-
    resolution gap already flagged in this codebase).
    """
    if actor_role != "BU Head":
        raise CorePullOverrideForbidden(
            f"Core-Pull override requires BU Head role, got '{actor_role}'."
        )
    if event.status != "PENDING":
        raise ValueError(f"CorePullEvent {event.id} is not PENDING (status={event.status}).")
    if len(justification or "") < OVERRIDE_JUSTIFICATION_MIN_CHARS:
        raise InvalidOverrideJustification(
            f"Override justification must be at least {OVERRIDE_JUSTIFICATION_MIN_CHARS} characters."
        )

    event.status = "OVERRIDDEN"
    event.override_justification = justification
    event.overridden_by = actor_user_id
    event.overridden_at = datetime.utcnow()
    db.add(event)
    db.flush()

    window_start = datetime.utcnow() - timedelta(days=OVERRIDE_ALERT_WINDOW_DAYS)
    recent_overrides = (
        db.query(CorePullEvent)
        .filter(
            CorePullEvent.tenant_id == tenant_id,
            CorePullEvent.status == "OVERRIDDEN",
            CorePullEvent.overridden_at >= window_start,
        )
        .count()
    )
    if recent_overrides > OVERRIDE_ALERT_THRESHOLD and director is not None:
        try:
            send_notification(
                db, calling_context_tenant_id=tenant_id, recipient=director, priority_tier="P1",
                message=(
                    f"Core-Pull override pattern: {recent_overrides} overrides in the last "
                    f"{OVERRIDE_ALERT_WINDOW_DAYS} days. Core pool may be insufficient."
                ),
            )
        except Exception:
            pass

    return event
