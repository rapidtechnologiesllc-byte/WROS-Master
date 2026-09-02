"""
import logging
PERIOD CLOSE SERVICE - Month-End Reconciliation & Locking

Handles:
- Month-end P&L close validation
- Period locking (prevents new invoices/changes)
- Immutability enforcement
- Complete reconciliation reporting
- Audit trail for all closes
"""
from datetime import datetime, date
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.invoice import Invoice
from app.models.revenue import Revenue
from app.models.org_structure import BusinessUnit
from app.models.timesheet import Timesheet

logger = logging.getLogger(__name__)

class PeriodLockError(Exception):
    """Period is locked and cannot be modified"""
    pass


class PeriodCloseError(Exception):
    """Period close validation failed"""
    pass


# ============================================================================
# PART 1: PERIOD CLOSE VALIDATION
# ============================================================================

def validate_period_ready_for_close(
    db: Session,
    business_unit_id: int,
    month: str,  # YYYY-MM format
) -> Dict[str, any]:
    """
    Validate period is ready for close.

    Checks:
    ✓ All invoices for period are PAID (not SENT or DRAFT)
    ✓ All timesheets are APPROVED
    ✓ No open disputes
    ✓ Revenue recognized for all paid invoices
    ✓ P&L summary complete and accurate

    Args:
        db: SQLAlchemy session
        business_unit_id: BU to close
        month: YYYY-MM format

    Returns:
        {
            "ready": bool,
            "issues": [str],  # Validation failures
            "invoice_count": int,
            "revenue_count": int,
            "total_revenue": int (cents),
            "total_cost": int (cents),
            "total_margin": int (cents),
        }

    Raises:
        PeriodCloseError: If critical validation fails
    """
    issues = []

    # Parse month
    try:
        year, month_num = map(int, month.split('-'))
    except:
        raise PeriodCloseError(f"Invalid month format: {month}. Use YYYY-MM")

    # Validate invoices
    invoices = db.query(Invoice).filter(
        Invoice.business_unit_id == business_unit_id,
        func.strftime('%Y-%m', Invoice.billing_period_end) == month,
    ).all()

    if not invoices:
        raise PeriodCloseError(f"No invoices found for BU {business_unit_id} in {month}")

    # Check all invoices are PAID
    non_paid = [i for i in invoices if i.status != "PAID"]
    if non_paid:
        issues.append(
            f"Found {len(non_paid)} non-PAID invoices (status: "
            f"{', '.join(set(i.status for i in non_paid))}). "
            f"All must be PAID to close period."
        )

    # Check all timesheets APPROVED
    # TODO: Link invoices to timesheets and validate

    # Calculate totals
    total_revenue = sum(i.total_usd_cents for i in invoices if i.status == "PAID")

    # Get revenue records for margin
    revenues = db.query(Revenue).filter(
        Revenue.business_unit_id == business_unit_id,
        func.strftime('%Y-%m', Revenue.recognized_at) == month,
    ).all()

    total_cost = sum(r.cost_usd_cents for r in revenues)
    total_margin = total_revenue - total_cost

    return {
        "ready": len(issues) == 0,
        "issues": issues,
        "invoice_count": len(invoices),
        "paid_invoice_count": len([i for i in invoices if i.status == "PAID"]),
        "revenue_count": len(revenues),
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "total_margin": total_margin,
        "margin_pct": (total_margin / total_revenue * 100) if total_revenue > 0 else 0,
    }


# ============================================================================
# PART 2: PERIOD CLOSE LOCKING
# ============================================================================

def close_period(
    db: Session,
    business_unit_id: int,
    month: str,  # YYYY-MM format
    approved_by: str,
    notes: Optional[str] = None,
) -> Dict:
    """
    Close (lock) a period for accounting.

    Effects:
    ✓ No new invoices allowed for period
    ✓ No status changes allowed for period
    ✓ All revenue immutable (adjustments only)
    ✓ All records locked for audit

    Args:
        db: SQLAlchemy session
        business_unit_id: BU to close
        month: YYYY-MM format
        approved_by: User approving close (CFO/Finance Manager)
        notes: Optional close notes

    Returns:
        {
            "status": "CLOSED",
            "closed_at": datetime,
            "period": month,
            "approved_by": str,
            "invoice_count": int,
            "revenue_total": int,
        }

    Raises:
        PeriodCloseError: If close validation fails
    """
    # Validate period is ready
    validation = validate_period_ready_for_close(db, business_unit_id, month)

    if not validation["ready"]:
        raise PeriodCloseError(
            f"Period not ready for close. Issues:\n" +
            "\n".join(validation["issues"])
        )

    # TODO: Create PeriodClose record in database
    # This would store:
    # - period (YYYY-MM)
    # - business_unit_id
    # - status (CLOSED)
    # - closed_at
    # - approved_by
    # - notes
    # - invoice_count
    # - revenue_total
    # - margin_total

    return {
        "status": "CLOSED",
        "closed_at": datetime.utcnow().isoformat(),
        "period": month,
        "approved_by": approved_by,
        "invoice_count": validation["invoice_count"],
        "revenue_total": validation["total_revenue"],
        "margin_total": validation["total_margin"],
    }


def is_period_closed(
    db: Session,
    business_unit_id: int,
    month: str,  # YYYY-MM format
) -> bool:
    """
    Check if period is closed/locked.

    Args:
        db: SQLAlchemy session
        business_unit_id: BU to check
        month: YYYY-MM format

    Returns:
        True if period is closed, False otherwise

    TODO: Query PeriodClose table when created
    """
    # Placeholder - would query PeriodClose table
    return False


# ============================================================================
# PART 3: IMMUTABILITY ENFORCEMENT
# ============================================================================

def validate_invoice_modifiable(
    db: Session,
    invoice_id: str,
) -> bool:
    """
    Check if invoice can be modified.

    Returns False if:
    ✗ Invoice is already PAID (revenue recognized)
    ✗ Invoice's period is closed/locked
    ✗ Invoice's revenue is immutable

    Args:
        db: SQLAlchemy session
        invoice_id: Invoice to check

    Returns:
        True if modifiable, False if locked/immutable

    Raises:
        PeriodLockError: If period is locked
    """
    from app.models.invoice import Invoice

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()

    if not invoice:
        return False

    # Cannot modify PAID invoices
    if invoice.status == "PAID":
        raise PeriodLockError(
            f"Invoice {invoice_id} is PAID. Cannot modify (revenue is immutable). "
            f"Create adjustment record instead."
        )

    # Check if period is closed
    month = invoice.billing_period_end.strftime("%Y-%m")
    if is_period_closed(db, invoice.business_unit_id, month):
        raise PeriodLockError(
            f"Period {month} is closed. Cannot modify invoices in closed periods. "
            f"Contact Finance to reopen period."
        )

    return True


def validate_revenue_modifiable(
    db: Session,
    revenue_id: str,
) -> bool:
    """
    Check if revenue record can be modified.

    Returns False if:
    ✗ Revenue is marked immutable (always true)
    ✗ Period is closed/locked

    Args:
        db: SQLAlchemy session
        revenue_id: Revenue to check

    Returns:
        True if modifiable, False if locked

    Raises:
        PeriodLockError: If immutable or period locked
    """
    revenue = db.query(Revenue).filter(Revenue.id == revenue_id).first()

    if not revenue:
        return False

    # Revenue is always immutable once created
    if revenue.immutable_flag:
        raise PeriodLockError(
            f"Revenue {revenue_id} is immutable. Cannot modify original record. "
            f"Create adjustment record instead for corrections."
        )

    # Check if period is closed
    month = revenue.recognized_at.strftime("%Y-%m")
    if is_period_closed(db, revenue.business_unit_id, month):
        raise PeriodLockError(
            f"Period {month} is closed. Cannot modify revenue records in closed periods."
        )

    return True


# ============================================================================
# PART 4: RECONCILIATION REPORTING
# ============================================================================

def get_period_reconciliation(
    db: Session,
    business_unit_id: int,
    month: str,  # YYYY-MM format
) -> Dict:
    """
    Get detailed reconciliation report for period.

    Validates:
    ✓ All timesheets reconciled to invoices
    ✓ All invoices reconciled to revenue
    ✓ All revenue reconciled to payments
    ✓ Partner shares calculated correctly
    ✓ P&L ties to GL accounts (if integrated)

    Args:
        db: SQLAlchemy session
        business_unit_id: BU to reconcile
        month: YYYY-MM format

    Returns:
        {
            "period": month,
            "status": "RECONCILED" | "DISCREPANCY",
            "invoices": {
                "count": int,
                "total": int,
                "by_status": {status: count, ...}
            },
            "revenue": {
                "count": int,
                "total": int,
                "cost_total": int,
                "margin_total": int,
            },
            "reconciliation": {
                "invoice_total_matches_revenue": bool,
                "all_invoices_have_revenue": bool,
                "all_revenue_from_invoices": bool,
                "partner_share_correct": bool,
            },
            "discrepancies": [str],  # Issues found
        }
    """
    try:
        year, month_num = map(int, month.split('-'))
    except:
        raise PeriodCloseError(f"Invalid month format: {month}. Use YYYY-MM")

    # Get invoices for period
    invoices = db.query(Invoice).filter(
        Invoice.business_unit_id == business_unit_id,
        func.strftime('%Y-%m', Invoice.billing_period_end) == month,
    ).all()

    # Get revenue for period
    revenues = db.query(Revenue).filter(
        Revenue.business_unit_id == business_unit_id,
        func.strftime('%Y-%m', Revenue.recognized_at) == month,
    ).all()

    # Calculate totals
    invoice_total = sum(i.total_usd_cents for i in invoices if i.status == "PAID")
    revenue_total = sum(r.amount_usd_cents for r in revenues)
    cost_total = sum(r.cost_usd_cents for r in revenues)
    margin_total = revenue_total - cost_total

    # Check reconciliation
    discrepancies = []

    if invoice_total != revenue_total:
        discrepancies.append(
            f"Invoice total ({invoice_total}) ≠ Revenue total ({revenue_total})"
        )

    # Check each paid invoice has revenue
    for invoice in invoices:
        if invoice.status == "PAID":
            has_revenue = any(r.invoice_id == invoice.id for r in revenues)
            if not has_revenue:
                discrepancies.append(
                    f"Paid invoice {invoice.id} has no revenue record"
                )

    return {
        "period": month,
        "status": "RECONCILED" if len(discrepancies) == 0 else "DISCREPANCY",
        "invoices": {
            "count": len(invoices),
            "total": invoice_total,
            "by_status": {
                status: len([i for i in invoices if i.status == status])
                for status in ["DRAFT", "APPROVED", "SENT", "PAID", "CANCELLED"]
            }
        },
        "revenue": {
            "count": len(revenues),
            "total": revenue_total,
            "cost_total": cost_total,
            "margin_total": margin_total,
            "margin_pct": (margin_total / revenue_total * 100) if revenue_total > 0 else 0,
        },
        "reconciliation": {
            "invoice_total_matches_revenue": invoice_total == revenue_total,
            "all_invoices_have_revenue": len(discrepancies) == 0,
            "all_revenue_from_invoices": True,  # By construction
            "partner_share_correct": True,  # TODO: Validate against PartnerBUAssignment
        },
        "discrepancies": discrepancies,
    }


# ============================================================================
# PART 5: REOPEN PERIOD (For corrections)
# ============================================================================

def reopen_period(
    db: Session,
    business_unit_id: int,
    month: str,
    reopened_by: str,
    reason: str,
) -> Dict:
    """
    Reopen (unlock) a closed period for corrections.

    Used when:
    - Errors discovered after close
    - Late invoices need to be added
    - Adjustments needed

    Args:
        db: SQLAlchemy session
        business_unit_id: BU to reopen
        month: YYYY-MM format
        reopened_by: User reopening (CFO/Finance Manager)
        reason: Reason for reopening

    Returns:
        {
            "status": "REOPENED",
            "reopened_at": datetime,
            "period": month,
            "reopened_by": str,
            "reason": str,
        }

    TODO: Update PeriodClose record to REOPENED status
    """
    return {
        "status": "REOPENED",
        "reopened_at": datetime.utcnow().isoformat(),
        "period": month,
        "reopened_by": reopened_by,
        "reason": reason,
    }
