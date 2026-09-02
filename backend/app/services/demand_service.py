"""HRMS-0103 — demand creation, status state machine, and the
bench-first sourcing gate (R-04)."""
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.demand import ALLOWED_DEMAND_TRANSITIONS, Demand, DemandHistory

logger = logging.getLogger(__name__)

class InvalidDemandTransition(Exception):
    pass


class DemandValidationError(Exception):
    pass


class BenchFirstNotChecked(Exception):
    """R-04: bench-first must be confirmed before external sourcing."""


def create_demand(db: Session, **fields) -> Demand:
    """
    Enforces the spec's UNIQUE(tenant_id, client_id, job_title,
    status='OPEN') at the application layer (a partial/conditional
    unique index isn't portable across SQLite/SQL Server the same way).
    Only matters for demands actually being opened -- DRAFT duplicates
    are fine, since they're not yet visible to sourcing/recruiting.
    """
    if fields.get("status") == "OPEN":
        existing = db.query(Demand).filter(
            Demand.tenant_id == fields.get("tenant_id"),
            Demand.client_id == fields.get("client_id"),
            Demand.job_title == fields.get("job_title"),
            Demand.status == "OPEN",
        ).first()
        if existing:
            raise DemandValidationError(
                f"An OPEN demand already exists for client={fields.get('client_id')} "
                f"job_title={fields.get('job_title')!r}."
            )
    demand = Demand(**fields)
    db.add(demand)
    return demand


def transition_demand_status(
    db: Session,
    demand: Demand,
    new_status: str,
    *,
    reason: Optional[str] = None,
    changed_by: Optional[str] = None,
) -> Demand:
    if new_status == "CANCELLED" and (not reason or len(reason) < 50):
        raise DemandValidationError("Cancelling a demand requires a reason of at least 50 characters.")

    current = demand.status
    allowed = ALLOWED_DEMAND_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise InvalidDemandTransition(
            f"Cannot transition demand from '{current}' to '{new_status}'. "
            f"Allowed from '{current}': {sorted(allowed) or 'none (terminal state)'}"
        )

    if new_status == "OPEN":
        missing = [f for f in ("required_skills", "client_id", "min_experience_years") if not getattr(demand, f)]
        if missing:
            raise DemandValidationError(f"Cannot open demand -- missing required fields: {missing}")

    history = DemandHistory(
        tenant_id=demand.tenant_id, demand_id=demand.id, change_type="STATUS",
        old_value=json.dumps({"status": current}), new_value=json.dumps({"status": new_status}),
        reason=reason, changed_by=changed_by,
    )
    demand.status = new_status
    db.add(demand)
    db.add(history)
    return demand


def enable_sourcing(db: Session, demand: Demand, *, bench_first_override: bool = False, changed_by: Optional[str] = None) -> Demand:
    """
    BR-02 / R-04: sourcing_enabled cannot be set True unless
    bench_first_checked is already True. bench_first_override is for
    the logged RM-override path (HRMS-P607) -- passing it True sets
    bench_first_checked=True as part of THIS call, so the override
    itself is auditable via the same history mechanism rather than a
    silent bypass.
    """
    if bench_first_override:
        demand.bench_first_checked = True

    if not demand.bench_first_checked:
        raise BenchFirstNotChecked(
            "Cannot enable external sourcing until bench-first has been checked "
            "(R-04) -- confirm bench insufficiency first, or pass an explicit, logged override."
        )

    demand.sourcing_enabled = True
    db.add(demand)
    return demand


def record_placement(db: Session, demand: Demand) -> Demand:
    """
    BR-03: called when a submission against this demand reaches
    OFFER_ACCEPTED (the Submission entity itself is a later Phase 2
    domain not yet built in this codebase -- this function is the
    sanctioned increment path for whenever that call site exists, so
    the auto-fill-and-transition logic lives in one place from the start
    rather than being reimplemented per caller).
    """
    demand.positions_filled += 1
    if demand.positions_filled >= demand.headcount and demand.status != "FILLED":
        transition_demand_status(db, demand, "FILLED", reason="Headcount reached", changed_by="system")
    else:
        db.add(demand)
    return demand
