"""
Agent Pyramid Reporting System - Hierarchical Accountability

Structure:
  CEO (Executive Dashboard)
    ↑ receives weekly summaries
    ↓ sends feedback
  Partners (Weekly Consolidation)
    ↑ receives BU reports Thursday morning
    ↓ sends feedback
  BU Heads (Thursday Morning Report)
    ↑ executes every Thursday 9AM
    ↓ sends to Partner

Flow:
1. Thursday 9AM: BU Head Agent generates weekly report
   - Delivery cadence %
   - Utilization %
   - New hires/departures
   - Revenue generated
   - KPI vs target
   - Issues & risks

2. Thursday 10AM: Partner Weekly Consolidation Agent receives BU reports
   - Collects reports from all BUs
   - Calculates rolled-up metrics
   - Identifies red flags across BUs
   - Generates partner-level summary
   - Sends notification to Partner

3. Thursday 4PM/Friday 9AM: Partner reports to CEO
   - Executive summary (1-page)
   - All partner's BU performance
   - Consolidated pipeline
   - Issues & escalations
   - Recommendations

4. CEO Executive Dashboard updated
   - All partners' reports visible
   - Drill-down to BU level
   - Risk dashboard (red flags)
   - Weekly targets vs actual

Feedback Loop:
- CEO gives feedback on weekly report
- Partner distributes feedback to BU Heads
- BU Heads adjust execution based on feedback
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.business_unit import BusinessUnit
from app.models.employee import Employee
from app.models.user import Users
from app.models.opportunity import Opportunity
from app.models.project import Project
from app.core.logging import logger


class BUWeeklyReportAgent:
    """
    BU Weekly Report Agent - Runs every Thursday 9AM

    Question: How did this BU perform this week?
    """

    @staticmethod
    def generate_bu_weekly_report(db: Session, tenant_id: str, bu_id: str, reporting_week: str = None) -> Dict[str, Any]:
        """
        Generate comprehensive BU weekly report.

        reporting_week format: "2026-W34" (week 34 of 2026)
        If None, uses current week (Monday-Sunday)
        """

        bu = db.query(BusinessUnit).filter(
            BusinessUnit.id == bu_id,
            BusinessUnit.tenant_id == tenant_id
        ).first()

        if not bu:
            return {"status": "error", "message": "BU not found"}

        today = datetime.utcnow()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=7)

        # 1. DELIVERY CADENCE
        projects = db.query(Project).filter(
            Project.tenant_id == tenant_id,
            Project.business_unit_id == bu_id,
            Project.end_date >= week_start,
            Project.end_date <= week_end
        ).all()

        on_time = sum(1 for p in projects if p.end_date and p.end_date <= today)
        delivery_cadence = (on_time / len(projects) * 100) if len(projects) > 0 else 100

        # 2. UTILIZATION
        total_employees = db.query(func.count(Employee.id)).filter(
            Employee.business_unit_id == bu_id,
            Employee.status == "ACTIVE"
        ).scalar() or 1

        allocated = db.query(func.count(Employee.id)).filter(
            Employee.business_unit_id == bu_id,
            Employee.status == "ACTIVE",
            Employee.current_project_id.isnot(None)
        ).scalar() or 0

        utilization = (allocated / total_employees * 100) if total_employees > 0 else 0

        # 3. NEW HIRES / DEPARTURES
        new_hires = db.query(func.count(Employee.id)).filter(
            Employee.business_unit_id == bu_id,
            Employee.created_at >= week_start
        ).scalar() or 0

        departures = db.query(func.count(Employee.id)).filter(
            Employee.business_unit_id == bu_id,
            Employee.status == "INACTIVE",
            Employee.updated_at >= week_start
        ).scalar() or 0

        # 4. REVENUE GENERATED
        revenue_cents = db.query(func.sum(Opportunity.deal_size_usd)).filter(
            Opportunity.tenant_id == tenant_id,
            Opportunity.partner_id.in_(
                db.query(Users.UserID).filter(Users.UserRoleID == bu_id)
            ),
            Opportunity.close_date >= week_start,
            Opportunity.close_date <= week_end,
            Opportunity.status == "won"
        ).scalar() or 0

        revenue = revenue_cents / 100

        # 5. OPPORTUNITIES ADDED
        opportunities_added = db.query(func.count(Opportunity.id)).filter(
            Opportunity.tenant_id == tenant_id,
            Opportunity.partner_id.in_(
                db.query(Users.UserID).filter(Users.UserRoleID == bu_id)
            ),
            Opportunity.created_at >= week_start,
            Opportunity.created_at <= week_end
        ).scalar() or 0

        # 6. PIPELINE VALUE
        pipeline_cents = db.query(func.sum(Opportunity.deal_size_usd)).filter(
            Opportunity.tenant_id == tenant_id,
            Opportunity.partner_id.in_(
                db.query(Users.UserID).filter(Users.UserRoleID == bu_id)
            ),
            Opportunity.status.in_(["prospecting", "proposal", "negotiation"])
        ).scalar() or 0

        pipeline = pipeline_cents / 100

        # Status
        health_score = (delivery_cadence * 0.3 + utilization * 0.3 + (revenue / 10000) * 0.2 + (new_hires * 10) * 0.2)
        status = "🟢 HEALTHY" if health_score >= 75 else "🟡 CAUTION" if health_score >= 50 else "🔴 CRITICAL"

        return {
            "week": f"{week_start.date()} to {week_end.date()}",
            "bu_id": bu_id,
            "bu_name": bu.name,
            "reporting_time": today.isoformat(),
            "metrics": {
                "delivery_cadence": {
                    "value": round(delivery_cadence, 1),
                    "unit": "%",
                    "target": "90%",
                    "status": "🟢" if delivery_cadence >= 90 else "🟡" if delivery_cadence >= 75 else "🔴"
                },
                "utilization": {
                    "value": round(utilization, 1),
                    "unit": "%",
                    "target": "75%",
                    "allocated": allocated,
                    "total": total_employees,
                    "status": "🟢" if utilization >= 75 else "🟡" if utilization >= 60 else "🔴"
                },
                "headcount": {
                    "new_hires": new_hires,
                    "departures": departures,
                    "net_change": new_hires - departures,
                    "total": total_employees,
                    "status": "🟢" if (new_hires - departures) > 0 else "🟡"
                },
                "revenue_this_week": {
                    "value": f"${revenue:,.0f}",
                    "opportunities_won": on_time,
                    "status": "🟢" if revenue > 0 else "🟡"
                },
                "opportunities": {
                    "added": opportunities_added,
                    "pipeline_value": f"${pipeline:,.0f}",
                    "pipeline_count": db.query(func.count(Opportunity.id)).filter(
                        Opportunity.tenant_id == tenant_id,
                        Opportunity.status.in_(["prospecting", "proposal", "negotiation"])
                    ).scalar() or 0,
                    "status": "🟢" if opportunities_added > 3 else "🟡" if opportunities_added > 0 else "🔴"
                }
            },
            "health_score": round(health_score, 1),
            "overall_status": status,
            "recommendation": BUWeeklyReportAgent._get_bu_recommendation(
                delivery_cadence, utilization, new_hires, departures, revenue, opportunities_added
            ),
            "escalations": BUWeeklyReportAgent._identify_escalations(
                delivery_cadence, utilization, (new_hires - departures), opportunities_added
            )
        }

    @staticmethod
    def _get_bu_recommendation(delivery: float, util: float, hires: int, dept: int, revenue: float, opps: int) -> str:
        """Get actionable recommendation for this BU."""

        if delivery < 85 and util < 70:
            return "⚠️ CRITICAL: Both delivery and utilization falling. Increase project resourcing urgently."
        elif delivery < 85:
            return f"🟡 DELIVERY RISK: {delivery:.0f}% on-time. Review project schedule and risk mitigation."
        elif util < 70:
            return f"🟡 UTILIZATION LOW: {util:.0f}% allocated. Find additional project work or adjust staffing."
        elif (hires - dept) < 0:
            return f"🟡 HEADCOUNT LOSS: Lost {dept - hires} people this week. Review retention risks."
        elif opps < 2:
            return f"🟡 SALES PIPELINE: Only {opps} opportunities added. Sales team needs coaching."
        else:
            return "✅ ALL TARGETS MET: Maintain current execution. No immediate issues."

    @staticmethod
    def _identify_escalations(delivery: float, util: float, net_hires: int, opps: int) -> List[str]:
        """Identify issues that need escalation to Partner."""

        escalations = []
        if delivery < 80:
            escalations.append("DELIVERY_MISS: Projects falling behind schedule")
        if util < 60:
            escalations.append("UTILIZATION_RISK: Resource underutilization may impact revenue")
        if net_hires < -1:
            escalations.append("ATTRITION_ALERT: Multiple departures this week")
        if opps < 1:
            escalations.append("SALES_PIPELINE_DRY: No new opportunities this week")
        return escalations


class PartnerWeeklyConsolidationAgent:
    """
    Partner Weekly Consolidation Agent - Runs Friday morning

    Question: How did all my BUs perform this week?

    Collects reports from all BUs, identifies red flags, sends to Partner.
    """

    @staticmethod
    def generate_partner_weekly_consolidation(db: Session, tenant_id: str, partner_id: str) -> Dict[str, Any]:
        """
        Generate consolidated weekly report for Partner (all BUs).
        """

        partner = db.query(Users).filter(
            Users.UserID == partner_id,
            Users.tenant_id == tenant_id
        ).first()

        if not partner:
            return {"status": "error", "message": "Partner not found"}

        # Get all BUs for this partner (assuming partner has business_unit_id or has assigned BUs)
        bus = db.query(BusinessUnit).filter(
            BusinessUnit.tenant_id == tenant_id
            # TODO: Add FK to user_roles or business_unit_managers
        ).all()

        # Generate BU reports for all BUs
        bu_reports = []
        escalations = []
        total_revenue = 0
        total_opps = 0

        for bu in bus:
            bu_report = BUWeeklyReportAgent.generate_bu_weekly_report(db, tenant_id, bu.id)
            if bu_report.get("status") == "success":
                bu_reports.append(bu_report)
                # Aggregate
                revenue_str = bu_report["metrics"]["revenue_this_week"]["value"].replace("$", "").replace(",", "")
                total_revenue += float(revenue_str) if revenue_str else 0
                total_opps += bu_report["metrics"]["opportunities"]["added"]
                escalations.extend(bu_report.get("escalations", []))

        # Calculate consolidated health
        avg_delivery = sum(b["metrics"]["delivery_cadence"]["value"] for b in bu_reports) / len(bu_reports) if bu_reports else 0
        avg_util = sum(b["metrics"]["utilization"]["value"] for b in bu_reports) / len(bu_reports) if bu_reports else 0
        consolidated_health = (avg_delivery * 0.4 + avg_util * 0.3 + (total_revenue / 50000) * 0.3)

        return {
            "week": bu_reports[0]["week"] if bu_reports else "N/A",
            "partner_id": partner_id,
            "partner_name": partner.UserName,
            "reporting_date": datetime.utcnow().isoformat(),
            "bu_count": len(bu_reports),
            "consolidated_metrics": {
                "avg_delivery_cadence": round(avg_delivery, 1),
                "avg_utilization": round(avg_util, 1),
                "total_revenue": f"${total_revenue:,.0f}",
                "total_opportunities": total_opps,
                "health_status": "🟢 HEALTHY" if consolidated_health >= 75 else "🟡 CAUTION" if consolidated_health >= 50 else "🔴 CRITICAL"
            },
            "bu_reports": bu_reports,
            "escalations": list(set(escalations)),  # Deduplicate
            "recommendation": PartnerWeeklyConsolidationAgent._get_partner_recommendation(
                consolidated_health, total_revenue, total_opps, len(escalations)
            ),
            "action_items": PartnerWeeklyConsolidationAgent._generate_action_items(
                bu_reports, escalations
            )
        }

    @staticmethod
    def _get_partner_recommendation(health: float, revenue: float, opps: int, escalation_count: int) -> str:
        """Get recommendation for Partner on what to do."""

        if escalation_count >= 3:
            return f"🔴 CRITICAL: {escalation_count} major escalations this week. Emergency coordination call required."
        elif health < 60:
            return f"🟡 OVERALL CAUTION: Consolidated health score {health:.0f}. Review BU strategies and resource allocation."
        elif opps < 3:
            return f"🟡 SALES PIPELINE WEAK: Only {opps} opportunities added across all BUs. Need sales activity boost."
        elif revenue > 50000:
            return f"✅ STRONG WEEK: ${revenue:,.0f} revenue + {opps} new opportunities. Maintain momentum."
        else:
            return f"✅ ON TRACK: All BUs performing within targets. Continue current execution."

    @staticmethod
    def _generate_action_items(bu_reports: List[Dict], escalations: List[str]) -> List[Dict]:
        """Generate specific action items for Partner."""

        actions = []

        # If any BU delivery < 85%, create action
        for bu_report in bu_reports:
            delivery = bu_report["metrics"]["delivery_cadence"]["value"]
            if delivery < 85:
                actions.append({
                    "priority": "HIGH",
                    "bu": bu_report["bu_name"],
                    "action": f"Address delivery miss ({delivery:.0f}%). Review project schedule & resource plan.",
                    "owner": f"BU Head - {bu_report['bu_name']}",
                    "due_date": "2026-08-30"  # Next Friday
                })

        # If escalations exist, prioritize
        for escalation in escalations:
            if escalation.startswith("ATTRITION"):
                actions.append({
                    "priority": "CRITICAL",
                    "action": "Address employee attrition. Conduct retention reviews.",
                    "owner": "HR + BU Heads",
                    "due_date": "Immediate"
                })

        return actions


class CEOExecutiveDashboardAgent:
    """
    CEO Executive Dashboard Agent - Runs Friday afternoon

    Question: How did all my Partners perform this week?

    Consolidates all partner reports, identifies company-wide risks.
    """

    @staticmethod
    def generate_ceo_executive_summary(db: Session, tenant_id: str) -> Dict[str, Any]:
        """
        Generate executive summary for CEO across all Partners.
        """

        # Get all Partners
        partners = db.query(Users).filter(
            Users.tenant_id == tenant_id,
            Users.UserRole == "Partner"
        ).all()

        # Generate partner reports
        partner_reports = []
        total_company_revenue = 0
        critical_issues = []

        for partner in partners:
            partner_report = PartnerWeeklyConsolidationAgent.generate_partner_weekly_consolidation(
                db, tenant_id, partner.UserID
            )
            if partner_report.get("status") != "error":
                partner_reports.append(partner_report)
                # Aggregate
                revenue_str = partner_report["consolidated_metrics"]["total_revenue"].replace("$", "").replace(",", "")
                total_company_revenue += float(revenue_str) if revenue_str else 0
                critical_issues.extend(partner_report.get("escalations", []))

        # Company-wide health calculation
        company_health_score = sum(
            float(p["consolidated_metrics"]["health_status"][0:2].replace("🟢", "90").replace("🟡", "60").replace("🔴", "30"))
            for p in partner_reports
        ) / len(partner_reports) if partner_reports else 0

        return {
            "reporting_date": datetime.utcnow().isoformat(),
            "executive_summary": {
                "company_health": "🟢 HEALTHY" if company_health_score >= 75 else "🟡 CAUTION" if company_health_score >= 50 else "🔴 CRITICAL",
                "health_score": round(company_health_score, 1),
                "total_revenue_ytd": f"${total_company_revenue:,.0f}",
                "partner_count": len(partner_reports),
                "critical_issues": len(critical_issues)
            },
            "partner_scorecards": partner_reports,
            "company_risks": CEOExecutiveDashboardAgent._identify_company_risks(partner_reports, critical_issues),
            "ceo_recommendation": CEOExecutiveDashboardAgent._get_ceo_action(
                company_health_score, len(critical_issues), total_company_revenue
            ),
            "next_actions": CEOExecutiveDashboardAgent._generate_ceo_actions(
                partner_reports, critical_issues
            )
        }

    @staticmethod
    def _identify_company_risks(partner_reports: List[Dict], escalations: List[str]) -> List[str]:
        """Identify company-wide risks from partner reports."""

        risks = []

        critical_partner_count = sum(1 for p in partner_reports if "CRITICAL" in p["consolidated_metrics"]["health_status"])
        if critical_partner_count > 1:
            risks.append(f"MULTI-PARTNER_RISK: {critical_partner_count} partners in critical status")

        if len(escalations) > 5:
            risks.append(f"ESCALATION_SURGE: {len(escalations)} escalations across company")

        low_revenue_partner = [p for p in partner_reports if "revenue_ytd" in p and float(p.get("total_revenue", "$0").replace("$", "").replace(",", "")) < 10000]
        if low_revenue_partner:
            risks.append(f"UNDERPERFORMING_PARTNERS: {len(low_revenue_partner)} partners below ${10000:,.0f}")

        return risks

    @staticmethod
    def _get_ceo_action(health: float, critical_issues: int, revenue: float) -> str:
        """Get CEO's top priority action."""

        if critical_issues > 5:
            return "🔴 IMMEDIATE: Emergency all-hands call to address critical escalations."
        elif health < 60:
            return f"🟡 STRATEGIC: Company health at {health:.0f}. Convene partner leadership for reset."
        elif revenue < 100000:
            return f"🟡 REVENUE RISK: Weekly revenue ${revenue:,.0f} below $100K target. Increase sales focus."
        else:
            return f"✅ ON TRACK: Company health {health:.0f}, revenue ${revenue:,.0f}. Maintain focus."

    @staticmethod
    def _generate_ceo_actions(partner_reports: List[Dict], escalations: List[str]) -> List[Dict]:
        """Generate specific CEO action items."""

        actions = []

        # If any partner critical, create escalation
        for partner_report in partner_reports:
            if "CRITICAL" in partner_report["consolidated_metrics"]["health_status"]:
                actions.append({
                    "priority": "CRITICAL",
                    "item": f"Partner {partner_report['partner_name']} in critical status",
                    "action": "Schedule urgent partner call to understand blockers & provide support",
                    "owner": "CEO",
                    "due_date": "Today"
                })

        # If revenue trending down, flag
        if partner_reports:
            actions.append({
                "priority": "HIGH",
                "item": "Weekly revenue review",
                "action": f"Review partner revenue trends. Current: ${sum(float(p['consolidated_metrics']['total_revenue'].replace('$', '').replace(',', '')) for p in partner_reports):,.0f}",
                "owner": "CEO + CFO",
                "due_date": "Friday 4PM"
            })

        return actions
