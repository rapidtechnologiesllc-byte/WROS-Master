"""Partner ROI Agent — computes weekly Partner scorecard based on BlitzenX Operating Model KPIs."""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text
from app.models.client import Client
from app.models.opportunity import Opportunity
from app.models.invoice import Invoice
from app.models.user import Users
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.demand import Demand
from app.services.pnl_service import get_bu_pnl
from app.services.client_revenue_dashboard_service import get_client_revenue_dashboard
from app.utils.agent_logger import log_agent_execution


def get_partner_kpis(db: Session, partner_id: str, year_month: str = None) -> dict:
    """
    Compute Partner KPIs per BlitzenX Operating Model.
    Partner KPIs: Revenue, Gross Margin, Net New Logos, Customer Satisfaction, Practice Utilization, Practice Growth, Thought Leadership, P&L.

    Args:
        db: Database session
        partner_id: Partner's UserID
        year_month: YYYY-MM format; defaults to current month

    Returns:
        dict with keys: revenue, gross_margin, net_new_logos, customer_satisfaction, practice_utilization,
                       practice_growth, thought_leadership, pnl, period, partner_name, bu_id
    """
    if not year_month:
        today = datetime.utcnow()
        year_month = today.strftime("%Y-%m")

    year, month = year_month.split("-")
    year, month = int(year), int(month)

    # Get partner and their BU
    partner = db.query(Users).filter(Users.UserID == partner_id).first()
    if not partner:
        raise ValueError(f"Partner {partner_id} not found")

    # Partner owns exactly one BU per the Operating Model
    bu_id = partner.business_unit_id
    if not bu_id:
        return {
            "error": "Partner has no assigned Business Unit",
            "partner_id": partner_id,
            "partner_name": partner.UserName
        }

    # All KPIs scoped to this Partner's BU
    period_start = datetime(year, month, 1)
    if month == 12:
        period_end = datetime(year + 1, 1, 1)
    else:
        period_end = datetime(year, month + 1, 1)

    # 1. Revenue: total invoiced revenue for this BU this month
    invoices = db.query(func.sum(Invoice.total_amount_usd_cents)).filter(
        Invoice.business_unit_id == bu_id,
        Invoice.created_at >= period_start,
        Invoice.created_at < period_end,
        Invoice.status.in_(["APPROVED", "SENT", "PAID"])
    ).scalar() or 0

    revenue_usd_cents = invoices
    revenue_usd = revenue_usd_cents / 100 if revenue_usd_cents else 0

    # 2. Gross Margin: (Revenue - Fully Loaded Cost) / Revenue
    pnl = get_bu_pnl(db, bu_id, year_month)

    # 3. Net New Logos: new clients added this month to this BU (status=ACTIVE, first invoice this month)
    new_clients = db.query(func.count(Client.id)).filter(
        Client.business_unit_id == bu_id,
        Client.status == "ACTIVE",
        Client.created_at >= period_start,
        Client.created_at < period_end
    ).scalar() or 0

    # 4. Customer Satisfaction: placeholder (no satisfaction data model exists yet)
    # Would come from post-project surveys once implemented
    customer_satisfaction = None

    # 5. Practice Utilization: billable hours / total available hours for allocated employees
    # Available hours = 40 hours/week, roughly 4.33 weeks/month = 173 hours
    allocated_employees = db.query(func.count(func.distinct(EmployeeAllocation.employee_id))).filter(
        EmployeeAllocation.business_unit_id == bu_id,
        EmployeeAllocation.start_date <= period_end,
        and_(
            EmployeeAllocation.end_date.is_(None),
            EmployeeAllocation.end_date >= period_start
        )
    ).scalar() or 0

    available_hours = allocated_employees * 173 if allocated_employees > 0 else 1

    # Billable hours from invoices (approximation: invoice line items have hours)
    billable_hours = db.query(func.sum(Invoice.billable_hours)).filter(
        Invoice.business_unit_id == bu_id,
        Invoice.created_at >= period_start,
        Invoice.created_at < period_end
    ).scalar() or 0

    practice_utilization_pct = (billable_hours / available_hours * 100) if available_hours > 0 else 0

    # 6. Practice Growth: YoY revenue growth
    # Previous year same month
    prev_year = year - 1 if month >= 1 else year - 1
    prev_month = month
    prev_period_start = datetime(prev_year, prev_month, 1)
    if prev_month == 12:
        prev_period_end = datetime(prev_year + 1, 1, 1)
    else:
        prev_period_end = datetime(prev_year, prev_month + 1, 1)

    prev_invoices = db.query(func.sum(Invoice.total_amount_usd_cents)).filter(
        Invoice.business_unit_id == bu_id,
        Invoice.created_at >= prev_period_start,
        Invoice.created_at < prev_period_end,
        Invoice.status.in_(["APPROVED", "SENT", "PAID"])
    ).scalar() or 1  # Avoid divide by zero

    growth_pct = ((revenue_usd_cents - prev_invoices) / prev_invoices * 100) if prev_invoices else 0

    # 7. Thought Leadership: placeholder (would track articles/speaking/etc.)
    thought_leadership = None

    # 8. P&L (from pnl_service)
    pnl_margin = pnl.get("margin_pct", 0) if pnl else 0

    result = {
        "partner_id": partner_id,
        "partner_name": partner.UserName,
        "bu_id": bu_id,
        "period": year_month,
        "revenue_usd": revenue_usd,
        "revenue_usd_cents": revenue_usd_cents,
        "gross_margin_pct": pnl_margin,
        "net_new_logos": new_clients,
        "customer_satisfaction_score": customer_satisfaction,
        "practice_utilization_pct": round(practice_utilization_pct, 1),
        "practice_growth_yoy_pct": round(growth_pct, 1),
        "thought_leadership_score": thought_leadership,
        "pnl_usd": (pnl.get("net_position_usd_cents", 0) / 100) if pnl else 0,
        "pnl_usd_cents": pnl.get("net_position_usd_cents", 0) if pnl else 0,
        "pnl_margin_pct": pnl_margin,
        "billable_hours": billable_hours,
        "allocated_headcount": allocated_employees
    }

    log_agent_execution(
        db=db,
        agent_name="Partner ROI Agent",
        action_taken="get_partner_kpis",
        tenant_id=partner_id,
        action_data={
            "bu_id": bu_id,
            "revenue_usd_cents": revenue_usd_cents,
            "gross_margin_pct": pnl_margin,
            "new_logos": new_clients
        },
        success=True,
    )

    return result


def get_partner_trend(db: Session, partner_id: str, months_back: int = 6) -> list:
    """Get Partner's KPI trend over last N months."""
    partner = db.query(Users).filter(Users.UserID == partner_id).first()
    if not partner:
        raise ValueError(f"Partner {partner_id} not found")

    today = datetime.utcnow()
    trend = []

    for i in range(months_back):
        month_offset = today - timedelta(days=today.day) - timedelta(days=30 * i)
        year_month = month_offset.strftime("%Y-%m")
        kpis = get_partner_kpis(db, partner_id, year_month)
        if "error" not in kpis:
            trend.append(kpis)

    return sorted(trend, key=lambda x: x["period"])


def get_partner_actions(db: Session, partner_id: str) -> list:
    """Generate prioritized action items for Partner based on KPIs."""
    kpis = get_partner_kpis(db, partner_id)

    if "error" in kpis:
        return []

    actions = []

    # Low utilization warning
    if kpis["practice_utilization_pct"] < 70:
        actions.append({
            "priority": "HIGH",
            "category": "UTILIZATION",
            "message": f"Practice utilization at {kpis['practice_utilization_pct']}% — below 70% target. Review open demands and bench allocation.",
            "metric": "practice_utilization_pct"
        })

    # Margin concern
    if kpis["pnl_margin_pct"] < 15:
        actions.append({
            "priority": "HIGH",
            "category": "MARGIN",
            "message": f"Gross margin at {kpis['pnl_margin_pct']}% — below 20% target. Review pricing and delivery costs.",
            "metric": "pnl_margin_pct"
        })

    # Growth trend
    if kpis["practice_growth_yoy_pct"] < 0:
        actions.append({
            "priority": "MEDIUM",
            "category": "GROWTH",
            "message": f"Year-over-year revenue declined {abs(kpis['practice_growth_yoy_pct'])}% — accelerate new customer acquisition.",
            "metric": "practice_growth_yoy_pct"
        })

    # Low new logos
    if kpis["net_new_logos"] < 2:
        actions.append({
            "priority": "MEDIUM",
            "category": "LOGOS",
            "message": f"Only {kpis['net_new_logos']} new logos this month — increase pipeline activity.",
            "metric": "net_new_logos"
        })

    return sorted(actions, key=lambda x: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(x["priority"], 3), x["category"]))
