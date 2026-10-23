"""
EPIC-16 -- Fully Loaded Cost + Blended Delivery Rate. See
app.models.cost_rate_config for the config-driven design rationale.
"""
from datetime import date
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.cost_rate_config import CostRateConfig
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.timesheet import Timesheet
from app.services.forecast_variance_service import get_monthly_actual_revenue

logger = logging.getLogger(__name__)

class CostRateConfigError(Exception):
    pass

def set_cost_rate_config(
    db: Session, *, statutory_pct: float, overhead_pct: float, created_by: str,
    business_unit_id: Optional[int] = None, tenant_id: Optional[int] = None,
    effective_date: Optional[date] = None, notes: Optional[str] = None, country: Optional[str] = None,
) -> CostRateConfig:
    """A new rate for one cost object (BU x country; either may be None = every one). Append-only:
    a later row with a later effective date replaces it from that date, earlier days keep theirs."""
    if statutory_pct < 0 or overhead_pct < 0:
        raise CostRateConfigError("statutory_pct and overhead_pct must both be non-negative.")
    if country is not None:
        from app.services.employment_type_policy import country_code

        code = country_code(country)
        if code is None:
            raise CostRateConfigError(f"Country {country!r} is not one we operate in (use an ISO code such as IN or US).")
        country = code
    config = CostRateConfig(
        tenant_id=tenant_id, business_unit_id=business_unit_id, country=country,
        statutory_pct=statutory_pct, overhead_pct=overhead_pct,
        effective_date=effective_date or date.today(), created_by=created_by, notes=notes,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config

def get_active_cost_rate_config(db: Session, *, business_unit_id: Optional[int] = None,
                                country: Optional[str] = None, on: Optional[date] = None) -> Optional[CostRateConfig]:
    """The rate for a cost object on a day: BU+country, else the country default, else the BU
    default, else the tenant default -- the latest row effective on or before `on` (today by
    default) at the first level that has one; for a day before any rate took effect, the first rate
    set. None when no level has a rate: the cost is then reported missing, never guessed."""
    on = on or date.today()
    levels = []
    if business_unit_id is not None and country is not None:
        levels.append((business_unit_id, country))
    if country is not None:
        levels.append((None, country))
    if business_unit_id is not None:
        levels.append((business_unit_id, None))
    levels.append((None, None))
    def at(bu_id, code):
        query = db.query(CostRateConfig)
        query = query.filter(CostRateConfig.business_unit_id.is_(None) if bu_id is None
                             else CostRateConfig.business_unit_id == bu_id)
        return query.filter(CostRateConfig.country.is_(None) if code is None else CostRateConfig.country == code)

    for bu_id, code in levels:
        row = at(bu_id, code).filter(CostRateConfig.effective_date <= on) \
            .order_by(CostRateConfig.effective_date.desc(), CostRateConfig.id.desc()).first()
        if row is not None:
            return row
    # a day before any rate took effect: the first rate set is the best known one (rates were
    # configured after the fact), at the most specific level that has any
    for bu_id, code in levels:
        row = at(bu_id, code).order_by(CostRateConfig.effective_date.asc(), CostRateConfig.id.asc()).first()
        if row is not None:
            return row
    return None

def calculate_fully_loaded_cost_usd_cents(employee: Employee, config: CostRateConfig) -> Optional[int]:
    """Monthly fully-loaded cost = base salary + statutory components +
    admin overhead allocation, matching the real workbook's Roster
    formula shape. None (not a fake 0) when the employee has no salary
    on file -- consistent with this codebase's established
    INSUFFICIENT_DATA posture elsewhere (e.g. Project revenue estimate)."""
    if employee.base_salary_usd_cents is None:
        return None
    base = employee.base_salary_usd_cents
    statutory = round(base * float(config.statutory_pct) / 100)
    overhead = round(base * float(config.overhead_pct) / 100)
    return base + statutory + overhead

def calculate_blended_delivery_rate(
    db: Session, *, business_unit_id: int, year: int, month: int,
) -> Optional[float]:
    """Blended delivery rate = actual revenue billed for the BU in the
    period / total approved billable hours delivered in the same
    period -- a real, derived $/hour figure, not a per-employee rate
    card. None when there are no approved billable hours to divide by."""
    client_ids = [c.id for c in db.query(Client.id).filter(Client.business_unit_id == business_unit_id).all()]
    if not client_ids:
        return None

    revenue_usd_cents = get_monthly_actual_revenue(db, client_ids=client_ids, year=year, month=month)

    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    total_hours = (
        db.query(Timesheet)
        .join(EmployeeAllocation, Timesheet.allocation_id == EmployeeAllocation.id)
        .filter(
            EmployeeAllocation.client_id.in_(client_ids),
            Timesheet.status == "APPROVED",
            Timesheet.week_starting_date >= start, Timesheet.week_starting_date < end,
        )
        .with_entities(Timesheet.billable_hours)
        .all()
    )
    total_billable_hours = sum(float(h[0]) for h in total_hours)
    if total_billable_hours <= 0:
        return None
    return round(revenue_usd_cents / total_billable_hours, 2)
