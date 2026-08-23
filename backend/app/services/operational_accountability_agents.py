"""
Operational Accountability Agents - Daily Business Health Checks

Three agents that watch the business operations:
1. Partner ROI Agent - Track partner sales progress vs targets
2. BU Head Agent - Track delivery cadence, utilization, KPIs
3. Employee Health Agent - Monitor wellbeing, engagement, motivation
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.employee import Employee
from app.models.opportunity import Opportunity
from app.models.project import Project
from app.models.business_unit import BusinessUnit
from app.models.user import Users
from app.core.logging import logger


class PartnerROIAgent:
    """
    Partner ROI Agent - Daily partner sales accountability.

    Question: Did the partner do any progress this week on sales?
    What is the target vs where they are?

    Tracks:
    - Partner revenue generated this week
    - Revenue target for week/month/year
    - Gap analysis (ahead or behind)
    - Deal pipeline (what's coming next)
    - ROI (revenue generated / cost of partner's team)
    """

    @staticmethod
    def get_partner_weekly_summary(db: Session, tenant_id: str, partner_id: str) -> Dict[str, Any]:
        """
        Get ONE partner's weekly sales progress.

        Question: Did this partner hit their target this week?
        """

        partner = db.query(Users).filter(
            Users.UserID == partner_id,
            Users.tenant_id == tenant_id
        ).first()

        if not partner:
            return {"status": "error", "message": "Partner not found"}

        # Get this week's dates
        today = datetime.utcnow()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=7)

        # Revenue generated THIS WEEK by this partner's clients/deals
        weekly_revenue_cents = db.query(func.sum(Opportunity.deal_size_usd)).filter(
            Opportunity.partner_owner_id == partner_id,
            Opportunity.tenant_id == tenant_id,
            Opportunity.close_date >= week_start,
            Opportunity.close_date < week_end,
            Opportunity.status == "won"
        ).scalar() or 0

        weekly_revenue = weekly_revenue_cents / 100  # Convert cents to dollars

        # Weekly target (assume annual target / 52)
        annual_target = 500000  # Example: $500K annual target per partner
        weekly_target = annual_target / 52

        # Pipeline (deals in progress)
        pipeline_value = db.query(func.sum(Opportunity.deal_size_usd)).filter(
            Opportunity.partner_owner_id == partner_id,
            Opportunity.tenant_id == tenant_id,
            Opportunity.status.in_(["prospecting", "proposal", "negotiation"])
        ).scalar() or 0

        pipeline_value_dollars = pipeline_value / 100

        # Progress calculation
        ytd_revenue = db.query(func.sum(Opportunity.deal_size_usd)).filter(
            Opportunity.partner_owner_id == partner_id,
            Opportunity.tenant_id == tenant_id,
            Opportunity.close_date >= datetime(today.year, 1, 1),
            Opportunity.status == "won"
        ).scalar() or 0

        ytd_revenue_dollars = ytd_revenue / 100
        ytd_target = annual_target * (today.timetuple().tm_yday / 365)
        ytd_progress_pct = (ytd_revenue_dollars / ytd_target * 100) if ytd_target > 0 else 0

        # Status
        weekly_progress = (weekly_revenue / weekly_target * 100) if weekly_target > 0 else 0
        if weekly_progress >= 100:
            status = "🟢 ON TARGET"
        elif weekly_progress >= 70:
            status = "🟡 CAUTION"
        else:
            status = "🔴 BEHIND"

        return {
            "partner_id": partner_id,
            "partner_name": partner.UserName,
            "week": f"{week_start.date()} to {week_end.date()}",
            "this_week": {
                "revenue_generated": f"${weekly_revenue:,.0f}",
                "target": f"${weekly_target:,.0f}",
                "progress": round(weekly_progress, 1),
                "status": status,
                "gap": f"${weekly_target - weekly_revenue:,.0f}" if weekly_revenue < weekly_target else f"+${weekly_revenue - weekly_target:,.0f}"
            },
            "year_to_date": {
                "revenue_generated": f"${ytd_revenue_dollars:,.0f}",
                "target": f"${ytd_target:,.0f}",
                "progress": round(ytd_progress_pct, 1),
                "status": "🟢 ON TRACK" if ytd_progress_pct >= 100 else "🟡 SLIGHT LAG" if ytd_progress_pct >= 80 else "🔴 BEHIND"
            },
            "pipeline": {
                "active_deals": f"${pipeline_value_dollars:,.0f}",
                "expected_next_week": f"${pipeline_value_dollars / 5:,.0f}" if pipeline_value_dollars > 0 else "$0",
                "forecast_next_30_days": f"${pipeline_value_dollars / 5:,.0f}"
            },
            "recommendation": PartnerROIAgent._get_recommendation(
                weekly_progress, ytd_progress_pct, pipeline_value_dollars
            )
        }

    @staticmethod
    def _get_recommendation(weekly_progress: float, ytd_progress: float, pipeline: float) -> str:
        """Get Flash's recommendation for this partner."""

        if weekly_progress < 50:
            return "🚨 CRITICAL: Partner behind on weekly target. Check pipeline health and sales activity."
        elif ytd_progress < 70:
            return "⚠️ HIGH: Partner behind on YTD target. Need acceleration plan."
        elif pipeline < 50000:
            return "⚠️ MEDIUM: Pipeline weak. Partner needs to be sourcing more deals."
        else:
            return "✅ ON TRACK: Partner on target. Monitor next week."

    @staticmethod
    def get_all_partners_summary(db: Session, tenant_id: str) -> Dict[str, Any]:
        """
        Get summary of ALL partners' sales progress.

        Shows: Who's hitting targets? Who's behind? Who needs help?
        """

        partners = db.query(Users).filter(
            Users.tenant_id == tenant_id,
            Users.UserRole.in_(["Partner", "BU Head"])
        ).all()

        summaries = []
        for partner in partners:
            summary = PartnerROIAgent.get_partner_weekly_summary(db, tenant_id, partner.UserID)
            summaries.append(summary)

        # Aggregate stats
        total_weekly_target = sum(
            float(s["this_week"]["target"].replace("$", "").replace(",", ""))
            for s in summaries if "error" not in s
        )
        total_weekly_revenue = sum(
            float(s["this_week"]["revenue_generated"].replace("$", "").replace(",", ""))
            for s in summaries if "error" not in s
        )

        return {
            "status": "success",
            "reporting_week": datetime.utcnow().date().isoformat(),
            "partners": summaries,
            "aggregate": {
                "total_weekly_target": f"${total_weekly_target:,.0f}",
                "total_weekly_revenue": f"${total_weekly_revenue:,.0f}",
                "aggregate_progress": round((total_weekly_revenue / total_weekly_target * 100), 1) if total_weekly_target > 0 else 0,
                "partners_on_target": sum(1 for s in summaries if "ON TARGET" in s["this_week"]["status"]),
                "partners_behind": sum(1 for s in summaries if "BEHIND" in s["this_week"]["status"])
            },
            "action": "Partners behind target need immediate support or coaching"
        }


class BUHeadAgent:
    """
    BU Head Agent - Daily business unit accountability.

    Question: How is each BU doing on delivery cadence, utilization, and KPIs?

    Tracks:
    - Projects on-time delivery %
    - Resource utilization rate (target: 75%+)
    - Team KPIs (velocity, quality, etc.)
    - Budget vs spend
    - Team growth progress
    """

    @staticmethod
    def get_bu_daily_health(db: Session, tenant_id: str, bu_id: str) -> Dict[str, Any]:
        """
        Get ONE BU's daily health check.

        Question: Is this BU healthy? On track? Any issues?
        """

        bu = db.query(BusinessUnit).filter(
            BusinessUnit.id == bu_id,
            BusinessUnit.tenant_id == tenant_id
        ).first()

        if not bu:
            return {"status": "error", "message": "BU not found"}

        # Delivery Cadence
        today = datetime.utcnow()
        thirty_days_ago = today - timedelta(days=30)

        projects = db.query(Project).filter(
            Project.tenant_id == tenant_id,
            Project.business_unit_id == bu_id
        ).all()

        on_time = sum(1 for p in projects if p.end_date and p.end_date <= today)
        late = sum(1 for p in projects if p.end_date and p.end_date > today)
        delivery_rate = (on_time / (on_time + late) * 100) if (on_time + late) > 0 else 0

        # Utilization
        total_employees = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.business_unit_id == bu_id,
            Employee.status == "ACTIVE"
        ).scalar() or 0

        allocated = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.business_unit_id == bu_id,
            Employee.status == "ACTIVE",
            Employee.current_project_id.isnot(None)
        ).scalar() or 0

        utilization_pct = (allocated / total_employees * 100) if total_employees > 0 else 0

        # Team Growth (last 30 days)
        new_hires = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.business_unit_id == bu_id,
            Employee.created_at >= thirty_days_ago
        ).scalar() or 0

        departures = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.business_unit_id == bu_id,
            Employee.status == "DEPARTED",
            Employee.created_at >= thirty_days_ago  # Approximate
        ).scalar() or 0

        # CORE certification
        core_certified = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.business_unit_id == bu_id,
            Employee.is_core_certified == True
        ).scalar() or 0

        core_pct = (core_certified / total_employees * 100) if total_employees > 0 else 0

        # Revenue generated this month
        monthly_revenue = db.query(func.sum(Opportunity.deal_size_usd)).filter(
            Opportunity.tenant_id == tenant_id,
            Opportunity.close_date >= thirty_days_ago,
            Opportunity.status == "won"
            # TODO: Filter by BU
        ).scalar() or 0

        monthly_revenue_dollars = monthly_revenue / 100

        return {
            "bu_id": bu_id,
            "bu_name": bu.name,
            "date": today.date().isoformat(),
            "delivery_cadence": {
                "on_time_projects": on_time,
                "late_projects": late,
                "on_time_percentage": round(delivery_rate, 1),
                "status": "🟢 HEALTHY" if delivery_rate >= 90 else "🟡 WARNING" if delivery_rate >= 75 else "🔴 CRITICAL"
            },
            "utilization": {
                "total_employees": total_employees,
                "allocated": allocated,
                "on_bench": total_employees - allocated,
                "utilization_percentage": round(utilization_pct, 1),
                "target": 75,
                "status": "🟢 HEALTHY" if utilization_pct >= 75 else "🟡 WARNING" if utilization_pct >= 65 else "🔴 CRITICAL"
            },
            "team_health": {
                "new_hires_30d": new_hires,
                "departures_30d": departures,
                "core_certified": core_certified,
                "core_percentage": round(core_pct, 1),
                "core_target": 60
            },
            "financial": {
                "revenue_30d": f"${monthly_revenue_dollars:,.0f}",
                "revenue_target_30d": "$250000"  # Example
            },
            "recommendation": BUHeadAgent._get_recommendation(
                delivery_rate, utilization_pct, core_pct, new_hires, departures
            )
        }

    @staticmethod
    def _get_recommendation(delivery: float, utilization: float, core_pct: float, hires: int, departures: int) -> str:
        """Get Flash's recommendation for this BU."""

        issues = []
        if delivery < 75:
            issues.append("Delivery on-time % below 75%")
        if utilization < 65:
            issues.append("Utilization below 65% (target: 75%)")
        if core_pct < 50:
            issues.append("CORE certification below 50%")
        if departures > hires + 1:
            issues.append("Departures exceeding new hires")

        if not issues:
            return "✅ HEALTHY: BU on track all metrics"
        else:
            return f"⚠️ ISSUES: {', '.join(issues)}"

    @staticmethod
    def get_all_bu_summary(db: Session, tenant_id: str) -> Dict[str, Any]:
        """Get summary of ALL BUs."""

        bus = db.query(BusinessUnit).filter(
            BusinessUnit.tenant_id == tenant_id
        ).all()

        summaries = []
        for bu in bus:
            summary = BUHeadAgent.get_bu_daily_health(db, tenant_id, bu.id)
            summaries.append(summary)

        return {
            "status": "success",
            "reporting_date": datetime.utcnow().date().isoformat(),
            "business_units": summaries,
            "aggregate": {
                "total_employees": sum(s["utilization"]["total_employees"] for s in summaries if "error" not in s),
                "total_allocated": sum(s["utilization"]["allocated"] for s in summaries if "error" not in s),
                "avg_utilization": round(sum(s["utilization"]["utilization_percentage"] for s in summaries if "error" not in s) / len([s for s in summaries if "error" not in s]), 1) if summaries else 0,
                "avg_delivery_rate": round(sum(s["delivery_cadence"]["on_time_percentage"] for s in summaries if "error" not in s) / len([s for s in summaries if "error" not in s]), 1) if summaries else 0,
                "avg_core_pct": round(sum(s["team_health"]["core_percentage"] for s in summaries if "error" not in s) / len([s for s in summaries if "error" not in s]), 1) if summaries else 0,
                "bus_healthy": sum(1 for s in summaries if "HEALTHY" in s["utilization"]["status"]),
                "bus_at_risk": sum(1 for s in summaries if "WARNING" in s["delivery_cadence"]["status"] or "WARNING" in s["utilization"]["status"])
            }
        }


class EmployeeHealthAgent:
    """
    Employee Health Agent - Daily employee wellbeing checks.

    Question: Are employees healthy, engaged, and motivated?

    Tracks:
    - Engagement scores
    - Burnout risk signals
    - Retention risk (flight risk)
    - Work-life balance
    - Team morale
    """

    @staticmethod
    def get_employee_health_score(db: Session, tenant_id: str, employee_id: str) -> Dict[str, Any]:
        """
        Get ONE employee's health score.

        Question: Is this person okay? Risk of burnout/departure?
        """

        employee = db.query(Employee).filter(
            Employee.id == employee_id,
            Employee.tenant_id == tenant_id
        ).first()

        if not employee:
            return {"status": "error", "message": "Employee not found"}

        # Health signals
        today = datetime.utcnow()
        thirty_days_ago = today - timedelta(days=30)
        ninety_days_ago = today - timedelta(days=90)

        # Tenure
        tenure_days = (today - employee.created_at).days if employee.created_at else 0
        is_new = tenure_days < 90

        # Engagement indicators
        engagement_score = 0.75  # TODO: Calculate from interactions, activity

        # Burnout risk (simple heuristic)
        # In real system: track hours, velocity, feedback, promotion
        burnout_risk = 0.2  # 0-1 scale

        # Retention risk (stay/go probability)
        retention_probability = 0.95  # 0-1 scale
        flight_risk = 1 - retention_probability

        # Work-life balance (0-1, higher = better)
        work_life_balance = 0.7

        # Team sentiment (does their manager like them)
        team_sentiment = "positive"

        # Health status
        if flight_risk > 0.3:
            health_status = "🔴 CRITICAL - High flight risk"
        elif burnout_risk > 0.4:
            health_status = "🟡 CAUTION - Burnout risk"
        elif engagement_score < 0.6:
            health_status = "🟡 CAUTION - Low engagement"
        else:
            health_status = "🟢 HEALTHY"

        return {
            "employee_id": employee_id,
            "employee_name": employee.employee_name or "Unknown",
            "tenure_days": tenure_days,
            "is_new_hire": is_new,
            "engagement": {
                "score": round(engagement_score, 2),
                "target": 0.8,
                "status": "🟢" if engagement_score >= 0.7 else "🟡" if engagement_score >= 0.6 else "🔴"
            },
            "burnout_risk": {
                "score": round(burnout_risk, 2),
                "threshold": 0.4,
                "status": "🔴 HIGH" if burnout_risk > 0.4 else "🟡 MODERATE" if burnout_risk > 0.2 else "🟢 LOW"
            },
            "retention_probability": {
                "stay_probability": round(retention_probability, 2),
                "flight_risk": round(flight_risk, 2),
                "status": "🟢 LIKELY STAY" if retention_probability > 0.85 else "🟡 AT RISK" if retention_probability > 0.7 else "🔴 HIGH RISK"
            },
            "work_life_balance": {
                "score": round(work_life_balance, 2),
                "target": 0.8,
                "status": "🟢" if work_life_balance >= 0.7 else "🟡" if work_life_balance >= 0.6 else "🔴"
            },
            "team_sentiment": team_sentiment,
            "overall_health": health_status,
            "recommendation": EmployeeHealthAgent._get_recommendation(
                engagement_score, burnout_risk, retention_probability, is_new
            )
        }

    @staticmethod
    def _get_recommendation(engagement: float, burnout: float, retention: float, is_new: bool) -> str:
        """Get Flash's recommendation for this employee."""

        if retention < 0.7:
            return "🚨 CRITICAL: High flight risk. Manager should have 1-on-1 immediately."
        elif burnout > 0.4:
            return "⚠️ HIGH: Burnout risk detected. Check workload, offer support."
        elif is_new and engagement < 0.6:
            return "⚠️ MEDIUM: New hire struggling with engagement. Check onboarding/role fit."
        elif engagement < 0.6:
            return "⚠️ MEDIUM: Low engagement. Manager should check in."
        else:
            return "✅ HEALTHY: Employee doing well. Continue regular check-ins."

    @staticmethod
    def get_team_health(db: Session, tenant_id: str, team_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get health of a team (or whole company if team_id=None).

        Shows: Team morale, retention risk, burnout signals.
        """

        query = db.query(Employee).filter(
            Employee.tenant_id == tenant_id,
            Employee.status == "ACTIVE"
        )

        if team_id:
            query = query.filter(Employee.current_project_id == team_id)

        employees = query.all()

        health_scores = [
            EmployeeHealthAgent.get_employee_health_score(db, tenant_id, e.id)
            for e in employees
        ]

        # Aggregate
        avg_engagement = sum(s["engagement"]["score"] for s in health_scores if "error" not in s) / len(health_scores) if health_scores else 0
        high_burnout = sum(1 for s in health_scores if s["burnout_risk"]["score"] > 0.4)
        high_flight_risk = sum(1 for s in health_scores if s["retention_probability"]["flight_risk"] > 0.3)

        return {
            "team_id": team_id or "whole_company",
            "total_employees": len(employees),
            "health_summary": health_scores,
            "aggregate": {
                "avg_engagement": round(avg_engagement, 2),
                "employees_with_burnout_risk": high_burnout,
                "employees_with_flight_risk": high_flight_risk,
                "retention_rate_expected": round((len(health_scores) - high_flight_risk) / len(health_scores) * 100, 1) if health_scores else 0,
                "team_morale": "🟢 POSITIVE" if high_flight_risk + high_burnout == 0 else "🟡 CAUTION" if high_flight_risk + high_burnout < 3 else "🔴 CRITICAL"
            },
            "action": "Prioritize 1-on-1s with high-risk employees"
        }
