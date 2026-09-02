"""
S-243 (EPIC-02 Revenue Leakage Detection). See app.models.pipeline_leakage
for the 4-pattern design and why sub-vendor cost overruns aren't built.
"""
from datetime import datetime, timedelta
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.demand import Demand
from app.models.opportunity import CLOSED_STAGES, Opportunity
from app.models.pipeline_leakage import PipelineLeakageFlag
from app.models.project import Project
from app.services import revenue_leakage_service

DEFAULT_STALLED_OPPORTUNITY_DAYS = 30
DEFAULT_UNFILLED_DEMAND_GRACE_DAYS = 0  # flags the moment required_start_date has passed


def _get_or_create(db: Session, *, pattern_type: str, match_filters: dict, **fields) -> PipelineLeakageFlag:
    """One open (unresolved) flag per pattern_type+source entity --
    re-scanning refreshes the existing row's detail/impact rather than
    creating duplicates."""
    existing = (
        db.query(PipelineLeakageFlag)
        .filter_by(pattern_type=pattern_type, resolved_at=None, **match_filters)
        .first()
    )
    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
        db.add(existing)
        return existing
    flag = PipelineLeakageFlag(pattern_type=pattern_type, **match_filters, **fields)
    db.add(flag)
    return flag


def scan_stalled_opportunities(
    db: Session, *, stale_days: int = DEFAULT_STALLED_OPPORTUNITY_DAYS, now: Optional[datetime] = None,
) -> List[PipelineLeakageFlag]:
    """An open opportunity with no stage movement (updated_at) in
    stale_days is a stalled-pipeline leakage signal -- money the
    forecast counts that isn't actually moving toward close."""
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=stale_days)

    query = (
        db.query(Opportunity, Client.business_unit_id)
        .outerjoin(Client, Client.id == Opportunity.client_id)
        .filter(Opportunity.stage.notin_(CLOSED_STAGES), Opportunity.updated_at <= cutoff)
    )
    flags = []
    for opp, bu_id in query.all():
        flag = _get_or_create(
            db, pattern_type="STALLED_OPPORTUNITY", match_filters={"opportunity_id": opp.id},
            tenant_id=opp.tenant_id, business_unit_id=bu_id,
            estimated_impact_usd_cents=opp.revenue_value_usd_cents,
            detail=f"No stage movement since {opp.updated_at.isoformat() if opp.updated_at else 'unknown'} (stage={opp.stage}).",
        )
        flags.append(flag)
    return flags


def scan_unfilled_demand(
    db: Session, *, grace_days: int = DEFAULT_UNFILLED_DEMAND_GRACE_DAYS, now: Optional[datetime] = None,
) -> List[PipelineLeakageFlag]:
    """A Demand past its required_start_date with positions still open
    is revenue the pipeline counted that isn't being delivered (and,
    since Invoice is timesheet-driven, isn't billing either)."""
    now = now or datetime.utcnow()
    cutoff_date = (now - timedelta(days=grace_days)).date()

    query = db.query(Demand).filter(
        Demand.status.in_(("OPEN", "IN_PROGRESS")),
        Demand.required_start_date.isnot(None),
        Demand.required_start_date <= cutoff_date,
        Demand.positions_filled < Demand.headcount,
    )
    flags = []
    for demand in query.all():
        open_positions = demand.headcount - demand.positions_filled
        impact = None
        if demand.revenue_potential_usd_cents is not None and demand.headcount:
            impact = round(demand.revenue_potential_usd_cents * open_positions / demand.headcount)
        flag = _get_or_create(
            db, pattern_type="UNFILLED_DEMAND", match_filters={"demand_id": demand.id},
            tenant_id=demand.tenant_id, business_unit_id=demand.assigned_bu_id,
            estimated_impact_usd_cents=impact,
            detail=(
                f"{open_positions}/{demand.headcount} position(s) still open, "
                f"past required start date {demand.required_start_date.isoformat()}."
            ),
        )
        flags.append(flag)
    return flags


def scan_unbilled_time(db: Session, *, tenant_id: Optional[int] = None) -> List[PipelineLeakageFlag]:
    """Reuses revenue_leakage_service's already-shipped HRMS-0906 check
    (BR-0906-01: one shared detection source) rather than reimplementing
    unbilled-hours detection -- wraps each active flag as a
    PipelineLeakageFlag so it surfaces in the same EPIC-02 leakage list."""
    existing_flags = revenue_leakage_service.get_active_leakage_flags(db, tenant_id=tenant_id)
    flags = []
    for rlf in existing_flags:
        bu_id = None
        project = db.query(Project).filter(Project.id == rlf.project_id).first()
        if project is not None:
            client = db.query(Client).filter(Client.id == project.client_id).first()
            bu_id = client.business_unit_id if client else None
        flag = _get_or_create(
            db, pattern_type="UNBILLED_TIME", match_filters={"revenue_leakage_flag_id": rlf.id},
            tenant_id=rlf.tenant_id, business_unit_id=bu_id,
            detail=(
                f"{rlf.unbilled_hours} unbilled hour(s) on project {rlf.project_id} "
                f"for period {rlf.period_start}-{rlf.period_end}."
            ),
        )
        flags.append(flag)
    return flags


def scan_subvendor_cost_overruns(db: Session) -> List[PipelineLeakageFlag]:
    """NOT BUILT -- see app.models.pipeline_leakage's module docstring.
    No cost/budget/rate field exists anywhere in the Sub-Vendor Portal
    domain to compare an actual placement cost against. Real function
    with a real signature, deliberately returns nothing rather than a
    fabricated comparison -- surfaced as a flagged gap, not silently
    omitted from the pattern list."""
    return []


def scan_all_leakage(db: Session, *, tenant_id: Optional[int] = None) -> List[PipelineLeakageFlag]:
    flags: List[PipelineLeakageFlag] = []
    flags += scan_stalled_opportunities(db)
    flags += scan_unfilled_demand(db)
    flags += scan_unbilled_time(db, tenant_id=tenant_id)
    flags += scan_subvendor_cost_overruns(db)
    return flags


def get_active_leakage_flags(
    db: Session, *, business_unit_ids: Optional[List[int]] = None, tenant_id: Optional[int] = None,
) -> List[PipelineLeakageFlag]:
    query = db.query(PipelineLeakageFlag).filter(PipelineLeakageFlag.resolved_at.is_(None))
    if tenant_id is not None:
        query = query.filter(PipelineLeakageFlag.tenant_id == tenant_id)
    if business_unit_ids is not None:
        query = query.filter(PipelineLeakageFlag.business_unit_id.in_(business_unit_ids))
    return query.order_by(PipelineLeakageFlag.detected_at.desc()).all()


def resolve_leakage_flag(db: Session, flag: PipelineLeakageFlag, *, resolution_note: Optional[str] = None) -> PipelineLeakageFlag:
    flag.resolved_at = datetime.utcnow()
    flag.resolution_note = resolution_note
    db.add(flag)
    return flag
