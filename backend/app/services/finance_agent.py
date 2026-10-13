"""
Finance Agent - Constant Vigilance Over Profitability

Monitors P&L per partner and per BU and escalates when net profit falls
below the 25% floor.

Real data model:
- A partner owns the BUs where BusinessUnit.partner_user_id is their UserID.
- Revenue is client invoices (Invoice.total_usd_cents, excluding DRAFT);
  invoices reach a BU through Client.business_unit_id.
- Payroll is Employee.base_salary_usd_cents (monthly) for the BU's
  working employees (Employee.bu_id); titles containing "sales" count
  as sales opex, everyone else as delivery COGS.
- Vendor/contractor invoices are not recorded anywhere, so contractor
  spend is reported as untracked (0), not estimated.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import roles
from app.models.business_unit import BusinessUnit
from app.models.client import Client
from app.models.employee import Employee
from app.models.invoice import Invoice
from app.models.org_structure import OrgNode

logger = logging.getLogger(__name__)

RECOGNISED_INVOICE_STATUSES = ("APPROVED", "SENT", "PAID")
WORKING_EMPLOYEE_STATUSES = ("ACTIVE", "ALLOCATED", "BENCH", "ON_LEAVE", "NOTICE_PERIOD",
                             "SPECIALITY_READY", "PERFORMANCE_MANAGED")
# Estimated fixed costs (no cost ledger exists yet)
INFRASTRUCTURE_BASE_USD = 2000
INFRASTRUCTURE_PCT_OF_REVENUE = 0.05
MARKETING_MONTHLY_USD = 3000
GA_MONTHLY_USD = 5000
LARGE_INVOICE_USD = 10000
NET_MARGIN_FLOOR_PCT = 25


def partner_bu_ids(db: Session, partner_id: str) -> List[int]:
    """The BUs this partner owns (BusinessUnit.partner_user_id). BU heads are per company (BusinessUnitLocationHead)."""
    return [row[0] for row in db.query(BusinessUnit.id).filter(BusinessUnit.partner_user_id == partner_id).all()]


def partner_user_ids(db: Session, tenant_id) -> List[str]:
    """Partners are the users the BU structure names as partner, not a UserRole string."""
    rows = db.query(BusinessUnit.partner_user_id).filter(BusinessUnit.tenant_id == tenant_id,
                                                         BusinessUnit.partner_user_id.isnot(None)).distinct().all()
    return [row[0] for row in rows]


def _client_ids(bu_ids: Iterable[int]):
    return select(Client.id).where(Client.business_unit_id.in_(list(bu_ids)))


def _invoice_cents(db: Session, bu_ids: List[int], since: datetime) -> int:
    return db.query(func.coalesce(func.sum(Invoice.total_usd_cents), 0)).filter(
        Invoice.client_id.in_(_client_ids(bu_ids)),
        Invoice.created_at >= since,
        Invoice.status.in_(RECOGNISED_INVOICE_STATUSES),
    ).scalar() or 0


def _payroll_usd(db: Session, bu_ids: List[int], sales: bool) -> float:
    """Sales vs delivery payroll by the function of the person's org seat (from their
    department), never by words in a job title."""
    in_sales = select(OrgNode.id).where(OrgNode.specialization == "Sales")
    is_sales = Employee.org_node_id.in_(in_sales)
    cents = db.query(func.coalesce(func.sum(Employee.base_salary_usd_cents), 0)).filter(
        Employee.bu_id.in_(bu_ids),
        Employee.status.in_(WORKING_EMPLOYEE_STATUSES),
        is_sales if sales else or_(Employee.org_node_id.is_(None), ~is_sales),
    ).scalar() or 0
    return cents / 100


class FinanceAgent:
    """Real-time profitability monitoring per partner and per BU."""

    @staticmethod
    def calculate_pl_for_bus(db: Session, bu_ids: List[int], annual_goal_usd: Optional[float] = None) -> Dict[str, Any]:
        """Month-to-date P&L across the given BUs."""
        today = datetime.utcnow()
        month_start = datetime(today.year, today.month, 1)

        revenue = _invoice_cents(db, bu_ids, month_start) / 100 if bu_ids else 0
        invoice_counts = dict(
            db.query(Invoice.status, func.count(Invoice.id)).filter(
                Invoice.client_id.in_(_client_ids(bu_ids)),
                Invoice.created_at >= month_start,
                Invoice.status.in_(RECOGNISED_INVOICE_STATUSES),
            ).group_by(Invoice.status).all()
        ) if bu_ids else {}
        invoice_total = sum(invoice_counts.values())

        delivery_team_salary = _payroll_usd(db, bu_ids, sales=False) if bu_ids else 0
        contractor_spend = 0  # not tracked: no vendor invoices exist
        infrastructure_cost = INFRASTRUCTURE_BASE_USD + revenue * INFRASTRUCTURE_PCT_OF_REVENUE
        total_cogs = delivery_team_salary + contractor_spend + infrastructure_cost

        gross_profit = revenue - total_cogs
        gross_margin = (gross_profit / revenue * 100) if revenue > 0 else 0

        sales_team_salary = _payroll_usd(db, bu_ids, sales=True) if bu_ids else 0
        total_opex = sales_team_salary + MARKETING_MONTHLY_USD + GA_MONTHLY_USD

        operating_profit = gross_profit - total_opex
        operating_margin = (operating_profit / revenue * 100) if revenue > 0 else 0
        net_profit = operating_profit
        net_margin = (net_profit / revenue * 100) if revenue > 0 else 0

        health_status = "🟢 HEALTHY" if net_margin >= 25 else "🟡 CAUTION" if net_margin >= 20 else "🔴 CRITICAL"
        result = {
            "bu_ids": bu_ids,
            "reporting_time": today.isoformat(),
            "period": f"MTD (since {month_start.date()})",
            "revenue": {
                "total": f"${revenue:,.0f}",
                "total_usd": revenue,
                "invoices_paid": invoice_counts.get("PAID", 0),
                "invoices_pending": invoice_total - invoice_counts.get("PAID", 0),
                "average_invoice": f"${revenue / max(1, invoice_total):,.0f}",
            },
            "cogs": {
                "delivery_team_salary": f"${delivery_team_salary:,.0f}",
                "contractor_spend": f"${contractor_spend:,.0f}",
                "contractor_spend_tracked": False,
                "infrastructure": f"${infrastructure_cost:,.0f}",
                "total_cogs": f"${total_cogs:,.0f}",
                "cogs_pct_revenue": round(total_cogs / revenue * 100, 1) if revenue > 0 else 0,
            },
            "gross_profit": {
                "amount": f"${gross_profit:,.0f}",
                "margin_pct": round(gross_margin, 1),
                "target": 70,
                "status": "✅" if gross_margin >= 70 else "⚠️",
            },
            "opex": {
                "sales_team_salary": f"${sales_team_salary:,.0f}",
                "marketing": f"${MARKETING_MONTHLY_USD:,.0f}",
                "ga_expense": f"${GA_MONTHLY_USD:,.0f}",
                "total_opex": f"${total_opex:,.0f}",
                "opex_pct_revenue": round(total_opex / revenue * 100, 1) if revenue > 0 else 0,
            },
            "operating_profit": {
                "amount": f"${operating_profit:,.0f}",
                "margin_pct": round(operating_margin, 1),
                "target": 20,
                "status": "✅" if operating_margin >= 20 else "⚠️",
            },
            "net_profit": {
                "amount": f"${net_profit:,.0f}",
                "margin_pct": round(net_margin, 1),
                "target": NET_MARGIN_FLOOR_PCT,
                "status": health_status,
            },
            "escalation": net_margin < NET_MARGIN_FLOOR_PCT,
            "escalation_message": FinanceAgent._get_escalation_message(net_margin, revenue),
        }
        if annual_goal_usd:
            ytd_start = datetime(today.year, 1, 1)
            ytd_revenue = _invoice_cents(db, bu_ids, ytd_start) / 100 if bu_ids else 0
            expected = annual_goal_usd * (today.timetuple().tm_yday / 365)
            result["annual_goal"] = {
                "goal_usd": annual_goal_usd,
                "ytd_revenue_usd": ytd_revenue,
                "expected_by_today_usd": round(expected, 2),
                "pct_of_goal": round(ytd_revenue / annual_goal_usd * 100, 1),
                "on_pace": ytd_revenue >= expected,
            }
        return result

    @staticmethod
    def calculate_real_time_partner_pl(db: Session, tenant_id, partner_id: str,
                                       annual_goal_usd: Optional[float] = None) -> Dict[str, Any]:
        """Month-to-date P&L consolidated across the partner's BUs."""
        result = FinanceAgent.calculate_pl_for_bus(db, partner_bu_ids(db, partner_id), annual_goal_usd)
        result["partner_id"] = partner_id
        return result

    @staticmethod
    def calculate_bu_pl(db: Session, tenant_id, bu_id: int,
                        annual_goal_usd: Optional[float] = None) -> Dict[str, Any]:
        result = FinanceAgent.calculate_pl_for_bus(db, [bu_id], annual_goal_usd)
        result["bu_id"] = bu_id
        return result

    @staticmethod
    def _get_escalation_message(net_margin: float, revenue: float) -> str:
        """Generate escalation message if profitability is at risk."""
        if revenue <= 0:
            return "🟡 NO REVENUE: No approved/sent/paid invoices this month."
        if net_margin < 15:
            return f"🔴🔴 SEVERE: Net margin {net_margin:.1f}% - Business failing. Emergency intervention required. CEO + Partner emergency call NOW."
        elif net_margin < 20:
            return f"🔴 CRITICAL: Net margin {net_margin:.1f}% below 25% floor. Recovery plan due 24 hours. All discretionary spending frozen."
        elif net_margin < 25:
            return f"🟡 RED LINE APPROACHING: Net margin {net_margin:.1f}% - Within 5% of critical floor. Increase revenue or reduce costs immediately."
        elif net_margin < 30:
            return f"🟡 CAUTION: Net margin {net_margin:.1f}% - Monitor closely. Any decline triggers escalation."
        else:
            return f"✅ HEALTHY: Net margin {net_margin:.1f}% - All systems nominal."

    @staticmethod
    def hourly_partner_check(db: Session, tenant_id) -> List[Dict[str, Any]]:
        """Check every partner's P&L; return the escalations and caution flags."""
        from app.models.user import Users

        partners = db.query(Users).filter(
            Users.tenant_id == tenant_id,
            Users.UserRole == roles.PARTNER
        ).all()

        results = []
        for partner in partners:
            pl = FinanceAgent.calculate_real_time_partner_pl(db, tenant_id, partner.UserID)
            margin = pl["net_profit"]["margin_pct"]
            if pl.get("escalation"):
                results.append({
                    "partner": partner.UserName,
                    "partner_id": partner.UserID,
                    "status": "ESCALATION_TRIGGERED",
                    "net_margin": margin,
                    "message": pl["escalation_message"],
                    "action": "ALERT_CEO_CFO",
                })
            elif margin < 30:
                results.append({
                    "partner": partner.UserName,
                    "partner_id": partner.UserID,
                    "status": "CAUTION",
                    "net_margin": margin,
                    "action": "MONITOR",
                })
        return results

    @staticmethod
    def forecast_margin_risk(db: Session, tenant_id, partner_id: str, days_ahead: int = 7) -> Dict[str, Any]:
        """Project margin days_ahead from the last 7 days of invoicing vs payroll run-rate."""
        current_pl = FinanceAgent.calculate_real_time_partner_pl(db, tenant_id, partner_id)
        current_margin = current_pl["net_profit"]["margin_pct"]
        bu_ids = partner_bu_ids(db, partner_id)

        week_ago = datetime.utcnow() - timedelta(days=7)
        daily_revenue = (_invoice_cents(db, bu_ids, week_ago) / 100 / 7) if bu_ids else 0
        monthly_payroll = (_payroll_usd(db, bu_ids, sales=False) + _payroll_usd(db, bu_ids, sales=True)) if bu_ids else 0
        daily_cost = monthly_payroll / 30

        forecast_revenue = daily_revenue * days_ahead
        forecast_cost = daily_cost * days_ahead
        forecast_margin = ((forecast_revenue - forecast_cost) / forecast_revenue * 100) if forecast_revenue > 0 else 0

        risk_level = "🟢 SAFE" if forecast_margin >= 25 else "🟡 AT RISK" if forecast_margin >= 20 else "🔴 CRITICAL"
        return {
            "current_margin": round(current_margin, 1),
            "forecast_days": days_ahead,
            "forecast_margin": round(forecast_margin, 1),
            "risk_level": risk_level,
            "recommendation": FinanceAgent._get_forecast_recommendation(current_margin, forecast_margin, days_ahead),
        }

    @staticmethod
    def _get_forecast_recommendation(current: float, forecast: float, days_ahead: int = 7) -> str:
        if forecast < 25:
            return f"🔴 CRITICAL: Forecast margin {forecast:.1f}% in {days_ahead} days. Take action NOW before hitting floor."
        elif forecast < current:
            return f"🟡 DECLINING: Forecast margin {forecast:.1f}% (down from {current:.1f}%). Investigate cost increases or revenue gaps."
        elif forecast >= 30:
            return f"✅ STABLE: Forecast margin {forecast:.1f}%. Maintain current execution."
        else:
            return f"🟡 CAUTION: Forecast margin {forecast:.1f}%. Watch closely, any new costs trigger escalation."

    @staticmethod
    def detect_cost_anomalies(db: Session, tenant_id, partner_id: str) -> List[Dict[str, Any]]:
        """Flag this week's unusually large invoices in the partner's BUs for review."""
        bu_ids = partner_bu_ids(db, partner_id)
        if not bu_ids:
            return []
        today = datetime.utcnow()
        week_start = today - timedelta(days=today.weekday())

        rows = db.query(Invoice, Client.company_name).join(Client, Client.id == Invoice.client_id).filter(
            Client.business_unit_id.in_(bu_ids),
            Invoice.created_at >= week_start,
            Invoice.total_usd_cents > LARGE_INVOICE_USD * 100,
        ).all()
        return [
            {
                "type": "LARGE_INVOICE",
                "invoice_id": invoice.id,
                "invoice_amount": f"${invoice.total_usd_cents / 100:,.0f}",
                "client": client_name,
                "status": invoice.status,
                "date": invoice.created_at.date().isoformat() if invoice.created_at else None,
                "action": f"Review: invoice over ${LARGE_INVOICE_USD:,}",
            }
            for invoice, client_name in rows
        ]
