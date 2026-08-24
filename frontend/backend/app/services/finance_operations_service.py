"""EPIC-16 Finance Operations: Bank reconciliation, AR aging, invoice details."""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.invoice import Invoice, InvoiceLineItem
from app.models.client import Client
from app.models.user import Users


def get_bank_reconciliation_summary(db: Session, as_of_date: Optional[str] = None) -> Dict:
    """
    Bank reconciliation summary: bank balance vs ledger, outstanding checks/deposits.

    Returns:
    {
        "bank_balance_usd_cents": int,
        "ledger_balance_usd_cents": int,
        "reconciled": bool,
        "difference_usd_cents": int,
        "outstanding_items": [
            {
                "type": "check" | "deposit",
                "amount_usd_cents": int,
                "date": date,
                "days_outstanding": int,
                "description": str
            }
        ],
        "as_of_date": date
    }
    """
    # Placeholder - would integrate with real bank feed or GL
    return {
        "bank_balance_usd_cents": 0,
        "ledger_balance_usd_cents": 0,
        "reconciled": True,
        "difference_usd_cents": 0,
        "outstanding_items": [],
        "as_of_date": as_of_date or datetime.utcnow().date().isoformat(),
    }


def get_ar_aging_breakdown(db: Session, as_of_date: Optional[str] = None) -> Dict:
    """
    AR aging breakdown: invoices grouped by days overdue.

    Returns:
    {
        "total_ar_usd_cents": int,
        "aging_buckets": {
            "current": {...},          # 0-30 days
            "30_60_days": {...},       # 30-60 days
            "60_90_days": {...},       # 60-90 days
            "90_plus_days": {...}      # 90+ days
        },
        "as_of_date": date
    }
    """
    as_of = datetime.fromisoformat(as_of_date) if as_of_date else datetime.utcnow()

    invoices = db.query(Invoice).filter(
        Invoice.status.in_(("SENT", "PARTIAL")),
        Invoice.due_date <= as_of.date()
    ).all()

    buckets = {
        "current": {"count": 0, "total_usd_cents": 0, "invoices": []},
        "30_60_days": {"count": 0, "total_usd_cents": 0, "invoices": []},
        "60_90_days": {"count": 0, "total_usd_cents": 0, "invoices": []},
        "90_plus_days": {"count": 0, "total_usd_cents": 0, "invoices": []},
    }

    for inv in invoices:
        days_overdue = (as_of.date() - inv.due_date).days
        amount = inv.total_amount_usd_cents

        if days_overdue <= 30:
            bucket = "current"
        elif days_overdue <= 60:
            bucket = "30_60_days"
        elif days_overdue <= 90:
            bucket = "60_90_days"
        else:
            bucket = "90_plus_days"

        buckets[bucket]["count"] += 1
        buckets[bucket]["total_usd_cents"] += amount
        buckets[bucket]["invoices"].append({
            "invoice_id": inv.id,
            "client_name": inv.client.company_name if inv.client else "Unknown",
            "invoice_number": inv.invoice_number,
            "amount_usd_cents": amount,
            "due_date": inv.due_date.isoformat(),
            "days_overdue": days_overdue,
        })

    total_ar = sum(bucket["total_usd_cents"] for bucket in buckets.values())

    return {
        "total_ar_usd_cents": total_ar,
        "aging_buckets": buckets,
        "as_of_date": as_of.date().isoformat(),
    }


def get_invoice_detail_drill_down(db: Session, invoice_id: str) -> Dict:
    """
    Complete invoice detail view with line items, payment history, notes.

    Returns full invoice record with expanded details for drill-down panel.
    """
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()

    if not invoice:
        return {"error": f"Invoice {invoice_id} not found"}

    line_items = db.query(InvoiceLineItem).filter(
        InvoiceLineItem.invoice_id == invoice_id
    ).all()

    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "client_id": invoice.client_id,
        "client_name": invoice.client.company_name if invoice.client else "Unknown",
        "status": invoice.status,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "total_amount_usd_cents": invoice.total_amount_usd_cents,
        "paid_amount_usd_cents": invoice.paid_amount_usd_cents or 0,
        "outstanding_amount_usd_cents": (invoice.total_amount_usd_cents or 0) - (invoice.paid_amount_usd_cents or 0),
        "line_items": [
            {
                "description": item.description,
                "quantity": item.quantity,
                "rate_usd_cents": item.rate_usd_cents,
                "total_usd_cents": item.total_usd_cents,
                "category": item.category,
            }
            for item in line_items
        ],
        "notes": invoice.notes or "",
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
    }
