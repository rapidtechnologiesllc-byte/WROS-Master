"""
EPIC-16 Fully Loaded Cost + Blended Delivery Rate. Gated at
revenue.view_pnl -- cost/margin figures are the same P&L-adjacent tier
as markup_rate_pct and revenue leakage detail elsewhere.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.models.employee import Employee
from app.models.user import Users
from app.schemas.cost_rate import (
    BlendedDeliveryRateResponse, CostRateConfigResponse, FullyLoadedCostResponse, SetCostRateConfigRequest,
)
from app.schemas.bank_reconciliation import (
    BankTransactionResponse, MatchTransactionRequest, RecordBankTransactionRequest, UnmatchedPaidInvoiceResponse,
)
from app.schemas.hiring_affordability import HiringAffordabilityResponse
from app.schemas.intercompany_ledger import (
    CompanyNetPositionResponse, IntercompanySettlementResponse, LinkSettlementCompaniesRequest,
    RecordIntercompanySettlementRequest,
)
from app.schemas.pnl import BuPnlResponse, OrgPnlSummaryResponse
from app.schemas.reserve_fund import (
    RecordReserveFundEntryRequest, ReserveFundEntryResponse, ReserveFundStatusResponse,
)
from app.services.cost_rate_service import (
    CostRateConfigError, calculate_blended_delivery_rate, calculate_fully_loaded_cost_usd_cents,
    get_active_cost_rate_config, set_cost_rate_config,
)
from app.models.invoice import Invoice
from app.services.bank_reconciliation_service import (
    BankReconciliationError, get_unmatched_paid_invoices, get_unreconciled_transactions,
    match_transaction_to_invoice, record_bank_transaction,
)
from app.services.hiring_affordability_service import check_hiring_affordability
from app.services.intercompany_ledger_service import (
    IntercompanySettlementError, get_company_net_position, link_settlement_companies, list_settlements,
    record_intercompany_settlement,
)
from app.services.pnl_service import get_bu_pnl, get_org_pnl_summary
from app.services.reserve_fund_service import (
    ReserveFundError, get_reserve_fund_status, record_reserve_fund_entry,
)

router = APIRouter(tags=["cost-rate"])

@router.post(
    "/cost-rate-configs",
    response_model=CostRateConfigResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("finance-operations", "create"))]
)
def create_cost_rate_config(
    body: SetCostRateConfigRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
):
    try:
        return set_cost_rate_config(
            db, statutory_pct=body.statutory_pct, overhead_pct=body.overhead_pct,
            created_by=current_user.UserID, business_unit_id=body.business_unit_id,
            tenant_id=current_user.tenant_id, effective_date=body.effective_date, notes=body.notes,
            country=body.country,
        )
    except CostRateConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/cost-rate-configs/countries",
    dependencies=[Depends(require_resource_permission("finance-operations", "view"))]
)
def cost_rate_countries():
    """The locations a rate can be set for (the configured countries, ISO codes)."""
    from app.services import employment_type_policy

    return {"countries": [{"code": c["code"], "name": c["name"]} for c in employment_type_policy.describe()["countries"]]}


@router.get(
    "/cost-rate-configs",
    response_model=list[CostRateConfigResponse],
    dependencies=[Depends(require_resource_permission("finance-operations", "view"))]
)
def list_cost_rate_configs(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
):
    """Every rate set, newest first: per BU x country, country defaults, BU defaults, tenant default."""
    from app.models.cost_rate_config import CostRateConfig

    return (db.query(CostRateConfig)
            .filter((CostRateConfig.tenant_id == current_user.tenant_id) | (CostRateConfig.tenant_id.is_(None)))
            .order_by(CostRateConfig.effective_date.desc(), CostRateConfig.id.desc()).all())

@router.get(
    "/employees/{employee_id}/fully-loaded-cost",
    response_model=FullyLoadedCostResponse,
    dependencies=[Depends(require_resource_permission("finance-operations", "view"))]
)
def fully_loaded_cost(
    employee_id: str, business_unit_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
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

@router.get(
    "/blended-delivery-rate/bu/{business_unit_id}",
    response_model=BlendedDeliveryRateResponse,
    dependencies=[Depends(require_resource_permission("finance-operations", "view"))]
)
def blended_delivery_rate(
    business_unit_id: int, year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
):
    rate = calculate_blended_delivery_rate(db, business_unit_id=business_unit_id, year=year, month=month)
    return BlendedDeliveryRateResponse(
        business_unit_id=business_unit_id, year=year, month=month,
        blended_delivery_rate_usd_cents_per_hour=rate,
    )

@router.get(
    "/pnl/bu/{business_unit_id}",
    response_model=BuPnlResponse,
    dependencies=[Depends(require_resource_permission("finance-operations", "view"))]
)
def bu_pnl(
    business_unit_id: int, year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
):
    return get_bu_pnl(db, business_unit_id=business_unit_id, year=year, month=month)


@router.post(
    "/reserve-fund/entries",
    response_model=ReserveFundEntryResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("finance-operations", "create"))]
)
def create_reserve_fund_entry(
    body: RecordReserveFundEntryRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
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

@router.get(
    "/reserve-fund/bu/{business_unit_id}/status",
    response_model=ReserveFundStatusResponse,
    dependencies=[Depends(require_resource_permission("finance-operations", "view"))]
)
def reserve_fund_status(
    business_unit_id: int, year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
):
    return get_reserve_fund_status(db, business_unit_id=business_unit_id, as_of_year=year, as_of_month=month)

@router.get(
    "/hiring-affordability/bu/{business_unit_id}",
    response_model=HiringAffordabilityResponse,
    dependencies=[Depends(require_resource_permission("finance-operations", "view"))]
)
def hiring_affordability(
    business_unit_id: int, proposed_annual_salary_usd_cents: int, year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
):
    return check_hiring_affordability(
        db, business_unit_id=business_unit_id,
        proposed_annual_salary_usd_cents=proposed_annual_salary_usd_cents, year=year, month=month,
    )

@router.post(
    "/intercompany-settlements",
    response_model=IntercompanySettlementResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("finance-operations", "create"))]
)
def create_intercompany_settlement(
    body: RecordIntercompanySettlementRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
):
    try:
        return record_intercompany_settlement(
            db, from_company_id=body.from_company_id, to_company_id=body.to_company_id,
            amount_usd_cents=body.amount_usd_cents,
            settlement_date=body.settlement_date, reason=body.reason,
            created_by=current_user.UserID, tenant_id=current_user.tenant_id,
            business_unit_id=body.business_unit_id,
        )
    except IntercompanySettlementError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get(
    "/intercompany-settlements",
    response_model=list[IntercompanySettlementResponse],
    dependencies=[Depends(require_resource_permission("finance-operations", "view"))]
)
def list_intercompany_settlements(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
):
    return list_settlements(db, tenant_id=current_user.tenant_id)

@router.post(
    "/intercompany-settlements/{settlement_id}/link-companies",
    response_model=IntercompanySettlementResponse,
    dependencies=[Depends(require_resource_permission("finance-operations", "edit"))]
)
def link_intercompany_settlement(
    settlement_id: int,
    body: LinkSettlementCompaniesRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
):
    """Link an old settlement whose free-text company name matched no company."""
    from app.models.intercompany_ledger import IntercompanySettlement

    settlement = db.query(IntercompanySettlement).filter(
        IntercompanySettlement.id == settlement_id, IntercompanySettlement.tenant_id == current_user.tenant_id).first()
    if settlement is None:
        raise HTTPException(status_code=404, detail="Settlement not found.")
    try:
        return link_settlement_companies(db, settlement, from_company_id=body.from_company_id,
                                         to_company_id=body.to_company_id)
    except IntercompanySettlementError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get(
    "/intercompany-settlements/company/{company_id}/net-position",
    response_model=CompanyNetPositionResponse,
    dependencies=[Depends(require_resource_permission("finance-operations", "view"))]
)
def company_net_position(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
):
    from app.models.location import Location

    try:
        net = get_company_net_position(db, company_id=company_id, tenant_id=current_user.tenant_id)
    except IntercompanySettlementError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    name = db.query(Location.name).filter(Location.id == company_id).scalar()
    return CompanyNetPositionResponse(company_id=company_id, entity=name, net_position_usd_cents=net)

@router.post(
    "/bank-transactions",
    response_model=BankTransactionResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("finance-operations", "create"))]
)
def create_bank_transaction(
    body: RecordBankTransactionRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
):
    try:
        return record_bank_transaction(
            db, transaction_date=body.transaction_date, amount_usd_cents=body.amount_usd_cents,
            description=body.description, created_by=current_user.UserID, tenant_id=current_user.tenant_id,
        )
    except BankReconciliationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))



@router.post(
    "/bank-transactions/{transaction_id}/match",
    response_model=BankTransactionResponse,
    dependencies=[Depends(require_resource_permission("finance-operations", "create"))]
)
def match_bank_transaction(
    transaction_id: int,
    body: MatchTransactionRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
):
    """Match a recorded bank credit to an invoice; a SENT invoice becomes PAID on that date."""
    from app.models.bank_reconciliation import BankTransaction

    transaction = db.query(BankTransaction).filter(BankTransaction.id == transaction_id,
                                                   BankTransaction.tenant_id == current_user.tenant_id).first()
    invoice = db.query(Invoice).filter(Invoice.id == body.invoice_id, Invoice.tenant_id == current_user.tenant_id).first()
    if transaction is None or invoice is None:
        raise HTTPException(status_code=404, detail="Bank transaction or invoice not found.")
    try:
        return match_transaction_to_invoice(db, transaction, invoice)
    except BankReconciliationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))


@router.get(
    "/bank-transactions/unreconciled",
    response_model=list[BankTransactionResponse],
    dependencies=[Depends(require_resource_permission("finance-operations", "view"))]
)
def list_unreconciled_transactions(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
):
    return get_unreconciled_transactions(db, tenant_id=current_user.tenant_id)


@router.get(
    "/bank-transactions/unmatched-paid-invoices",
    response_model=list[UnmatchedPaidInvoiceResponse],
    dependencies=[Depends(require_resource_permission("finance-operations", "view"))]
)
def list_unmatched_paid_invoices(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
):
    return [UnmatchedPaidInvoiceResponse(invoice_id=i.id, client_id=i.client_id, total_usd_cents=i.total_usd_cents)
            for i in get_unmatched_paid_invoices(db, tenant_id=current_user.tenant_id)]


@router.get(
    "/pnl/org",
    response_model=OrgPnlSummaryResponse,
    dependencies=[Depends(require_resource_permission("finance-operations", "view"))]
)
def org_pnl(
    year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("finance-operations", "view")),
):
    return get_org_pnl_summary(db, year=year, month=month, tenant_id=current_user.tenant_id)
