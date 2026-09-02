"""
import logging
Finance Agent - Constant Vigilance Over Profitability

This agent is "smelling everyone's ass every second of their living" -
relentlessly monitoring financial metrics, identifying risks,
escalating immediately when profitability floor (<25% net profit) is breached.

The Finance Agent is:
- Always watching
- Always calculating
- Always ready to escalate
- Unapologetic about protection of the 25% floor

It doesn't care about excuses, deadlines, or strategic plans.
If net profit < 25%, it sounds the alarm immediately.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.opportunity import Opportunity
from app.models.invoice import Invoice
from app.models.employee import Employee
from app.models.business_unit import BusinessUnit
from app.core.logging import logger

logger = logging.getLogger(__name__)

class FinanceAgent:
    """
    Finance Agent - Real-time Profitability Monitoring

    Monitors profitability metrics CONSTANTLY:
    - Hourly P&L calculations for each partner
    - Immediate escalation if <25% net profit
    - Weekly forecasting to predict margin misses
    - Cost tracking and anomaly detection
    """

    @staticmethod
    def calculate_real_time_partner_pl(db: Session, tenant_id: str, partner_id: str) -> Dict[str, Any]:
        """
        Calculate CURRENT net profit for partner (not just end-of-week).

        This runs continuously - whenever anyone makes a transaction,
        the P&L instantly updates.
        """

        # Current month YTD
        today = datetime.utcnow()
        month_start = datetime(today.year, today.month, 1)

        # Revenue: All invoices paid + pending (recognized upon invoice)
        revenue_cents = db.query(func.sum(Invoice.invoice_amount_usd)).filter(
            Invoice.tenant_id == tenant_id,
            Invoice.partner_id == partner_id,
            Invoice.invoice_date >= month_start,
            Invoice.status.in_(["PAID", "PENDING"])
        ).scalar() or 0

        revenue = revenue_cents / 100

        # COGS: Employee salaries (monthly), contractor costs, infrastructure
        # Delivery team salaries for this partner
        delivery_team_salary = db.query(func.sum(Employee.monthly_salary_usd)).filter(
            Employee.partner_id == partner_id,
            Employee.role.in_(["DELIVERY", "CONTRACTOR"]),
            Employee.status == "ACTIVE"
        ).scalar() or 0

        # Contractor spend (from invoices to contractors)
        contractor_spend_cents = db.query(func.sum(Invoice.invoice_amount_usd)).filter(
            Invoice.tenant_id == tenant_id,
            Invoice.partner_id == partner_id,
            Invoice.vendor_type == "CONTRACTOR",
            Invoice.invoice_date >= month_start
        ).scalar() or 0

        contractor_spend = contractor_spend_cents / 100

        # Infrastructure costs (estimated: $2K/month base + variable)
        infrastructure_cost = 2000 + (revenue * 0.05)  # 5% of revenue for servers, tools, etc.

        total_cogs = delivery_team_salary + contractor_spend + infrastructure_cost

        # Gross Profit
        gross_profit = revenue - total_cogs
        gross_margin = (gross_profit / revenue * 100) if revenue > 0 else 0

        # Operating Expenses
        # Sales team salaries
        sales_team_salary = db.query(func.sum(Employee.monthly_salary_usd)).filter(
            Employee.partner_id == partner_id,
            Employee.role == "SALES",
            Employee.status == "ACTIVE"
        ).scalar() or 0

        # Sales & marketing spend
        marketing_spend = 3000  # Estimated monthly

        # G&A (office, tools, insurance, admin)
        ga_expense = 5000

        total_opex = sales_team_salary + marketing_spend + ga_expense

        # Operating Profit
        operating_profit = gross_profit - total_opex
        operating_margin = (operating_profit / revenue * 100) if revenue > 0 else 0

        # Net Profit
        net_profit = operating_profit  # Simplified (no other income/expense)
        net_margin = (net_profit / revenue * 100) if revenue > 0 else 0

        # Calculate health
        health_status = "🟢 HEALTHY" if net_margin >= 25 else "🟡 CAUTION" if net_margin >= 20 else "🔴 CRITICAL"
        escalation_needed = net_margin < 25

        return {
            "partner_id": partner_id,
            "reporting_time": today.isoformat(),
            "period": f"MTD (since {month_start.date()})",
            "revenue": {
                "total": f"${revenue:,.0f}",
                "invoices_paid": 0,  # Count from DB
                "invoices_pending": 0,
                "average_deal_size": f"${revenue / max(1, 5):,.0f}"  # Estimate
            },
            "cogs": {
                "delivery_team_salary": f"${delivery_team_salary:,.0f}",
                "contractor_spend": f"${contractor_spend:,.0f}",
                "infrastructure": f"${infrastructure_cost:,.0f}",
                "total_cogs": f"${total_cogs:,.0f}",
                "cogs_pct_revenue": round(total_cogs / revenue * 100, 1) if revenue > 0 else 0
            },
            "gross_profit": {
                "amount": f"${gross_profit:,.0f}",
                "margin_pct": round(gross_margin, 1),
                "target": 70,
                "status": "✅" if gross_margin >= 70 else "⚠️"
            },
            "opex": {
                "sales_team_salary": f"${sales_team_salary:,.0f}",
                "marketing": f"${marketing_spend:,.0f}",
                "ga_expense": f"${ga_expense:,.0f}",
                "total_opex": f"${total_opex:,.0f}",
                "opex_pct_revenue": round(total_opex / revenue * 100, 1) if revenue > 0 else 0
            },
            "operating_profit": {
                "amount": f"${operating_profit:,.0f}",
                "margin_pct": round(operating_margin, 1),
                "target": 20,
                "status": "✅" if operating_margin >= 20 else "⚠️"
            },
            "net_profit": {
                "amount": f"${net_profit:,.0f}",
                "margin_pct": round(net_margin, 1),
                "target": 25,  # The non-negotiable floor
                "status": health_status
            },
            "escalation": escalation_needed,
            "escalation_message": FinanceAgent._get_escalation_message(net_margin, revenue)
        }

    @staticmethod
    def _get_escalation_message(net_margin: float, revenue: float) -> str:
        """Generate escalation message if profitability is at risk."""

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
    def hourly_partner_check(db: Session, tenant_id: str) -> List[Dict[str, Any]]:
        """
        Run HOURLY: Check ALL partners for profitability issues.

        This is the relentless monitoring system.
        Every hour, every partner's P&L is calculated.
        If anything looks wrong, immediate alert.
        """

        from app.models.user import Users

        partners = db.query(Users).filter(
            Users.tenant_id == tenant_id,
            Users.UserRole == "Partner"
        ).all()

        results = []
        escalations = []

        for partner in partners:
            pl = FinanceAgent.calculate_real_time_partner_pl(db, tenant_id, partner.UserID)

            if pl.get("escalation"):
                escalations.append({
                    "partner_id": partner.UserID,
                    "partner_name": partner.UserName,
                    "net_margin": pl["net_profit"]["margin_pct"],
                    "message": pl["escalation_message"],
                    "timestamp": datetime.utcnow().isoformat()
                })

                results.append({
                    "partner": partner.UserName,
                    "status": "ESCALATION_TRIGGERED",
                    "net_margin": pl["net_profit"]["margin_pct"],
                    "action": "ALERT_CEO_CFO"
                })
            elif pl["net_profit"]["margin_pct"] < 30:
                # Caution zone - flag for monitoring
                results.append({
                    "partner": partner.UserName,
                    "status": "CAUTION",
                    "net_margin": pl["net_profit"]["margin_pct"],
                    "action": "MONITOR"
                })

        return results

    @staticmethod
    def forecast_margin_risk(db: Session, tenant_id: str, partner_id: str, days_ahead: int = 7) -> Dict[str, Any]:
        """
        Look ahead: Will we miss the 25% floor in the next N days?

        This is predictive - the Finance Agent watches the future,
        not just the present.
        """

        # Current trajectory
        current_pl = FinanceAgent.calculate_real_time_partner_pl(db, tenant_id, partner_id)
        current_margin = current_pl["net_profit"]["margin_pct"]

        # Get recent trend (last 7 days)
        today = datetime.utcnow()
        week_ago = today - timedelta(days=7)

        # Revenue trend
        recent_revenue = db.query(func.sum(Invoice.invoice_amount_usd)).filter(
            Invoice.tenant_id == tenant_id,
            Invoice.partner_id == partner_id,
            Invoice.invoice_date >= week_ago
        ).scalar() or 0

        daily_revenue = recent_revenue / 100 / 7

        # Cost trend
        recent_costs = db.query(func.sum(Invoice.invoice_amount_usd)).filter(
            Invoice.tenant_id == tenant_id,
            Invoice.partner_id == partner_id,
            Invoice.vendor_type == "CONTRACTOR",
            Invoice.invoice_date >= week_ago
        ).scalar() or 0

        daily_cost = recent_costs / 100 / 7

        # Forecast
        forecast_revenue = daily_revenue * days_ahead
        forecast_cost = daily_cost * days_ahead
        forecast_margin = ((forecast_revenue - forecast_cost) / forecast_revenue * 100) if forecast_revenue > 0 else 0

        risk_level = "🟢 SAFE" if forecast_margin >= 25 else "🟡 AT RISK" if forecast_margin >= 20 else "🔴 CRITICAL"

        return {
            "current_margin": round(current_margin, 1),
            "forecast_days": days_ahead,
            "forecast_margin": round(forecast_margin, 1),
            "risk_level": risk_level,
            "recommendation": FinanceAgent._get_forecast_recommendation(current_margin, forecast_margin)
        }

    @staticmethod
    def _get_forecast_recommendation(current: float, forecast: float) -> str:
        """Get recommendation based on forecast."""

        if forecast < 25:
            return f"🔴 CRITICAL: Forecast margin {forecast:.1f}% in {7} days. Take action NOW before hitting floor."
        elif forecast < current:
            return f"🟡 DECLINING: Forecast margin {forecast:.1f}% (down from {current:.1f}%). Investigate cost increases or revenue gaps."
        elif forecast >= 30:
            return f"✅ STABLE: Forecast margin {forecast:.1f}%. Maintain current execution."
        else:
            return f"🟡 CAUTION: Forecast margin {forecast:.1f}%. Watch closely, any new costs trigger escalation."

    @staticmethod
    def detect_cost_anomalies(db: Session, tenant_id: str, partner_id: str) -> List[Dict[str, Any]]:
        """
        Real-time anomaly detection: Is someone spending unusually?

        The Finance Agent catches spending red flags instantly.
        """

        today = datetime.utcnow()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=7)

        # Get all invoices this week
        invoices = db.query(Invoice).filter(
            Invoice.tenant_id == tenant_id,
            Invoice.partner_id == partner_id,
            Invoice.invoice_date >= week_start,
            Invoice.invoice_date <= week_end
        ).all()

        anomalies = []

        for invoice in invoices:
            # Is this invoice unusually large?
            if invoice.invoice_amount_usd > 10000:  # $10K threshold
                anomalies.append({
                    "type": "LARGE_INVOICE",
                    "invoice_amount": f"${invoice.invoice_amount_usd:,.0f}",
                    "vendor": invoice.vendor_name,
                    "date": invoice.invoice_date.date().isoformat(),
                    "action": "Requires Partner approval for >$10K spend"
                })

            # Is this contractor spend rising rapidly?
            if invoice.vendor_type == "CONTRACTOR":
                anomalies.append({
                    "type": "CONTRACTOR_SPEND",
                    "amount": f"${invoice.invoice_amount_usd:,.0f}",
                    "vendor": invoice.vendor_name,
                    "warning": "Monitor: Contractor spend impacts COGS. Is this temporary or permanent?"
                })

        return anomalies
