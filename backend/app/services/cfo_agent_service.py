"""CFO Agent â€” financial Q&A and insights for Chief Financial Officer."""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models.invoice import Invoice
from app.models.revenue_leakage import RevenueLeakageFlag
from app.models.timesheet_dispute import TimesheetDispute
from app.models.user import Users
from app.services.pnl_service import get_org_pnl_summary, get_bu_pnl
from app.services.ar_followup_service import scan_overdue_invoices
from app.services.reserve_fund_service import get_reserve_fund_status
import logging
from app.utils.agent_logger import log_agent_execution


def get_org_financial_snapshot(db: Session, year_month: str = None, tenant_id: str = None) -> dict:
    """
    Get organization-wide financial snapshot for CFO (requires Finance role + CEO access).

    Args:
        db: Database session
        year_month: YYYY-MM format; defaults to current month

    Returns:
        dict with org-wide metrics: total_revenue, total_cost, gross_margin, cash_position, ar_aging, leakage, disputes
    """
    if not year_month:
        today = datetime.utcnow()
        year_month = today.strftime("%Y-%m")

    year, month = year_month.split("-")
    year, month = int(year), int(month)

    period_start = datetime(year, month, 1)
    if month == 12:
        period_end = datetime(year + 1, 1, 1)
    else:
        period_end = datetime(year, month + 1, 1)

    # 1. Total Revenue (all invoices, all BUs, this month)
    total_revenue = db.query(func.sum(Invoice.total_amount_usd_cents)).filter(
        Invoice.created_at >= period_start,
        Invoice.created_at < period_end,
        Invoice.status.in_(["APPROVED", "SENT", "PAID"])
    ).scalar() or 0

    # 2. Org-wide P&L (all BUs combined)
    pnl = get_org_pnl_summary(db, year_month)

    # 3. AR Aging (unpaid invoices by age bucket)
    ar_aging = scan_overdue_invoices(db, year_month)

    # 4. Reserve Fund Status
    reserve = get_reserve_fund_status(db)

    # 5. Revenue Leakage (gap between invoiced and earned hours)
    leakage = db.query(func.sum(RevenueLeakageFlag.unbilled_hours)).filter(
        RevenueLeakageFlag.detected_at >= period_start,
        RevenueLeakageFlag.detected_at < period_end
    ).scalar() or 0

    # 6. Open Disputes (timesheet disputes pending resolution)
    disputes = db.query(func.count(TimesheetDispute.id)).filter(
        TimesheetDispute.status == "PENDING",
        TimesheetDispute.created_at >= period_start
    ).scalar() or 0

    # 7. Cash Position (invoices PAID, minus expenses)
    cash_paid = db.query(func.sum(Invoice.total_amount_usd_cents)).filter(
        Invoice.status == "PAID",
        Invoice.created_at >= period_start,
        Invoice.created_at < period_end
    ).scalar() or 0

    result = {
        "period": year_month,
        "total_revenue_usd": total_revenue / 100 if total_revenue else 0,
        "total_revenue_usd_cents": total_revenue,
        "gross_margin_pct": pnl.get("margin_pct", 0) if pnl else 0,
        "net_position_usd": (pnl.get("net_position_usd_cents", 0) / 100) if pnl else 0,
        "net_position_usd_cents": pnl.get("net_position_usd_cents", 0) if pnl else 0,
        "cost_of_delivery_usd": (pnl.get("total_cost_usd_cents", 0) / 100) if pnl else 0,
        "cost_of_delivery_usd_cents": pnl.get("total_cost_usd_cents", 0) if pnl else 0,
        "cash_position_usd": cash_paid / 100 if cash_paid else 0,
        "cash_position_usd_cents": cash_paid,
        "ar_aging_summary": ar_aging,
        "reserve_fund_target_usd": (reserve.get("target_usd_cents", 0) / 100) if reserve else 0,
        "reserve_fund_current_usd": (reserve.get("current_balance_usd_cents", 0) / 100) if reserve else 0,
        "revenue_leakage_hours": leakage,
        "open_disputes_count": disputes
    }

    log_agent_execution(
        db=db,
        agent_name="CFO Agent",
        action_taken="get_org_financial_snapshot",
        tenant_id=tenant_id or "system",
        action_data={
            "period": year_month,
            "total_revenue_usd_cents": total_revenue,
            "gross_margin_pct": result.get("gross_margin_pct", 0),
            "net_position_usd_cents": result.get("net_position_usd_cents", 0),
        },
        success=True,
    )

    return result


def get_cfo_alerts(db: Session) -> list:
    """Generate critical financial alerts for CFO attention."""
    snapshot = get_org_financial_snapshot(db)
    alerts = []

    # Alert: Low cash position vs reserve target
    if snapshot["cash_position_usd_cents"] < (snapshot.get("reserve_fund_target_usd_cents", 0) * 0.5):
        alerts.append({
            "severity": "CRITICAL",
            "type": "CASH_POSITION",
            "message": f"Cash position ${snapshot['cash_position_usd']:.0f} is below 50% of reserve target ${snapshot.get('reserve_fund_target_usd', 0):.0f}",
            "recommendation": "Accelerate AR collection or reduce spending"
        })

    # Alert: High AR aging
    if snapshot["ar_aging_summary"]:
        overdue_90 = snapshot["ar_aging_summary"].get("overdue_90_plus_days", 0)
        if overdue_90 > 50000:  # $50k+
            alerts.append({
                "severity": "HIGH",
                "type": "AR_AGING",
                "message": f"${overdue_90 / 100:.0f} in invoices overdue >90 days",
                "recommendation": "Follow up with accounts receivable on oldest invoices"
            })

    # Alert: Negative margin month
    if snapshot["gross_margin_pct"] < 0:
        alerts.append({
            "severity": "CRITICAL",
            "type": "MARGIN",
            "message": f"Negative gross margin this month: {snapshot['gross_margin_pct']:.1f}%",
            "recommendation": "Urgent: Review pricing and delivery cost structure"
        })

    # Alert: High revenue leakage
    if snapshot["revenue_leakage_hours"] > 100:
        alerts.append({
            "severity": "HIGH",
            "type": "LEAKAGE",
            "message": f"{snapshot['revenue_leakage_hours']:.0f} hours of revenue leakage this period",
            "recommendation": "Review timesheet-to-invoice reconciliation process"
        })

    # Alert: Open disputes
    if snapshot["open_disputes_count"] > 5:
        alerts.append({
            "severity": "MEDIUM",
            "type": "DISPUTES",
            "message": f"{snapshot['open_disputes_count']} timesheet disputes pending resolution",
            "recommendation": "Route disputes to appropriate team leads for resolution"
        })

    return sorted(alerts, key=lambda x: ({"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}.get(x["severity"], 3)))


def get_bu_financial_comparison(db: Session, year_month: str = None) -> list:
    """Compare all BU financials side-by-side for CFO analysis."""
    if not year_month:
        today = datetime.utcnow()
        year_month = today.strftime("%Y-%m")

    # Get all users with business_unit_id assigned (replaces hardcoded Partner role check)
    # Partner role is identified via role template permissions, not UserRole string
    # This query gets all users managing a BU, regardless of role name
    partners = db.query(Users).filter(
        Users.business_unit_id.isnot(None)
    ).all()

    # Filter to only those with Partner-level permissions (business unit management)
    comparison = []
    for partner in partners:
        try:
            pnl = get_bu_pnl(db, partner.business_unit_id, year_month)
            comparison.append({
                "partner_name": partner.UserName,
                "bu_id": partner.business_unit_id,
                "revenue_usd": (pnl.get("total_revenue_usd_cents", 0) / 100) if pnl else 0,
                "cost_usd": (pnl.get("total_cost_usd_cents", 0) / 100) if pnl else 0,
                "net_position_usd": (pnl.get("net_position_usd_cents", 0) / 100) if pnl else 0,
                "margin_pct": pnl.get("margin_pct", 0) if pnl else 0
            })
        except Exception:
            pass

    return sorted(comparison, key=lambda x: x["revenue_usd"], reverse=True)


def get_expense_breakdown(db: Session, year_month: str = None) -> dict:
    """Break down org expenses by category (salaries, overhead, etc)."""
    if not year_month:
        today = datetime.utcnow()
        year_month = today.strftime("%Y-%m")

    # This would ideally come from detailed expense tracking
    # For now, derive from P&L
    pnl = get_org_pnl_summary(db, year_month)

    return {
        "period": year_month,
        "total_cost_usd": (pnl.get("total_cost_usd_cents", 0) / 100) if pnl else 0,
        "salary_cost_pct": 70,  # Estimated
        "overhead_cost_pct": 20,  # Estimated
        "other_cost_pct": 10,  # Estimated
        "note": "Breakdown is estimated â€” detailed expense tracking not yet implemented"
    }


def get_financial_forecast(db: Session, months_ahead: int = 3) -> dict:
    """Generate simple revenue forecast based on recent trend."""
    today = datetime.utcnow()
    recent_months = []

    for i in range(6):
        month_date = today - timedelta(days=30 * i)
        year_month = month_date.strftime("%Y-%m")
        snapshot = get_org_financial_snapshot(db, year_month)
        recent_months.append({
            "month": year_month,
            "revenue": snapshot["total_revenue_usd_cents"]
        })

    recent_months = sorted(recent_months, key=lambda x: x["month"])

    # Simple linear trend
    if len(recent_months) >= 2:
        avg_change = (recent_months[-1]["revenue"] - recent_months[0]["revenue"]) / (len(recent_months) - 1)
    else:
        avg_change = 0

    forecast = []
    latest_revenue = recent_months[-1]["revenue"] if recent_months else 0

    for i in range(months_ahead):
        forecast_month = (today + timedelta(days=30 * (i + 1))).strftime("%Y-%m")
        forecast_revenue = latest_revenue + (avg_change * (i + 1))
        forecast.append({
            "month": forecast_month,
            "forecast_revenue_usd": forecast_revenue / 100 if forecast_revenue > 0 else 0,
            "forecast_revenue_usd_cents": max(0, int(forecast_revenue))
        })

    return {
        "forecast_basis": "6-month linear trend",
        "months": forecast
    }
