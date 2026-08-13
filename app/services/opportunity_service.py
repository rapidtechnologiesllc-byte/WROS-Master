"""
HRMS-0207 (Create Opportunity), HRMS-0209 (Forecast Calculation),
HRMS-0215 (Pipeline Coverage Ratio).

calculate_weighted_forecast() is deliberately the ONE shared function
per HRMS-0209's BR-0209-01 -- every consuming dashboard (HRMS-0212
Executive Revenue Dashboard, HRMS-0213 Forecast vs Actual, HRMS-0215
Pipeline Coverage) is specified to call this rather than recalculate
independently. Those three dashboards themselves are UI/reporting
screens not built in this pass (consistent with every other Phase 2
entity this session -- no REST endpoints/UI yet for anything), but this
underlying calculation is real and tested so whichever screen gets
built later has one correct source to call.

Stage transition to WON auto-creates a Project (HRMS-0801 BR-0801-01,
completing the hook this module's own docstring used to defer -- Project
now exists as of the Projects build round).
"""
from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.demand import Demand
from app.models.opportunity import CLOSED_STAGES, OPPORTUNITY_STAGES, Opportunity
from app.services.demand_service import create_demand
from app.services.project_service import create_project_from_won_opportunity


class OpportunityValidationError(Exception):
    pass


class InvalidStageTransition(Exception):
    pass


# 2026-08-12, Avinash: win probability must be system-generated, never a
# free-text field a user types a number into. Stage-based default is the
# interim mechanism; long term this is meant to be replaced by live
# HubSpot pipeline data (Avinash's stated "most important feature" for
# a future session) once that integration exists -- this map is the
# placeholder single source of truth until then, not a permanent design.
STAGE_PROBABILITY = {
    "QUALIFICATION": 10,
    "PROSPECT": 25,
    "PROPOSAL": 50,
    "NEGOTIATION": 75,
    "CONTRACT": 90,
    "ACTIVE": 100,
    "LOST": 0,
}


def default_probability_for_stage(stage: str) -> int:
    return STAGE_PROBABILITY.get(stage, 0)


def create_opportunity(
    db: Session,
    *,
    tenant_id: Optional[int],
    client_id: str,
    revenue_value_usd_cents: int,
    currency: str = "USD",
    revenue_value_native: Optional[int] = None,
    owner_employee_id: Optional[str] = None,
    client_owner_id: Optional[str] = None,
    expected_close_date=None,
    stage: str = "QUALIFICATION",
) -> Opportunity:
    if revenue_value_usd_cents <= 0:
        raise OpportunityValidationError("revenue_value_usd_cents must be positive.")

    opportunity = Opportunity(
        tenant_id=tenant_id, client_id=client_id, owner_employee_id=owner_employee_id,
        client_owner_id=client_owner_id,
        stage=stage, revenue_value_usd_cents=revenue_value_usd_cents,
        revenue_value_native=revenue_value_native, currency=currency,
        probability_pct=default_probability_for_stage(stage), expected_close_date=expected_close_date,
    )
    db.add(opportunity)
    return opportunity


def _update_client_status_from_opportunities(db: Session, client_id: str) -> None:
    """Auto-sync client status to match its most-advanced opportunity stage.

    Direct 1:1 mapping: Opportunity.stage values == Client.status values
    (QUALIFICATION, PROSPECT, PROPOSAL, NEGOTIATION, CONTRACT, ACTIVE, LOST)

    Precedence: ACTIVE > CONTRACT > NEGOTIATION > PROPOSAL > PROSPECT > QUALIFICATION > LOST
    Client.status reflects the highest-stage opportunity across all linked opportunities.
    """
    STAGE_PRIORITY = {
        "ACTIVE": 7,
        "CONTRACT": 6,
        "NEGOTIATION": 5,
        "PROPOSAL": 4,
        "PROSPECT": 3,
        "QUALIFICATION": 2,
        "LOST": 1,
    }

    # Get highest-priority stage across all opportunities for this client
    opportunities = db.query(Opportunity).filter(Opportunity.client_id == client_id).all()
    if not opportunities:
        return

    highest_stage = max(
        (opp.stage for opp in opportunities if opp.stage in STAGE_PRIORITY),
        key=lambda s: STAGE_PRIORITY.get(s, 0),
        default=None
    )

    if highest_stage:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client and client.status != highest_stage:
            client.status = highest_stage
            db.add(client)


def transition_stage(
    db: Session, opportunity: Opportunity, new_stage: str,
    *, project_name: Optional[str] = None, billing_type: str = "TIME_AND_MATERIALS",
    continent: Optional[str] = None, changed_by: Optional[str] = None,
):
    """
    Returns the Opportunity, unless new_stage='WON', in which case
    returns (opportunity, project) -- HRMS-0801 BR-0801-01: winning an
    opportunity auto-creates a Project inheriting client_id/currency,
    no manual re-entry.

    Also auto-syncs parent Client.status to match the most-advanced
    opportunity stage (WON > NEGOTIATION > PROPOSAL > QUALIFICATION > LOST).
    """
    if opportunity.stage in CLOSED_STAGES:
        raise InvalidStageTransition(
            f"Opportunity {opportunity.id} is already closed ({opportunity.stage}) -- cannot change stage."
        )
    if new_stage not in OPPORTUNITY_STAGES:
        raise InvalidStageTransition(f"'{new_stage}' is not a valid opportunity stage.")

    opportunity.stage = new_stage
    opportunity.probability_pct = default_probability_for_stage(new_stage)
    opportunity.updated_at = datetime.utcnow()
    db.add(opportunity)

    # Auto-sync parent Client status to match opportunity progression
    _update_client_status_from_opportunities(db, opportunity.client_id)

    if new_stage == "WON":
        project = create_project_from_won_opportunity(
            db, opportunity,
            name=project_name or f"Project for Opportunity {opportunity.id}",
            billing_type=billing_type, continent=continent, created_by=changed_by,
        )
        return opportunity, project

    return opportunity


def calculate_weighted_forecast(opportunity: Opportunity) -> int:
    """HRMS-0209 -- the one shared forecast calculation. Returns USD
    cents. weighted_value = revenue_value_usd_cents * (probability_pct / 100)."""
    return round(opportunity.revenue_value_usd_cents * opportunity.probability_pct / 100)


def aggregate_weighted_forecast(opportunities: Iterable[Opportunity]) -> int:
    """Sum of calculate_weighted_forecast() across a set of opportunities
    -- the by-client/by-BU/by-month aggregations HRMS-0209 describes are
    all just this sum applied to a differently-filtered query, so callers
    build that query (by client_id, by owner's BU, by expected_close_date
    month) and pass the resulting list here rather than three separate
    aggregation functions."""
    return sum(calculate_weighted_forecast(o) for o in opportunities)


def calculate_pipeline_coverage_ratio(total_pipeline_value_usd_cents: int, revenue_target_usd_cents: int) -> Optional[float]:
    """HRMS-0215. Returns None (undefined) rather than raising when the
    target is zero, since a zero target is a data problem for the
    caller to notice, not a math error to crash on."""
    if revenue_target_usd_cents <= 0:
        return None
    return total_pipeline_value_usd_cents / revenue_target_usd_cents


def calculate_revenue_potential(demand: Demand) -> Optional[int]:
    """HRMS-0211: bill_rate * duration * quantity, quantity mapping to
    Demand.headcount. Returns None when the inputs aren't all present
    yet rather than silently treating a missing value as zero."""
    if demand.billing_rate_usd_cents is None or demand.duration_hours is None:
        return None
    return demand.billing_rate_usd_cents * demand.duration_hours * demand.headcount


def recalculate_revenue_potential(demand: Demand) -> Demand:
    """HRMS-0211 BR-0211-01: never a stale one-time snapshot -- call
    this after any write to billing_rate_usd_cents, duration_hours, or
    headcount."""
    demand.revenue_potential_usd_cents = calculate_revenue_potential(demand)
    return demand


def create_role_demand_from_opportunity(
    db: Session,
    opportunity: Opportunity,
    *,
    tenant_id: Optional[int],
    job_title: str,
    required_skills: str,
    min_experience_years,
    work_location: str,
    quantity: int,
    duration_hours: int,
    billing_rate_usd_cents: int,
    changed_by: Optional[str] = None,
) -> Demand:
    """
    HRMS-0210 BR-0210-01: opportunity-originated demands use the exact
    same `demands` table and creation path (app.services.demand_service.
    create_demand()) as any other demand -- source_type=OPPORTUNITY is a
    tag, not a parallel schema or a bypassed creation path. `quantity`
    maps to the existing `headcount` field rather than a new column,
    and creating one demand row (not `quantity` duplicate rows) matches
    Demand's own existing headcount/positions_filled model.
    """
    if quantity < 1:
        raise ValueError("quantity must be >= 1.")

    demand = create_demand(
        db,
        tenant_id=tenant_id, client_id=opportunity.client_id,
        job_title=job_title, required_skills=required_skills,
        min_experience_years=min_experience_years, work_location=work_location,
        headcount=quantity, status="DRAFT",
        opportunity_id=opportunity.id, source_type="OPPORTUNITY",
        duration_hours=duration_hours, billing_rate_usd_cents=billing_rate_usd_cents,
        created_by=changed_by,
    )
    recalculate_revenue_potential(demand)
    return demand


def get_opportunity_revenue_rollup(db: Session, opportunity: Opportunity) -> int:
    """Sum of revenue_potential_usd_cents across every demand linked to
    this opportunity -- shown alongside the opportunity's own directly-
    entered revenue_value_usd_cents for comparison (HRMS-0211)."""
    demands: List[Demand] = db.query(Demand).filter(Demand.opportunity_id == opportunity.id).all()
    return sum(d.revenue_potential_usd_cents or 0 for d in demands)
