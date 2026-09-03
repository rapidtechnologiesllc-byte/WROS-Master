"""
import logging
Personal Goal Agents - Individual Accountability

Every person with a target gets an agent that:
1. Tracks their daily/weekly progress vs goal
2. Identifies gaps immediately
3. Provides coaching recommendations
4. Escalates if they're falling behind

Personal Goal Agents:
- Recruiter Goal Agent (for each recruiter)
- Sales Person Goal Agent (for each sales person)
- Partner Goal Agent (for each partner)
- BU Head Goal Agent (for each BU leader)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.employee import Employee
from app.models.opportunity import Opportunity
from app.models.candidate import Candidate
from app.models.user import Users
from app.core.logging import logger

logger = logging.getLogger(__name__)

class RecruiterGoalAgent:
    """
    Recruiter Goal Agent - Track each recruiter's hiring target.

    Question: Is this recruiter on pace to hit their hiring goal?

    Each recruiter has a monthly target (e.g., 10 hires/month)
    Agent tracks daily: candidates contacted, qualified, interviewed, hired
    """

    @staticmethod
    def get_recruiter_daily_progress(db: Session, tenant_id: str, recruiter_id: str, monthly_target: int = 10) -> Dict[str, Any]:
        """
        Track ONE recruiter's progress toward their monthly goal.

        Default: 10 hires/month = 2.5/week = ~0.5/day
        But realistic: 1-2/week = 4-8/month
        """

        recruiter = db.query(Users).filter(
            Users.UserID == recruiter_id,
            Users.tenant_id == tenant_id
        ).first()

        if not recruiter:
            return {"status": "error", "message": "Recruiter not found"}

        today = datetime.utcnow()
        month_start = datetime(today.year, today.month, 1)

        # Calculate days into month
        days_into_month = (today - month_start).days + 1
        days_remaining = (datetime(today.year, today.month + 1 if today.month < 12 else 1, 1) - today).days if today.month < 12 else (datetime(today.year + 1, 1, 1) - today).days

        # This month's hires (candidates they brought to "HIRED" status)
        monthly_hires = db.query(func.count(Candidate.candidateID)).filter(
            Candidate.tenant_id == tenant_id,
            Candidate.recruiter_id == recruiter_id,
            Candidate.status == "HIRED",
            Candidate.updated_at >= month_start
        ).scalar() or 0

        # This week's hires (last 7 days)
        week_start = today - timedelta(days=today.weekday())
        weekly_hires = db.query(func.count(Candidate.candidateID)).filter(
            Candidate.tenant_id == tenant_id,
            Candidate.recruiter_id == recruiter_id,
            Candidate.status == "HIRED",
            Candidate.updated_at >= week_start
        ).scalar() or 0

        # Progress
        expected_pace = (monthly_target / 30) * days_into_month  # What they should have by today
        progress_pct = (monthly_hires / monthly_target * 100) if monthly_target > 0 else 0
        pace_pct = (monthly_hires / expected_pace * 100) if expected_pace > 0 else 0

        # Pipeline (candidates they're working on)
        pipeline = db.query(func.count(Candidate.candidateID)).filter(
            Candidate.tenant_id == tenant_id,
            Candidate.recruiter_id == recruiter_id,
            Candidate.status.in_(["QUALIFIED", "SCREENING", "SUBMITTED_TO_JOB", "INTERVIEW", "OFFER"])
        ).scalar() or 0

        # Status
        if pace_pct >= 100:
            status = "🟢 ON PACE"
        elif pace_pct >= 80:
            status = "🟡 SLIGHT LAG"
        elif pace_pct >= 60:
            status = "🟡 FALLING BEHIND"
        else:
            status = "🔴 CRITICAL"

        return {
            "recruiter_id": recruiter_id,
            "recruiter_name": recruiter.UserName,
            "month": today.strftime("%B %Y"),
            "target_monthly": monthly_target,
            "progress": {
                "hires_so_far": monthly_hires,
                "target": monthly_target,
                "progress_pct": round(progress_pct, 1),
                "pace_pct": round(pace_pct, 1),
                "status": status
            },
            "this_week": {
                "hires": weekly_hires,
                "target_weekly": round(monthly_target / 4, 1),
                "on_pace": "Yes" if weekly_hires >= round(monthly_target / 4 * 0.5, 0) else "No"
            },
            "timeline": {
                "days_into_month": days_into_month,
                "days_remaining": days_remaining,
                "expected_by_today": round(expected_pace, 1)
            },
            "pipeline": {
                "candidates_in_pipeline": pipeline,
                "projected_additional_hires": max(0, pipeline // 4)  # Assume 25% conversion
            },
            "trajectory": {
                "at_current_pace": round((monthly_hires / max(days_into_month, 1)) * 30, 0),
                "recommendation": RecruiterGoalAgent._get_recommendation(pace_pct, monthly_hires, monthly_target, pipeline, days_remaining)
            }
        }

    @staticmethod
    def _get_recommendation(pace_pct: float, hires: int, target: int, pipeline: int, days_left: int) -> str:
        """Get coaching recommendation for this recruiter."""

        if pace_pct >= 100:
            return f"✅ ON PACE: {hires}/{target} done. Maintain current velocity."
        elif pace_pct >= 80:
            return f"⚠️ SLIGHT LAG: {hires}/{target} done, {days_left} days left. Accelerate slightly."
        elif pipeline > target - hires:
            return f"🟡 BEHIND but RECOVERABLE: Pipeline has enough to catch up. Close deals faster."
        else:
            return f"🔴 CRITICAL: {hires}/{target} done, {days_left} days left, weak pipeline. URGENT: Increase outreach NOW."

    @staticmethod
    def get_all_recruiters_scoreboard(db: Session, tenant_id: str) -> Dict[str, Any]:
        """Get scoreboard of ALL recruiters."""

        recruiters = db.query(Users).filter(
            Users.tenant_id == tenant_id,
            Users.UserRole == "Recruiter"
        ).all()

        scoreboard = []
        for recruiter in recruiters:
            progress = RecruiterGoalAgent.get_recruiter_daily_progress(db, tenant_id, recruiter.UserID, monthly_target=10)
            scoreboard.append(progress)

        # Sort by pace (worst first)
        scoreboard.sort(key=lambda x: x["progress"]["pace_pct"])

        return {
            "status": "success",
            "reporting_date": datetime.utcnow().date().isoformat(),
            "recruiters": scoreboard,
            "summary": {
                "total_recruiters": len(scoreboard),
                "on_pace": sum(1 for s in scoreboard if "ON PACE" in s["progress"]["status"]),
                "lagging": sum(1 for s in scoreboard if "BEHIND" in s["progress"]["status"] or "LAG" in s["progress"]["status"]),
                "critical": sum(1 for s in scoreboard if "CRITICAL" in s["progress"]["status"]),
                "total_hires_mtd": sum(s["progress"]["hires_so_far"] for s in scoreboard),
                "total_target": sum(10 for _ in scoreboard)  # Assumes all have 10-hire target
            },
            "action": "Push lagging recruiters; celebrate on-pace recruiters"
        }

class SalesPersonGoalAgent:
    """
    Sales Person Goal Agent - Track each sales person's revenue target.

    Question: Is this sales person on pace to hit their revenue goal?

    Each sales person has a monthly revenue target (e.g., $50K/month)
    Agent tracks: pipeline, closed deals, conversion rate
    """

    @staticmethod
    def get_salesperson_weekly_progress(db: Session, tenant_id: str, salesperson_id: str, weekly_target_usd: int = 15000) -> Dict[str, Any]:
        """
        Track ONE salesperson's weekly revenue progress.

        Default: $50K/month = $12.5K/week
        """

        salesperson = db.query(Users).filter(
            Users.UserID == salesperson_id,
            Users.tenant_id == tenant_id
        ).first()

        if not salesperson:
            return {"status": "error", "message": "Salesperson not found"}

        today = datetime.utcnow()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=7)

        # This week's revenue
        weekly_revenue_cents = db.query(func.sum(Opportunity.deal_size_usd)).filter(
            Opportunity.tenant_id == tenant_id,
            Opportunity.owner_id == salesperson_id,
            Opportunity.close_date >= week_start,
            Opportunity.close_date < week_end,
            Opportunity.status == "won"
        ).scalar() or 0

        weekly_revenue = weekly_revenue_cents / 100

        # Pipeline
        pipeline_cents = db.query(func.sum(Opportunity.deal_size_usd)).filter(
            Opportunity.tenant_id == tenant_id,
            Opportunity.owner_id == salesperson_id,
            Opportunity.status.in_(["prospecting", "proposal", "negotiation"])
        ).scalar() or 0

        pipeline = pipeline_cents / 100

        # Progress
        progress_pct = (weekly_revenue / weekly_target_usd * 100) if weekly_target_usd > 0 else 0

        # Status
        if progress_pct >= 100:
            status = "🟢 TARGET HIT"
        elif progress_pct >= 70:
            status = "🟡 CLOSE"
        elif progress_pct >= 50:
            status = "🟡 TRACKING"
        else:
            status = "🔴 WEAK"

        return {
            "salesperson_id": salesperson_id,
            "salesperson_name": salesperson.UserName,
            "week": f"{week_start.date()} to {week_end.date()}",
            "this_week": {
                "revenue_closed": f"${weekly_revenue:,.0f}",
                "target": f"${weekly_target_usd:,.0f}",
                "progress_pct": round(progress_pct, 1),
                "status": status
            },
            "pipeline": {
                "active_pipeline": f"${pipeline:,.0f}",
                "average_deal_size": f"${pipeline / max(db.query(func.count(Opportunity.id)).filter(Opportunity.owner_id == salesperson_id, Opportunity.status.in_(["prospecting", "proposal", "negotiation"])).scalar() or 1, 1):,.0f}",
                "expected_close_probability": "50%"
            },
            "forecast": {
                "expected_next_week": f"${pipeline / 5:,.0f}",
                "recommendation": SalesPersonGoalAgent._get_recommendation(progress_pct, weekly_revenue, weekly_target_usd, pipeline)
            }
        }

    @staticmethod
    def _get_recommendation(progress_pct: float, revenue: float, target: float, pipeline: float) -> str:
        """Get coaching recommendation for this sales person."""

        if progress_pct >= 100:
            return f"🎉 TARGET HIT: ${revenue:,.0f} closed. Maintain momentum."
        elif progress_pct >= 70:
            return f"✅ CLOSE: ${revenue:,.0f}/${target:,.0f}. Few more deals close the gap."
        elif pipeline >= target - revenue:
            return f"⚠️ TRACKING: ${revenue:,.0f}/${target:,.0f}. Pipeline is strong. Focus on closing."
        else:
            return f"🔴 WEAK WEEK: ${revenue:,.0f}/${target:,.0f}. Increase prospecting ASAP."

class PartnerGoalAgent:
    """
    Partner Goal Agent - Track each partner's revenue target.

    Question: Is this partner on track to their quarterly/annual goal?
    """

    @staticmethod
    def get_partner_goal_progress(db: Session, tenant_id: str, partner_id: str, annual_target_usd: int = 500000) -> Dict[str, Any]:
        """Track partner progress toward annual revenue goal."""

        partner = db.query(Users).filter(
            Users.UserID == partner_id,
            Users.tenant_id == tenant_id
        ).first()

        if not partner:
            return {"status": "error", "message": "Partner not found"}

        today = datetime.utcnow()
        ytd_start = datetime(today.year, 1, 1)

        # YTD revenue
        ytd_revenue_cents = db.query(func.sum(Opportunity.deal_size_usd)).filter(
            Opportunity.partner_owner_id == partner_id,
            Opportunity.tenant_id == tenant_id,
            Opportunity.close_date >= ytd_start,
            Opportunity.status == "won"
        ).scalar() or 0

        ytd_revenue = ytd_revenue_cents / 100
        days_into_year = today.timetuple().tm_yday
        expected_by_today = (annual_target_usd / 365) * days_into_year

        progress_pct = (ytd_revenue / annual_target_usd * 100) if annual_target_usd > 0 else 0
        pace_pct = (ytd_revenue / expected_by_today * 100) if expected_by_today > 0 else 0

        return {
            "partner_id": partner_id,
            "partner_name": partner.UserName,
            "annual_target": f"${annual_target_usd:,.0f}",
            "ytd": {
                "revenue": f"${ytd_revenue:,.0f}",
                "progress_pct": round(progress_pct, 1),
                "pace_pct": round(pace_pct, 1),
                "status": "🟢 ON PACE" if pace_pct >= 100 else "🟡 LAGGING" if pace_pct >= 75 else "🔴 CRITICAL"
            },
            "projection": {
                "at_current_pace": f"${(ytd_revenue / max(days_into_year, 1)) * 365:,.0f}",
                "gap_to_target": f"${annual_target_usd - ytd_revenue:,.0f}",
                "days_remaining": 365 - days_into_year
            },
            "recommendation": f"💰 {"ON TRACK" if pace_pct >= 100 else "NEEDS PUSH"}: ${ytd_revenue:,.0f}/${annual_target_usd:,.0f}"
        }

class BUHeadGoalAgent:
    """
    BU Head Goal Agent - Track each BU leader's performance targets.

    Question: Is this BU head hitting delivery, utilization, and growth targets?
    """

    @staticmethod
    def get_bu_head_goal_progress(db: Session, tenant_id: str, bu_id: str) -> Dict[str, Any]:
        """
        Track BU head's progress on all KPIs.

        Targets:
        - Delivery: 90%+ on-time
        - Utilization: 75%+
        - CORE: 60%+
        - Growth: Positive headcount change
        """

        from app.models.business_unit import BusinessUnit

        bu = db.query(BusinessUnit).filter(
            BusinessUnit.id == bu_id,
            BusinessUnit.tenant_id == tenant_id
        ).first()

        if not bu:
            return {"status": "error", "message": "BU not found"}

        today = datetime.utcnow()
        month_start = datetime(today.year, today.month, 1)

        # Delivery rate
        projects = db.query(Project).filter(
            Project.tenant_id == tenant_id,
            Project.business_unit_id == bu_id
        ).all()

        on_time = sum(1 for p in projects if p.end_date and p.end_date <= today)
        delivery_rate = (on_time / len(projects) * 100) if len(projects) > 0 else 100

        # Utilization
        total_emps = db.query(func.count(Employee.id)).filter(
            Employee.business_unit_id == bu_id,
            Employee.status == "ACTIVE"
        ).scalar() or 1

        allocated = db.query(func.count(Employee.id)).filter(
            Employee.business_unit_id == bu_id,
            Employee.status == "ACTIVE",
            Employee.current_project_id.isnot(None)
        ).scalar() or 0

        utilization = (allocated / total_emps * 100) if total_emps > 0 else 0

        # CORE
        core = db.query(func.count(Employee.id)).filter(
            Employee.business_unit_id == bu_id,
            Employee.is_core_certified == True
        ).scalar() or 0

        core_pct = (core / total_emps * 100) if total_emps > 0 else 0

        # Growth
        start_month_headcount = total_emps - db.query(func.count(Employee.id)).filter(
            Employee.business_unit_id == bu_id,
            Employee.created_at >= month_start
        ).scalar() or 0

        growth = total_emps - start_month_headcount

        # Score (0-100)
        score = (delivery_rate * 0.3 + utilization * 0.3 + core_pct * 0.2 + (growth if growth > 0 else -5) * 0.2)

        return {
            "bu_id": bu_id,
            "bu_name": bu.name,
            "date": today.date().isoformat(),
            "scorecard": {
                "delivery_rate": f"{round(delivery_rate, 1)}% (target: 90%+)",
                "utilization": f"{round(utilization, 1)}% (target: 75%+)",
                "core_certification": f"{round(core_pct, 1)}% (target: 60%+)",
                "headcount_growth": f"+{growth} this month",
                "overall_score": f"{round(score, 1)}/100"
            },
            "status": "🟢 EXCELLENT" if score >= 85 else "🟡 GOOD" if score >= 70 else "🔴 NEEDS WORK",
            "recommendation": BUHeadGoalAgent._get_recommendation(delivery_rate, utilization, core_pct, growth, score)
        }

    @staticmethod
    def _get_recommendation(delivery: float, util: float, core: float, growth: int, score: float) -> str:
        """Get coaching recommendation for this BU head."""

        issues = []
        if delivery < 90:
            issues.append("Delivery <90%")
        if util < 75:
            issues.append("Utilization <75%")
        if core < 60:
            issues.append("CORE <60%")
        if growth <= 0:
            issues.append("No headcount growth")

        if not issues:
            return f"🎯 EXCELLENT: All KPIs exceeded. Keep this momentum."
        else:
            return f"⚠️ FOCUS ON: {', '.join(issues)}"
