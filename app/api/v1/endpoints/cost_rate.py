"""
EPIC-16 Fully Loaded Cost + Blended Delivery Rate. Gated at
revenue.view_pnl -- cost/margin figures are the same P&L-adjacent tier
as markup_rate_pct and revenue leakage detail elsewhere.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models.employee import Employee
from app.models.user import Users
from app.schemas.cost_rate import (
    BlendedDeliveryRateResponse, CostRateConfigResponse, FullyLoadedCostResponse, SetCostRateConfigRequest,
)
from app.schemas.hiring_affordability import HiringAffordabilityResponse
from app.schemas.pnl import BuPnlResponse
from app.schemas.reserve_fund import (
    RecordReserveFundEntryRequest, ReserveFundEntryResponse, ReserveFundStatusResponse,
)
from app.services.cost_rate_service import (
    CostRateConfigError, calculate_blended_delivery_rate, calculate_fully_loaded_cost_usd_cents,
    get_active_cost_rate_config, set_cost_rate_config,
)
from app.services.hiring_affordability_service import check_hiring_affordability
from app.services.pnl_service import get_bu_pnl
from app.services.reserve_fund_service import (
    ReserveFundError, get_reserve_fund_status, record_reserve_fund_entry,
)

router = APIRouter(tags=["cost-rate"])


@router.post("/cost-rate-configs", response_model=CostRateConfigResponse, status_code=201)
def create_cost_rate_config(
    body: SetCostRateConfigRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    try:
        return set_cost_rate_config(
            db, statutory_pct=body.statutory_pct, overhead_pct=body.overhead_pct,
            created_by=current_user.UserID, business_unit_id=body.business_unit_id,
            tenant_id=current_user.tenant_id, effective_date=body.effective_date, notes=body.notes,
        )
    except CostRateConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/employees/{employee_id}/fully-loaded-cost", response_model=FullyLoadedCostResponse)
def fully_loaded_cost(
    employee_id: str, business_unit_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id!r} not found.")
    config = get_active_cost_rate_config(db, business_unit_id=business_unit_id)
    if config is None:
        raise HTTPException(status_code=400, detail="No cost-rate config exists yet -- set one first.")
    cost = calculate_fully_loaded_cost_usd_cents(employee, config)
    return FullyLoadedCostResponse(
        employee_id=employee.id, base_salary_usd_cents=employee.base_salary_usd_cents,
        fully_loaded_cost_usd_cents=cost,
    )


@router.get("/blended-delivery-rate/bu/{business_unit_id}", response_model=BlendedDeliveryRateResponse)
def blended_delivery_rate(
    business_unit_id: int, year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    rate = calculate_blended_delivery_rate(db, business_unit_id=business_unit_id, year=year, month=month)
    return BlendedDeliveryRateResponse(
        business_unit_id=business_unit_id, year=year, month=month,
        blended_delivery_rate_usd_cents_per_hour=rate,
    )


@router.get("/pnl/bu/{business_unit_id}", response_model=BuPnlResponse)
def bu_pnl(
    business_unit_id: int, year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    return get_bu_pnl(db, business_unit_id=business_unit_id, year=year, month=month)


@router.post("/reserve-fund/entries", response_model=ReserveFundEntryResponse, status_code=201)
def create_reserve_fund_entry(
    body: RecordReserveFundEntryRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    try:
        return record_reserve_fund_entry(
            db, entry_type=body.entry_type, amount_usd_cents=body.amount_usd_cents,
            period_year=body.period_year, period_month=body.period_month,
            created_by=current_user.UserID, business_unit_id=body.business_unit_id,
            tenant_id=current_user.tenant_id, notes=body.notes,
        )
    except ReserveFundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/reserve-fund/bu/{business_unit_id}/status", response_model=ReserveFundStatusResponse)
def reserve_fund_status(
    business_unit_id: int, year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    return get_reserve_fund_status(db, business_unit_id=business_unit_id, as_of_year=year, as_of_month=month)


@router.get("/hiring-affordability/bu/{business_unit_id}", response_model=HiringAffordabilityResponse)
def hiring_affordability(
    business_unit_id: int, proposed_annual_salary_usd_cents: int, year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    return check_hiring_affordability(
        db, business_unit_id=business_unit_id,
        proposed_annual_salary_usd_cents=proposed_annual_salary_usd_cents, year=year, month=month,
    )
