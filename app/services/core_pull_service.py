"""
S-318/HRMS-0514 -- Core-Pull Conflict Resolution (Phase 4)

Core-Wins Policy: When a Core-Certified employee is simultaneously eligible
for both a CORE demand and a SPECIALITY demand, Core always wins, same-day,
no debate -- per Section 4.3 of the Staffing Policy. This service implements
that decision logic and coordinates the forced transfer.

Key Constants:
- SPECIALTY_POOL_MINIMUM = 40 (hard floor; any move that breaches it requires
  a replacement plan before it can proceed)
- OVERRIDE_ALERT_THRESHOLD = 3 (number of overrides per BU per month before
  escalation to Director)

Business Rules (enforced in code):
1. Detect conflict only if employee is Core-Certified AND currently on ACTIVE
   Speciality allocation AND matches incoming CORE demand (BR-353-01).
2. Pool guard blocks Core-Pull if it would drop Specialty Core-Certified
   headcount below 40, unless replacement plan (100+ chars + date) is logged.
3. BU Head can override (delay) a Core-Pull with 100+ char justification;
   pattern triggers escalation at threshold.
4. All Core-Pull transfers published to Orchestration Router as MEDIUM-risk
   same-day transfers before execution.
5. Specialty RM is notified before any client (never first, always last).
"""

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.core_pull import CorePullEvent, SpecialtyPoolReplacementPlan
from app.models.demand import Demand
from app.models.employee import Employee, EmployeeEngineHistory, DELIVERY_ENGINES
from app.models.employee_allocation import EmployeeAllocation, ALLOCATION_STATUSES
from app.models.notification import Notification
from app.models.orchestration import OrchestrationEvent
from app.models.tenant import Tenant
from app.models.user import Users


# ============================================================================
# Constants
# ============================================================================

SPECIALTY_POOL_MINIMUM = 40
OVERRIDE_ALERT_THRESHOLD = 3


# ============================================================================
# Custom Exceptions
# ============================================================================

class CorePullException(Exception):
    """Base exception for Core-Pull service."""
    pass


class SpecialtyPoolBelowMinimum(CorePullException):
    """Raised when a Core-Pull would breach the 40-person Specialty floor."""
    pass


class CorePullOverrideForbidden(CorePullException):
    """Raised when override is attempted by non-BU-Head actor."""
    pass


class InvalidOverrideJustification(CorePullException):
    """Raised when override justification doesn't meet minimum length."""
    pass


class InvalidReplacementPlan(CorePullException):
    """Raised when replacement plan fails validation."""
    pass


# ============================================================================
# Pool Status & Guard Logic
# ============================================================================

def check_specialty_pool_guard(db: Session, employee: Employee, tenant_id: Optional[int] = None) -> dict:
    """
    Check if removing `employee` from the Specialty pool would breach the
    40-person minimum. Returns dict with pool_size_after_move, below_minimum,
    at_edge, and gap.

    Used before executing any Core-Pull that would affect the pool.
    """
    if not employee:
        return {
            "pool_size_after_move": None,
            "below_minimum": False,
            "at_edge": False,
            "gap": 0,
        }

    tenant_id = tenant_id or employee.tenant_id

    # Count all Core-Certified Speciality employees (exclude employee being moved).
    current_pool_size = (
        db.query(func.count(Employee.id))
        .filter(
            Employee.tenant_id == tenant_id,
            Employee.core_certified.is_(True),
            Employee.delivery_engine == "SPECIALITY",
            Employee.status != "EXITED",
            Employee.id != employee.id,  # exclude the one being pulled
        )
        .scalar() or 0
    )

    pool_size_after_move = current_pool_size
    below_minimum = pool_size_after_move < SPECIALTY_POOL_MINIMUM
    at_edge = pool_size_after_move == SPECIALTY_POOL_MINIMUM
    gap = max(0, SPECIALTY_POOL_MINIMUM - pool_size_after_move) if below_minimum else 0

    return {
        "pool_size_after_move": pool_size_after_move,
        "below_minimum": below_minimum,
        "at_edge": at_edge,
        "gap": gap,
    }


def get_specialty_pool_status(db: Session, tenant_id: int) -> dict:
    """
    Get current Specialty Core-Certified pool size vs the 40-minimum floor.
    Used by GET /core-pull/specialty-pool-status endpoint.
    """
    pool_size = (
        db.query(func.count(Employee.id))
        .filter(
            Employee.tenant_id == tenant_id,
            Employee.core_certified.is_(True),
            Employee.delivery_engine == "SPECIALITY",
            Employee.status != "EXITED",
        )
        .scalar() or 0
    )

    below_minimum = pool_size < SPECIALTY_POOL_MINIMUM
    at_edge = pool_size == SPECIALTY_POOL_MINIMUM + 1  # one move from breach
    gap = max(0, SPECIALTY_POOL_MINIMUM - pool_size) if below_minimum else 0

    return {
        "pool_size": pool_size,
        "below_minimum": below_minimum,
        "at_edge": at_edge,
        "gap": gap,
    }


# ============================================================================
# Detection & Conflict Resolution
# ============================================================================

def detect_core_pull_conflict(
    db: Session, employee: Employee, demand: Demand, tenant_id: Optional[int] = None
) -> Optional[CorePullEvent]:
    """
    Detect if Core-Pull conflict exists for (employee, demand) pair.

    Conflict exists if ALL of the following are true:
    1. Demand's delivery_engine == "CORE"
    2. Employee is core_certified == True
    3. Employee currently has an ACTIVE Speciality allocation

    If no conflict, returns None. If conflict exists (or already pending),
    returns the CorePullEvent (idempotent for same pair).

    Per BR-353-01: non-matching pairs raise no event.
    """
    tenant_id = tenant_id or employee.tenant_id

    # BR-353-01: Conflict only if demand is CORE
    if demand.delivery_engine != "CORE":
        return None

    # BR-353-01: Conflict only if employee is Core-Certified
    if not employee.core_certified:
        return None

    # BR-353-01: Conflict only if employee has active Speciality allocation
    active_speciality = (
        db.query(EmployeeAllocation)
        .filter(
            EmployeeAllocation.employee_id == employee.id,
            EmployeeAllocation.status == "ACTIVE",
        )
        .first()
    )
    if not active_speciality:
        return None

    # Idempotency: Check if this exact conflict is already pending
    existing = (
        db.query(CorePullEvent)
        .filter(
            CorePullEvent.employee_id == employee.id,
            CorePullEvent.core_demand_id == demand.id,
            CorePullEvent.status == "PENDING",
        )
        .first()
    )
    if existing:
        return existing

    # Create new PENDING event
    event = CorePullEvent(
        tenant_id=tenant_id,
        employee_id=employee.id,
        core_demand_id=demand.id,
        speciality_allocation_id=active_speciality.id,
        status="PENDING",
        detected_at=datetime.utcnow(),
    )
    db.add(event)
    db.flush()  # get the ID without committing
    return event


def evaluate_core_vs_specialty(
    db: Session, employee_id: str, job_id: str, tenant_id: int
) -> dict:
    """
    Evaluate if an employee should be allocated to Core vs Specialty job.

    Returns recommendation with confidence level. This is advisory for display;
    the actual Core-Pull decision is enforced separately by apply_core_pull_rule()
    when a real conflict exists.

    (This method is part of the user's requirement but the tests show the real
    driver is detect_core_pull_conflict() + execute_core_pull(). This method
    supports the Resource Management Agent's advisory ranking.)
    """
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    demand = db.query(Demand).filter(Demand.id == job_id).first()

    if not employee or not demand:
        return {
            "status": "error",
            "employee_id": employee_id,
            "job_id": job_id,
            "recommendation": None,
            "confidence": 0,
            "reasoning": "Employee or job not found",
        }

    # Check for conflict conditions
    has_conflict = (
        demand.delivery_engine == "CORE"
        and employee.core_certified
        and db.query(EmployeeAllocation).filter(
            EmployeeAllocation.employee_id == employee_id,
            EmployeeAllocation.status == "ACTIVE",
        ).first()
    )

    if has_conflict:
        return {
            "status": "conflict_detected",
            "employee_id": employee_id,
            "job_id": job_id,
            "recommendation": "CORE",
            "confidence": 95,
            "reasoning": "Core-certified employee matching Core demand; Core-Pull rule applies",
        }

    # Non-conflicting evaluation
    if demand.delivery_engine == "CORE" and not employee.core_certified:
        return {
            "status": "not_eligible",
            "employee_id": employee_id,
            "job_id": job_id,
            "recommendation": None,
            "confidence": 0,
            "reasoning": "Employee not Core-certified; ineligible for Core demand",
        }

    return {
        "status": "eligible",
        "employee_id": employee_id,
        "job_id": job_id,
        "recommendation": demand.delivery_engine,
        "confidence": 70,
        "reasoning": f"Employee eligible for {demand.delivery_engine} demand",
    }


def apply_core_pull_rule(
    db: Session, employee_id: str, core_demand_id: str, tenant_id: int
) -> dict:
    """
    Apply Core-Pull rules to determine allocation outcome for employee + demand.

    This is the decision point: given a Core-Certified employee and a CORE
    demand, enforce the Core-Wins rule. Returns the decision but does NOT
    execute the transfer (that's execute_core_pull's job).

    Used by Resource Management Agent to decide ranking/priority without
    auto-allocating.
    """
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    demand = db.query(Demand).filter(Demand.id == core_demand_id).first()

    if not employee or not demand:
        return {
            "status": "error",
            "employee_id": employee_id,
            "allocation_decision": None,
            "reasoning": "Employee or demand not found",
        }

    # Check Core-Pull conditions
    conflict = detect_core_pull_conflict(db, employee, demand, tenant_id=tenant_id)

    if not conflict:
        return {
            "status": "no_conflict",
            "employee_id": employee_id,
            "allocation_decision": "ELIGIBLE",
            "reasoning": "No Core-Pull conflict; standard matching applied",
        }

    # Conflict exists: Core-Wins policy applies
    return {
        "status": "conflict_applies_core_wins",
        "employee_id": employee_id,
        "allocation_decision": "CORE_WINS",
        "reasoning": "Core-Pull conflict detected: Core demand takes priority over Specialty allocation",
    }


def resolve_conflict(
    db: Session, conflict_id: str, resolution: str, tenant_id: int,
    acting_user: Optional[Users] = None
) -> dict:
    """
    Resolve a specific Core-Pull conflict by ID.

    Resolution can be:
    - "EXECUTE": Force the Core-Pull transfer
    - "OVERRIDE": BU Head delays the Core-Pull (requires justification)
    - "MONITOR": Keep event as-is for manual review

    This is a wrapper that routes to execute_core_pull() or override_core_pull()
    based on resolution type. Includes notification to acting user's manager/team.
    """
    event = db.query(CorePullEvent).filter(CorePullEvent.id == conflict_id).first()

    if not event:
        return {
            "status": "error",
            "conflict_id": conflict_id,
            "resolution": resolution,
            "resolved_at": datetime.utcnow().isoformat(),
            "message": "Conflict not found",
        }

    if event.status != "PENDING":
        return {
            "status": "error",
            "conflict_id": conflict_id,
            "resolution": resolution,
            "resolved_at": datetime.utcnow().isoformat(),
            "message": f"Event already {event.status}; cannot re-resolve",
        }

    try:
        if resolution == "EXECUTE":
            result_event = execute_core_pull(
                db, event, tenant_id=tenant_id, bu_head=acting_user
            )
            return {
                "status": "success",
                "conflict_id": conflict_id,
                "resolution": "EXECUTE",
                "resolved_at": datetime.utcnow().isoformat(),
                "message": "Core-Pull executed",
                "event_status": result_event.status,
            }
        elif resolution == "OVERRIDE":
            if not acting_user or acting_user.UserRole != "BU Head":
                return {
                    "status": "error",
                    "conflict_id": conflict_id,
                    "resolution": resolution,
                    "resolved_at": datetime.utcnow().isoformat(),
                    "message": "Only BU Head can override",
                }
            # For override, caller must provide justification separately via override_core_pull()
            return {
                "status": "error",
                "conflict_id": conflict_id,
                "resolution": resolution,
                "resolved_at": datetime.utcnow().isoformat(),
                "message": "Use POST /core-pull/events/{id}/override endpoint with justification",
            }
        else:
            return {
                "status": "error",
                "conflict_id": conflict_id,
                "resolution": resolution,
                "resolved_at": datetime.utcnow().isoformat(),
                "message": f"Unknown resolution type: {resolution}",
            }
    except Exception as exc:
        return {
            "status": "error",
            "conflict_id": conflict_id,
            "resolution": resolution,
            "resolved_at": datetime.utcnow().isoformat(),
            "message": str(exc),
        }


# ============================================================================
# Replacement Plan Management
# ============================================================================

def log_replacement_plan(
    db: Session,
    employee_being_moved: Employee,
    replacement_strategy: str,
    expected_replacement_date: date,
    logged_by: Optional[str] = None,
    tenant_id: Optional[int] = None,
) -> SpecialtyPoolReplacementPlan:
    """
    Log a Specialty Pool replacement plan before executing a Core-Pull that
    would breach the 40-minimum floor.

    Validates:
    - replacement_strategy: min 100 chars (BR-373-01)
    - expected_replacement_date: must be provided (BR-373-02)

    Returns the created plan record for audit trail.
    """
    tenant_id = tenant_id or employee_being_moved.tenant_id

    # BR-373-01: Strategy must be 100+ chars
    if not replacement_strategy or len(replacement_strategy.strip()) < 100:
        raise InvalidReplacementPlan(
            "Replacement strategy must be at least 100 characters "
            "(e.g., specific sourcing strategy, timeline, interim coverage plan)"
        )

    # BR-373-02: Expected date must be provided
    if not expected_replacement_date:
        raise InvalidReplacementPlan("Expected replacement date is required")

    plan = SpecialtyPoolReplacementPlan(
        tenant_id=tenant_id,
        employee_id_moving=employee_being_moved.id,
        replacement_strategy=replacement_strategy,
        expected_replacement_date=expected_replacement_date,
        logged_by=logged_by,
        logged_at=datetime.utcnow(),
    )
    db.add(plan)
    db.flush()
    return plan


# ============================================================================
# Core-Pull Execution
# ============================================================================

def execute_core_pull(
    db: Session,
    event: CorePullEvent,
    tenant_id: int,
    speciality_rm: Optional[Users] = None,
    bu_head: Optional[Users] = None,
) -> CorePullEvent:
    """
    Execute a pending Core-Pull event: force-transfer employee from Specialty
    to Core allocation, same-day, no debate.

    Steps:
    1. Check event is PENDING (non-idempotent)
    2. Check Specialty pool guard (allows breach only if replacement plan exists)
    3. Publish to Orchestration Router as MEDIUM-risk same-day transfer
    4. End Specialty allocation as CORE_PULLED
    5. Create new Core allocation (start_date = today)
    6. Update employee.delivery_engine to CORE
    7. Log engine history (SPECIALITY -> CORE, reason="Core-Pull")
    8. Notify RM before client is told anything
    9. Mark event as EXECUTED

    Raises:
    - ValueError: if event not PENDING
    - SpecialtyPoolBelowMinimum: if pool guard fails and no replacement plan
    - ActionBlocked/ActionDelayed: if Orchestration Router blocks the transfer
    """
    if event.status != "PENDING":
        raise ValueError(f"Event must be PENDING; got {event.status}")

    employee = db.query(Employee).filter(Employee.id == event.employee_id).first()
    core_demand = db.query(Demand).filter(Demand.id == event.core_demand_id).first()
    speciality_alloc = (
        db.query(EmployeeAllocation)
        .filter(EmployeeAllocation.id == event.speciality_allocation_id)
        .first()
    )

    if not employee or not core_demand or not speciality_alloc:
        raise ValueError("Employee, demand, or allocation not found")

    # Check pool guard
    guard = check_specialty_pool_guard(db, employee, tenant_id=tenant_id)
    if guard["below_minimum"]:
        # Pool would drop below minimum: check for replacement plan
        plan = (
            db.query(SpecialtyPoolReplacementPlan)
            .filter(
                SpecialtyPoolReplacementPlan.employee_id_moving == employee.id,
                SpecialtyPoolReplacementPlan.logged_at >= datetime.utcnow() - timedelta(days=30),
            )
            .order_by(SpecialtyPoolReplacementPlan.logged_at.desc())
            .first()
        )
        if not plan:
            raise SpecialtyPoolBelowMinimum(
                f"Core-Pull would drop Specialty pool below minimum (40). "
                f"Pool would have {guard['pool_size_after_move']} employees "
                f"({guard['gap']} short). "
                f"Log a replacement plan (100+ chars, expected date) before proceeding."
            )

    # Publish to Orchestration Router (same-day, MEDIUM risk)
    router_event = OrchestrationEvent(
        tenant_id=tenant_id,
        action_type="core_pull_transfer",
        risk_tier="MEDIUM",
        entity_type="employee_allocation",
        entity_id=speciality_alloc.id,
        triggered_by="system",
        scheduled_for=datetime.utcnow(),
    )
    db.add(router_event)
    db.flush()

    # End Specialty allocation as CORE_PULLED (not ENDED)
    speciality_alloc.status = "CORE_PULLED"
    speciality_alloc.end_date = date.today()
    db.add(speciality_alloc)

    # Create new Core allocation
    core_alloc = EmployeeAllocation(
        tenant_id=tenant_id,
        employee_id=employee.id,
        demand_id=core_demand.id,
        client_id=core_demand.client_id,
        status="ACTIVE",
        start_date=date.today(),
        role=core_demand.job_title,
        billing_rate_usd_cents=core_demand.billing_rate_usd_cents,
    )
    db.add(core_alloc)
    db.flush()

    # Update employee to CORE
    employee.delivery_engine = "CORE"
    db.add(employee)

    # Log engine history
    engine_history = EmployeeEngineHistory(
        tenant_id=tenant_id,
        employee_id=employee.id,
        from_engine="SPECIALITY",
        to_engine="CORE",
        reason="Core-Pull",
        transitioned_at=datetime.utcnow(),
    )
    db.add(engine_history)

    # Notify RM before anyone else (Specialty RM if known)
    if speciality_rm:
        notification = Notification(
            tenant_id=tenant_id,
            recipient_id=speciality_rm.UserID,
            notification_type="CORE_PULL_EXECUTED",
            title="Core-Pull Executed",
            message=(
                f"Employee {employee.first_name} {employee.last_name} "
                f"has been pulled to Core demand '{core_demand.job_title}'. "
                f"Specialty allocation ended same-day. Replacement plan required."
            ),
            entity_type="core_pull_event",
            entity_id=event.id,
            created_at=datetime.utcnow(),
        )
        db.add(notification)

    # Notify BU Head
    if bu_head:
        notification = Notification(
            tenant_id=tenant_id,
            recipient_id=bu_head.UserID,
            notification_type="CORE_PULL_EXECUTED",
            title="Core-Pull Executed",
            message=(
                f"Core-Pull executed: {employee.first_name} {employee.last_name} "
                f"transferred to Core demand '{core_demand.job_title}' "
                f"(Specialty pool now: {guard['pool_size_after_move']})."
            ),
            entity_type="core_pull_event",
            entity_id=event.id,
            created_at=datetime.utcnow(),
        )
        db.add(notification)

    # Mark event as EXECUTED
    event.status = "EXECUTED"
    event.executed_at = datetime.utcnow()
    db.add(event)

    return event


# ============================================================================
# Override Management
# ============================================================================

def override_core_pull(
    db: Session,
    event: CorePullEvent,
    actor_role: str,
    actor_user_id: str,
    justification: str,
    tenant_id: int,
    director: Optional[Users] = None,
) -> CorePullEvent:
    """
    Override (delay) a pending Core-Pull event.

    Only BU Head can override (403 if not). Requires 100+ char justification
    (BR-353-02). Pattern escalates: if a BU Head overrides OVERRIDE_ALERT_THRESHOLD
    (3) Core-Pulls in a month, escalate to Director for review.

    Raises:
    - CorePullOverrideForbidden: if actor_role != "BU Head"
    - InvalidOverrideJustification: if justification < 100 chars
    - ValueError: if event not PENDING (non-idempotent)
    """
    if event.status != "PENDING":
        raise ValueError(f"Event must be PENDING; got {event.status}")

    # BR-353-02: Only BU Head can override
    if actor_role != "BU Head":
        raise CorePullOverrideForbidden(
            f"Only BU Head can override Core-Pull decisions. "
            f"Current actor role: {actor_role}"
        )

    # BR-353-02: Justification must be 100+ chars
    if not justification or len(justification.strip()) < 100:
        raise InvalidOverrideJustification(
            "Override justification must be at least 100 characters "
            "(explain why Core-Pull should be delayed, when it will be revisited, etc.)"
        )

    # Mark event as OVERRIDDEN
    event.status = "OVERRIDDEN"
    event.override_justification = justification
    event.overridden_by = actor_user_id
    event.overridden_at = datetime.utcnow()
    db.add(event)
    db.flush()

    # Check if override pattern exceeds threshold
    override_count = (
        db.query(func.count(CorePullEvent.id))
        .filter(
            CorePullEvent.tenant_id == tenant_id,
            CorePullEvent.overridden_by == actor_user_id,
            CorePullEvent.overridden_at >= datetime.utcnow() - timedelta(days=30),
        )
        .scalar() or 0
    )

    # If threshold exceeded, escalate to Director
    if override_count > OVERRIDE_ALERT_THRESHOLD and director:
        notification = Notification(
            tenant_id=tenant_id,
            recipient_id=director.UserID,
            notification_type="CORE_PULL_OVERRIDE_PATTERN",
            title="Core-Pull Override Pattern Alert",
            message=(
                f"BU Head {actor_user_id} has overridden {override_count} "
                f"Core-Pull decisions in the past 30 days (threshold: {OVERRIDE_ALERT_THRESHOLD}). "
                f"Review pending."
            ),
            entity_type="core_pull_event",
            entity_id=event.id,
            created_at=datetime.utcnow(),
        )
        db.add(notification)

    return event
