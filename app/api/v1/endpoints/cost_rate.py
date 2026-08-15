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
from app.core.visibility import should_bypass_bu_filter, get_user_bu_id
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
    EntityNetPositionResponse, IntercompanySettlementResponse, RecordIntercompanySettlementRequest,
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
    IntercompanySettlementError, get_entity_net_position, list_settlements, record_intercompany_settlement,
)
from app.services.pnl_service import get_bu_pnl, get_org_pnl_summary
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


@router.get("/pnl/org-summary", response_model=OrgPnlSummaryResponse, summary="EPIC-16 Executive Dashboard: org-wide P&L rollup across all Business Units")
def org_pnl_summary(
    year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    return get_org_pnl_summary(db, year=year, month=month, tenant_id=current_user.tenant_id)


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


@router.post("/intercompany-settlements", response_model=IntercompanySettlementResponse, status_code=201)
def create_intercompany_settlement(
    body: RecordIntercompanySettlementRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    try:
        return record_intercompany_settlement(
            db, from_entity=body.from_entity, to_entity=body.to_entity, amount_usd_cents=body.amount_usd_cents,
            settlement_date=body.settlement_date, reason=body.reason,
            created_by=current_user.UserID, tenant_id=current_user.tenant_id,
        )
    except IntercompanySettlementError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/intercompany-settlements", response_model=list[IntercompanySettlementResponse])
def list_intercompany_settlements(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    return list_settlements(db, tenant_id=current_user.tenant_id)


@router.get("/intercompany-settlements/entity/{entity}/net-position", response_model=EntityNetPositionResponse)
def entity_net_position(
    entity: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    return EntityNetPositionResponse(
        entity=entity, net_position_usd_cents=get_entity_net_position(db, entity=entity, tenant_id=current_user.tenant_id),
    )


@router.post("/bank-transactions", response_model=BankTransactionResponse, status_code=201)
def create_bank_transaction(
    body: RecordBankTransactionRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    try:
        return record_bank_transaction(
            db, transaction_date=body.transaction_date, amount_usd_cents=body.amount_usd_cents,
            description=body.description, created_by=current_user.UserID, tenant_id=current_user.tenant_id,
        )
    except BankReconciliationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/bank-transactions/{transaction_id}/match", response_model=BankTransactionResponse)
def match_bank_transaction(
    transaction_id: int, body: MatchTransactionRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    from app.models.bank_reconciliation import BankTransaction

    transaction = db.query(BankTransaction).filter(BankTransaction.id == transaction_id).first()
    if transaction is None:
        raise HTTPException(status_code=404, detail=f"Bank transaction {transaction_id} not found.")
    invoice = db.query(Invoice).filter(Invoice.id == body.invoice_id).first()
    if invoice is None:
        raise HTTPException(status_code=404, detail=f"Invoice {body.invoice_id!r} not found.")
    try:
        return match_transaction_to_invoice(db, transaction, invoice)
    except BankReconciliationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/bank-transactions/unreconciled", response_model=list[BankTransactionResponse])
def unreconciled_bank_transactions(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    return get_unreconciled_transactions(db, tenant_id=current_user.tenant_id)


@router.get("/invoices/unmatched-paid", response_model=list[UnmatchedPaidInvoiceResponse])
def unmatched_paid_invoices(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    return [
        UnmatchedPaidInvoiceResponse(invoice_id=inv.id, client_id=inv.client_id, total_usd_cents=inv.total_usd_cents)
        for inv in get_unmatched_paid_invoices(db, tenant_id=current_user.tenant_id)
    ]
