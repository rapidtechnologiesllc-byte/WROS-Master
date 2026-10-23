"""
Revenue chain -- candidate -> job -> project -> timesheet -> invoice -> P&L
=========================================================================
Prefix: /revenue-chain

All figures come from app.services.revenue_chain_service, the same
calculation the BU/org P&L (pnl_service) and the CFO/CEO/Flash views read.
Amounts are USD cents. Periods are by timesheet week (start and end
inclusive, at most 366 days).

Routes:
  GET /revenue-chain/lines     One row per timesheet, traced end to end.
  GET /revenue-chain/summary   The same lines rolled up by employee, candidate,
                               job, project, client, business_unit or partner.
  GET /revenue-chain/pnl       Org P&L with every partner, business unit and client.

Every route shows only the business units the caller may see (app.core.data_scope);
org-level role templates see the whole firm.
"""
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.data_scope import visible_bu_ids
from app.core.dependencies import require_role_template_permission
from app.models.user import Users
from app.services import revenue_chain_service as chain

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/revenue-chain", tags=["revenue-chain"])

MAX_PERIOD_DAYS = 366


def _period(start: date, end: date):
    if end < start:
        raise HTTPException(status_code=422, detail="end must be on or after start.")
    if (end - start).days > MAX_PERIOD_DAYS:
        raise HTTPException(status_code=422, detail=f"Period can be at most {MAX_PERIOD_DAYS} days.")


@router.get("/lines", summary="Every timesheet traced from candidate to cash")
def revenue_chain_lines(
    start: date, end: date,
    client_id: Optional[str] = None, partner_user_id: Optional[str] = None, employee_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_role_template_permission("revenue", "view")),
):
    _period(start, end)
    lines = chain.chain_lines(db, start=start, end=end, tenant_id=current_user.tenant_id, client_id=client_id,
                              partner_user_id=partner_user_id, employee_id=employee_id,
                              business_unit_ids=visible_bu_ids(db, current_user))
    return {"start": start, "end": end, "count": len(lines), "lines": lines}


@router.get("/summary", summary="Revenue, cost and margin rolled up by one dimension")
def revenue_chain_summary(
    start: date, end: date,
    group_by: str = Query("partner", pattern="^(" + "|".join(chain.GROUPS) + ")$"),
    partner_user_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_role_template_permission("revenue", "view")),
):
    _period(start, end)
    lines = chain.chain_lines(db, start=start, end=end, tenant_id=current_user.tenant_id,
                              partner_user_id=partner_user_id, business_unit_ids=visible_bu_ids(db, current_user))
    return {"start": start, "end": end, "group_by": group_by, "rows": chain.summarize(lines, group_by)}


@router.get("/pnl", summary="Org P&L with partner, business unit, location, cost object and client breakdowns")
def revenue_chain_pnl(
    start: date, end: date,
    country: Optional[str] = Query(None, min_length=2, max_length=2, description="ISO country: one location's P&L"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_role_template_permission("revenue", "view")),
):
    _period(start, end)
    return chain.pnl(db, start=start, end=end, tenant_id=current_user.tenant_id,
                     business_unit_ids=visible_bu_ids(db, current_user),
                     country=country.upper() if country else None)
