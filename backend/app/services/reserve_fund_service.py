"""
EPIC-16 -- Reserve Fund Ledger. Target is a real, computed 12-month
operating-cost figure (trailing average BU P&L cost x 12), not an
invented number -- matching the "contribution-% reserve with a
12-month-target gate" shape already scoped for this engine. The
contribution amount/cadence itself is a real transaction Avinash (or
Finance) records, never invented here.
"""
from datetime import date
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.reserve_fund import ReserveFundEntry
from app.services.pnl_service import get_bu_pnl
from app.core.logging import logger

logger = logging.getLogger(__name__)

class ReserveFundError(Exception):
    pass


def record_reserve_fund_entry(
    db: Session, *, entry_type: str, amount_usd_cents: int, period_year: int, period_month: int,
    created_by: str, business_unit_id: Optional[int] = None, tenant_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> ReserveFundEntry:
    if amount_usd_cents <= 0:
        raise ReserveFundError("amount_usd_cents must be positive.")
    entry = ReserveFundEntry(
        tenant_id=tenant_id, business_unit_id=business_unit_id, entry_type=entry_type,
        amount_usd_cents=amount_usd_cents, period_year=period_year, period_month=period_month,
        created_by=created_by, notes=notes,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_reserve_fund_balance(db: Session, *, business_unit_id: Optional[int] = None) -> int:
    query = db.query(ReserveFundEntry)
    if business_unit_id is not None:
        query = query.filter(ReserveFundEntry.business_unit_id == business_unit_id)
    else:
        query = query.filter(ReserveFundEntry.business_unit_id.is_(None))
    balance = 0
    for entry in query.all():
        balance += entry.amount_usd_cents if entry.entry_type == "CONTRIBUTION" else -entry.amount_usd_cents
    return balance


def get_reserve_fund_target_usd_cents(
    db: Session, *, business_unit_id: int, as_of_year: int, as_of_month: int, trailing_months: int = 3,
) -> Optional[int]:
    """12x the trailing average monthly BU operating cost -- None when
    cost data isn't complete enough to average (no cost-rate config
    set, no allocations), never a fabricated target."""
    total_cost = 0
    months_with_data = 0
    y, m = as_of_year, as_of_month
    for _ in range(trailing_months):
        pnl = get_bu_pnl(db, business_unit_id=business_unit_id, year=y, month=m)
        if pnl["cost_data_complete"] and pnl["cost_usd_cents"] is not None:
            total_cost += pnl["cost_usd_cents"]
            months_with_data += 1
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    if months_with_data == 0:
        return None
    avg_monthly_cost = total_cost / months_with_data
    return round(avg_monthly_cost * 12)


def get_reserve_fund_status(
    db: Session, *, business_unit_id: int, as_of_year: int, as_of_month: int,
) -> dict:
    balance = get_reserve_fund_balance(db, business_unit_id=business_unit_id)
    target = get_reserve_fund_target_usd_cents(db, business_unit_id=business_unit_id, as_of_year=as_of_year, as_of_month=as_of_month)
    pct_funded = round(balance / target * 100, 1) if target and target > 0 else None
    return {
        "business_unit_id": business_unit_id,
        "balance_usd_cents": balance,
        "target_usd_cents": target,
        "gap_usd_cents": (target - balance) if target is not None else None,
        "pct_funded": pct_funded,
    }
