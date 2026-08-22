"""
EPIC-16 -- Hiring Affordability. Checks a proposed hire against the
BU's real current P&L before it proceeds (the CFO Agent's planned
"hiring affordability gate" reads this directly). No new config table
for a minimum-margin threshold -- the workbook gave this engine's
shape (compare projected margin against current), not an exact
threshold number, and inventing one would be a guess dressed up as
policy. Conservative default: affordable if projected gross margin
stays non-negative after the hire's fully loaded cost is added --
flagged here as the one real assumption, easy to make configurable
later once Avinash gives an actual minimum-margin policy.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.services.cost_rate_service import get_active_cost_rate_config
from app.services.pnl_service import get_bu_pnl

# Flagged assumption, not a given policy number -- see module docstring.
MIN_ACCEPTABLE_MARGIN_PCT = 0.0


def check_hiring_affordability(
    db: Session, *, business_unit_id: int, proposed_annual_salary_usd_cents: int, year: int, month: int,
) -> dict:
    pnl = get_bu_pnl(db, business_unit_id=business_unit_id, year=year, month=month)
    config = get_active_cost_rate_config(db, business_unit_id=business_unit_id)

    if not pnl["cost_data_complete"] or config is None:
        return {
            "business_unit_id": business_unit_id, "affordable": None,
            "current_margin_pct": pnl["margin_pct"], "projected_margin_pct": None,
            "reason": "Cost data incomplete -- set a cost-rate config and ensure current allocations have salaries on file first.",
        }

    proposed_monthly_salary = round(proposed_annual_salary_usd_cents / 12)
    proposed_monthly_fully_loaded_cost = round(
        proposed_monthly_salary
        * (1 + float(config.statutory_pct) / 100 + float(config.overhead_pct) / 100)
    )

    projected_cost = pnl["cost_usd_cents"] + proposed_monthly_fully_loaded_cost
    projected_margin_usd_cents = pnl["revenue_usd_cents"] - projected_cost
    projected_margin_pct = (
        round(projected_margin_usd_cents / pnl["revenue_usd_cents"] * 100, 1)
        if pnl["revenue_usd_cents"] > 0 else None
    )

    affordable = projected_margin_pct is not None and projected_margin_pct >= MIN_ACCEPTABLE_MARGIN_PCT

    return {
        "business_unit_id": business_unit_id,
        "affordable": affordable,
        "current_margin_pct": pnl["margin_pct"],
        "projected_margin_pct": projected_margin_pct,
        "proposed_monthly_fully_loaded_cost_usd_cents": proposed_monthly_fully_loaded_cost,
        "reason": None if affordable else f"Projected margin ({projected_margin_pct}%) would fall below the {MIN_ACCEPTABLE_MARGIN_PCT}% floor.",
    }
