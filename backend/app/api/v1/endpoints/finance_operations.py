from app.core.logging import logger
"""EPIC-16 Finance Operations endpoints: bank reconciliation, AR aging, invoice details."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.database import get_db
from app.models.user import Users
from app.services.finance_operations_service import (
    get_bank_reconciliation_summary,
    get_ar_aging_breakdown,
    get_invoice_detail_drill_down
)

import logging

router = APIRouter(prefix="/finance-operations", tags=["Finance Operations"])

@router.get("/bank-reconciliation", dependencies=[Depends(require_resource_permission("revenue", "view"))])
def get_bank_reconciliation(
    as_of_date: str = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get bank reconciliation summary (revenue.view_pnl gated)."""
    try:
        summary = get_bank_reconciliation_summary(db, as_of_date)
        return {"status": "success", "data": summary}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ar-aging", dependencies=[Depends(require_resource_permission("revenue", "view"))])
def get_ar_aging(
    as_of_date: str = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get AR aging breakdown by time bucket (revenue.view_pnl gated)."""
    try:
        aging = get_ar_aging_breakdown(db, as_of_date)
        return {"status": "success", "data": aging}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/invoices/{invoice_id}/detail", dependencies=[Depends(require_resource_permission("revenue", "view"))])
def get_invoice_detail(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get complete invoice detail for drill-down panel (revenue.view_pnl gated)."""
    try:
        detail = get_invoice_detail_drill_down(db, invoice_id)
        if "error" in detail:
            raise HTTPException(status_code=404, detail=detail["error"])
        return {"status": "success", "data": detail}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
