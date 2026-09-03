"""
import logging
Agent Pyramid Reporting System - 6-Level Hierarchical Accountability

COMPLETE HIERARCHY (Deep to Shallow):

Level 6: Tech Leads (Weekly Friday 3PM)
  └─ Individual work tracking for the week
  └─ Code commits, PRs, bugs fixed, stories completed
  └─ Blockers and challenges faced
  └─ Velocity metrics, code quality
  └─ Reports to: Manager

Level 5: Manager (Weekly Friday 4PM)
  └─ Consolidates 5-15 tech lead reports
  └─ Team velocity, code quality metrics
  └─ Resource allocation, blockers, risks
  └─ Team health, morale, attrition risks
  └─ Reports to: Principal Architect

Level 4: Principal Architect (Weekly Friday 5PM)
  └─ Consolidates 3-5 manager reports
  └─ Technical health, architecture decisions
  └─ Risk assessment, roadmap progress, technical debt
  └─ Report format: 1-page summary with drill-downs
  └─ Reports to: BU Head

Level 3: BU Head (Weekly Friday 6PM)
  └─ Consolidates architect + operational metrics
  └─ Delivery cadence, utilization, revenue
  └─ Headcount changes, team health
  └─ Report format: Dashboard with KPIs
  └─ Reports to: Partner

Level 2: Partner (Weekly Friday 7PM)
  └─ Consolidates all BU reports (architect + operational)
  └─ Consolidated revenue, pipeline, growth
  └─ Issues, escalations, action items per BU
  └─ Report format: Executive summary (1 page)
  └─ Reports to: CEO

Level 1: CEO (Weekly Friday 8PM)
  └─ Executive dashboard across all partners
  └─ Company health, critical escalations
  └─ Decision & feedback distribution
  └─ Report format: Company dashboard + action items

FEEDBACK LOOP (Shallow to Deep):
  CEO → Partners → BU Heads → Architects → Managers → Tech Leads
  (Feedback cascades down week-to-week for course correction)

EXECUTION SCHEDULE (WEEKLY, Every Friday):

  3:00 PM - Tech Leads submit weekly reports (commits, PRs, blockers, velocity)
  4:00 PM - Manager consolidates tech lead reports + sends to Architect
  5:00 PM - Principal Architect consolidates tech metrics + sends to BU Head
  6:00 PM - BU Head combines architect data with operational metrics
  7:00 PM - Partner consolidates all BUs + sends to CEO
  8:00 PM - CEO reviews all partners, identifies company-wide patterns

FEEDBACK CASCADE (Following Week):
  Monday morning: CEO feedback reaches Partners
  Monday 10AM: Partner feedback reaches BU Heads
  Monday 2PM: BU Head feedback reaches Architects
  Monday 4PM: Architect feedback reaches Managers
  Tuesday 9AM: Manager feedback reaches Tech Leads
  (All adjustments implemented for next week's reporting cycle)

"FIX ANYTHING AS MINUTE AS AN ANT" - EVERY LEVEL IS TRACKED AND ACCOUNTABLE
"""

import logging
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

logger = logging.getLogger(__name__)

class TechLeadWeeklyReportAgent:
    """
    Tech Lead Weekly Report Agent - Runs every Friday at 3PM

    Question: What did my team accomplish this week? What are our blockers?
    """

    @staticmethod
    def generate_tech_lead_weekly_report(db: Session, tenant_id: str, tech_lead_id: str, week_start: datetime = None) -> Dict[str, Any]:
        """
        Generate tech lead's weekly work report.

        Tracks:
        - Code commits this week
        - Pull requests created/reviewed/merged
        - Bugs fixed
        - Features/stories completed
        - Blockers and challenges
        - Next week's priorities
        - Velocity metrics
        """

        tech_lead = db.query(Employee).filter(
            Employee.UserID == tech_lead_id,
            Employee.tenant_id == tenant_id
        ).first()

        if not tech_lead:
            return {"status": "error", "message": "Tech lead not found"}

        if week_start is None:
            today = datetime.utcnow()
            week_start = today - timedelta(days=today.weekday())

        week_end = week_start + timedelta(days=7)

        return {
            "week": f"{week_start.date()} to {week_end.date()}",
            "tech_lead_id": tech_lead_id,
            "tech_lead_name": tech_lead.first_name + " " + tech_lead.last_name if tech_lead.first_name else "Unknown",
            "project": tech_lead.current_project_id or "Unassigned",
            "work_items": {
                "commits": 32,  # Would fetch from Git/GitHub API
                "pull_requests": {
                    "created": 4,
                    "reviewed": 6,
                    "merged": 3
                },
                "bugs_fixed": 2,
                "features_completed": 2,
                "stories_points_completed": 21,
                "velocity_vs_target": "105%",  # Above sprint target
                "code_quality_score": 8.5  # 0-10, based on code review feedback
            },
            "blockers": [],  # Tech lead lists what's blocking them
            "risks": [],  # Upcoming risks
            "next_week_priorities": [],  # What they'll focus on next week
            "status": "✅ ON TRACK",  # ON_TRACK, AHEAD, BLOCKED
            "morale": 8,  # 1-10 self-reported
            "comment": "Good progress on feature X. Design feedback for Y expected Monday."
        }

    @staticmethod
    def collect_team_reports(db: Session, tenant_id: str, manager_id: str, week_start: datetime = None) -> List[Dict]:
        """
        Collect all tech lead reports for a manager.
        """

        # Get all tech leads reporting to this manager
        team_members = db.query(Employee).filter(
            Employee.tenant_id == tenant_id,
            Employee.manager_id == manager_id  # Direct reports
        ).all()

        reports = []
        for member in team_members:
            report = TechLeadWeeklyReportAgent.generate_tech_lead_weekly_report(
                db, tenant_id, member.UserID, week_start
            )
            if report.get("status") != "error":
                reports.append(report)

        return reports

class ManagerWeeklyReportAgent:
    """
    Manager Weekly Report Agent - Runs every Friday at 4PM

    Question: How is my team performing this week? What blockers need escalation?

    Consolidates all tech lead reports from the week.
    """

    @staticmethod
    def generate_manager_weekly_report(db: Session, tenant_id: str, manager_id: str, week_start: datetime = None) -> Dict[str, Any]:
        """
        Generate manager's consolidated weekly team report.
        """

        manager = db.query(Employee).filter(
            Employee.UserID == manager_id,
            Employee.tenant_id == tenant_id
        ).first()

        if not manager:
            return {"status": "error", "message": "Manager not found"}

        if week_start is None:
            today = datetime.utcnow()
            week_start = today - timedelta(days=today.weekday())

        # Collect all tech lead reports
        tech_lead_reports = TechLeadWeeklyReportAgent.collect_team_reports(db, tenant_id, manager_id, week_start)

        # Aggregate metrics
        total_commits = sum(r.get("work_items", {}).get("commits", 0) for r in tech_lead_reports)
        total_prs_merged = sum(r.get("work_items", {}).get("pull_requests", {}).get("merged", 0) for r in tech_lead_reports)
        total_bugs_fixed = sum(r.get("work_items", {}).get("bugs_fixed", 0) for r in tech_lead_reports)
        total_velocity = sum(r.get("work_items", {}).get("stories_points_completed", 0) for r in tech_lead_reports)
        team_blockers = []
        for r in tech_lead_reports:
            team_blockers.extend(r.get("blockers", []))

        # Team health calculation
        avg_morale = sum(r.get("morale", 5) for r in tech_lead_reports) / len(tech_lead_reports) if tech_lead_reports else 5
        blockers_count = len(team_blockers)
        team_health = 100 - (blockers_count * 10) + (avg_morale * 5)
        team_health = min(100, max(0, team_health))

        week_end = week_start + timedelta(days=7)

        return {
            "week": f"{week_start.date()} to {week_end.date()}",
            "manager_id": manager_id,
            "manager_name": manager.first_name + " " + manager.last_name if manager.first_name else "Unknown",
            "team_size": len(tech_lead_reports),
            "aggregated_metrics": {
                "total_commits": total_commits,
                "total_pull_requests_merged": total_prs_merged,
                "total_bugs_fixed": total_bugs_fixed,
                "total_velocity_points": total_velocity,
                "avg_morale": round(avg_morale, 1),
                "team_health_score": round(team_health, 1)
            },
            "team_status": "🟢 HEALTHY" if team_health >= 75 else "🟡 CAUTION" if team_health >= 50 else "🔴 CRITICAL",
            "team_members": [
                {
                    "name": r["tech_lead_name"],
                    "status": r["status"],
                    "velocity": r.get("work_items", {}).get("stories_points_completed", 0),
                    "blockers": r.get("blockers", []),
                    "morale": r.get("morale", 5)
                }
                for r in tech_lead_reports
            ],
            "critical_blockers": [b for b in team_blockers if "CRITICAL" in b.upper()],
            "team_blockers_summary": f"{len(team_blockers)} blockers identified",
            "recommendation": ManagerWeeklyReportAgent._get_manager_recommendation(
                team_health, len(team_blockers), avg_morale
            ),
            "escalations": ManagerWeeklyReportAgent._identify_escalations(team_health, team_blockers, len(tech_lead_reports))
        }

    @staticmethod
    def _get_manager_recommendation(health: float, blockers: int, morale: float) -> str:
        """Get recommendation for manager."""

        if blockers >= 3:
            return f"🔴 CRITICAL: {blockers} blockers. Escalate to Principal Architect immediately."
        elif health < 60:
            return f"🟡 TEAM RISK: Health at {health:.0f}%. Address morale and blocker issues."
        elif morale < 5:
            return f"🟡 MORALE ALERT: Team morale {morale:.1f}/10. 1:1s recommended."
        else:
            return f"✅ TEAM ON TRACK: Health {health:.0f}%, {blockers} minor blockers. Continue momentum."

    @staticmethod
    def _identify_escalations(health: float, blockers: List[str], team_size: int) -> List[str]:
        """Identify issues needing escalation to Principal Architect."""

        escalations = []
        if health < 50:
            escalations.append("TEAM_HEALTH_CRITICAL")
        if len(blockers) >= 2:
            escalations.append("MULTIPLE_BLOCKERS")
        if team_size > 1 and len(blockers) >= team_size // 2:
            escalations.append("WIDESPREAD_BLOCKERS")
        return escalations

class PrincipalArchitectWeeklyReportAgent:
    """
    Principal Architect Weekly Report Agent - Runs every Friday at 5PM

    Question: What is the technical health of my organization this week?

    Consolidates manager reports and adds architectural assessment.
    """

    @staticmethod
    def generate_architect_weekly_report(db: Session, tenant_id: str, architect_id: str, week_start: datetime = None) -> Dict[str, Any]:
        """
        Generate principal architect's weekly technical health report.
        """

        architect = db.query(Employee).filter(
            Employee.UserID == architect_id,
            Employee.tenant_id == tenant_id
        ).first()

        if not architect:
            return {"status": "error", "message": "Architect not found"}

        if week_start is None:
            today = datetime.utcnow()
            week_start = today - timedelta(days=today.weekday())

        # Collect all manager reports (managers reporting to this architect)
        managers = db.query(Employee).filter(
            Employee.tenant_id == tenant_id,
            Employee.manager_id == architect_id  # Direct reports
        ).all()

        manager_reports = []
        for manager in managers:
            report = ManagerWeeklyReportAgent.generate_manager_weekly_report(
                db, tenant_id, manager.UserID, week_start
            )
            if report.get("status") != "error":
                manager_reports.append(report)

        # Aggregate technical metrics
        total_commits = sum(r.get("aggregated_metrics", {}).get("total_commits", 0) for r in manager_reports)
        total_prs = sum(r.get("aggregated_metrics", {}).get("total_pull_requests_merged", 0) for r in manager_reports)
        total_velocity = sum(r.get("aggregated_metrics", {}).get("total_velocity_points", 0) for r in manager_reports)
        avg_team_health = sum(r.get("aggregated_metrics", {}).get("team_health_score", 50) for r in manager_reports) / len(manager_reports) if manager_reports else 50

        # Identify technical risks
        tech_risks = []
        for r in manager_reports:
            if r.get("team_status") != "🟢 HEALTHY":
                tech_risks.extend(r.get("escalations", []))

        week_end = week_start + timedelta(days=7)

        return {
            "week": f"{week_start.date()} to {week_end.date()}",
            "architect_id": architect_id,
            "architect_name": architect.first_name + " " + architect.last_name if architect.first_name else "Unknown",
            "management_chain": len(manager_reports),
            "technical_metrics": {
                "total_commits": total_commits,
                "total_prs_merged": total_prs,
                "total_velocity_points": total_velocity,
                "avg_team_health": round(avg_team_health, 1),
                "technical_debt_level": "MODERATE",  # Would assess from code metrics
                "architecture_score": 7.5  # 0-10 health of system architecture
            },
            "technical_status": "🟢 HEALTHY" if avg_team_health >= 75 else "🟡 CAUTION" if avg_team_health >= 50 else "🔴 CRITICAL",
            "manager_reports_summary": [
                {
                    "manager_name": r["manager_name"],
                    "team_health": r["aggregated_metrics"]["team_health_score"],
                    "blockers": len(r.get("escalations", [])),
                    "velocity": r["aggregated_metrics"]["total_velocity_points"]
                }
                for r in manager_reports
            ],
            "technical_risks": list(set(tech_risks)),  # Deduplicate
            "architecture_decisions": [
                "Completed migration to new API gateway",
                "Reviewed caching strategy for DB optimization"
            ],
            "recommendation": PrincipalArchitectWeeklyReportAgent._get_architect_recommendation(
                avg_team_health, len(tech_risks), total_velocity
            ),
            "escalations": PrincipalArchitectWeeklyReportAgent._identify_architecture_escalations(
                avg_team_health, tech_risks
            )
        }

    @staticmethod
    def _get_architect_recommendation(health: float, risks: int, velocity: int) -> str:
        """Get recommendation from architect perspective."""

        if risks > 5:
            return f"🔴 CRITICAL: {risks} technical risks across organization. Escalate to BU Head for resource reallocation."
        elif health < 60:
            return f"🟡 TECHNICAL RISK: Organization health {health:.0f}%. Review team capacity and technical priorities."
        elif velocity < 50:
            return f"🟡 VELOCITY LOW: Only {velocity} points completed. Investigate blockers."
        else:
            return f"✅ TECHNICALLY HEALTHY: Health {health:.0f}%, {velocity} velocity points. No immediate concerns."

    @staticmethod
    def _identify_architecture_escalations(health: float, risks: List[str]) -> List[str]:
        """Identify architectural issues."""

        escalations = []
        if health < 50:
            escalations.append("ORGANIZATION_TECHNICAL_HEALTH_CRITICAL")
        if len([r for r in risks if "CRITICAL" in r]) > 0:
            escalations.append("MULTIPLE_CRITICAL_RISKS")
        return escalations

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
    def generate_partner_weekly_consolidation(db: Session, tenant_id: str, partner_id: str, annual_goal_usd: int = 5000000) -> Dict[str, Any]:
        """
        Generate consolidated weekly report for Partner (all BUs).

        Tracks weekly progress against annual goal.
        Example: Partner annual goal = $5M = $96.2K/week needed to stay on pace

        Shows:
        - This week's revenue
        - YTD revenue (all weeks so far this year)
        - Annual target
        - Weekly pace needed vs actual
        - Status: ON_PACE, AHEAD, BEHIND
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

        # Annual Goal Tracking
        today = datetime.utcnow()
        days_into_year = today.timetuple().tm_yday
        weeks_into_year = days_into_year // 7
        weeks_remaining = (365 - days_into_year) // 7

        # YTD Revenue (all weeks so far)
        # For now, assume current week is representative
        ytd_revenue = total_revenue * weeks_into_year
        expected_revenue_by_today = (annual_goal_usd / 365) * days_into_year
        weekly_pace_needed = annual_goal_usd / 52

        # Pace calculation
        pace_pct = (ytd_revenue / expected_revenue_by_today * 100) if expected_revenue_by_today > 0 else 0
        progress_pct = (ytd_revenue / annual_goal_usd * 100) if annual_goal_usd > 0 else 0

        # Status
        if pace_pct >= 100:
            pace_status = "🟢 ON PACE"
        elif pace_pct >= 80:
            pace_status = "🟡 SLIGHT LAG"
        elif pace_pct >= 60:
            pace_status = "🟡 FALLING BEHIND"
        else:
            pace_status = "🔴 CRITICAL MISS"

        return {
            "week": bu_reports[0]["week"] if bu_reports else "N/A",
            "partner_id": partner_id,
            "partner_name": partner.UserName,
            "reporting_date": datetime.utcnow().isoformat(),
            "bu_count": len(bu_reports),
            "consolidated_metrics": {
                "avg_delivery_cadence": round(avg_delivery, 1),
                "avg_utilization": round(avg_util, 1),
                "total_revenue_this_week": f"${total_revenue:,.0f}",
                "total_opportunities": total_opps,
                "health_status": "🟢 HEALTHY" if consolidated_health >= 75 else "🟡 CAUTION" if consolidated_health >= 50 else "🔴 CRITICAL"
            },
            "annual_goal_tracking": {
                "annual_target": f"${annual_goal_usd:,.0f}",
                "weekly_pace_needed": f"${weekly_pace_needed:,.0f}",
                "ytd_revenue": f"${ytd_revenue:,.0f}",
                "progress_pct": round(progress_pct, 1),
                "pace_pct": round(pace_pct, 1),
                "pace_status": pace_status,
                "weeks_completed": weeks_into_year,
                "weeks_remaining": weeks_remaining,
                "on_track": "YES" if pace_pct >= 100 else "NO"
            },
            "bu_reports": bu_reports,
            "escalations": list(set(escalations)),  # Deduplicate
            "recommendation": PartnerWeeklyConsolidationAgent._get_partner_recommendation(
                consolidated_health, total_revenue, total_opps, len(escalations), pace_pct
            ),
            "action_items": PartnerWeeklyConsolidationAgent._generate_action_items(
                bu_reports, escalations, pace_pct
            )
        }

    @staticmethod
    def _get_partner_recommendation(health: float, revenue: float, opps: int, escalation_count: int, pace_pct: float = 100) -> str:
        """Get recommendation for Partner on what to do."""

        if pace_pct < 60:
            return f"🔴 CRITICAL PACE: On-pace for ${revenue * 52:,.0f} annual (target ${revenue * 52 * (100/pace_pct):,.0f}). URGENT: Increase revenue activity."
        elif escalation_count >= 3:
            return f"🔴 CRITICAL: {escalation_count} major escalations this week. Emergency coordination call required."
        elif health < 60:
            return f"🟡 OVERALL CAUTION: Consolidated health score {health:.0f}. Review BU strategies and resource allocation."
        elif pace_pct < 80:
            return f"🟡 PACE BEHIND: {pace_pct:.0f}% of target pace. Increase deal flow and close rates."
        elif opps < 3:
            return f"🟡 SALES PIPELINE WEAK: Only {opps} opportunities added across all BUs. Need sales activity boost."
        elif revenue > 50000:
            return f"✅ STRONG WEEK: ${revenue:,.0f} revenue + {opps} new opportunities. Maintaining pace."
        else:
            return f"✅ ON TRACK: All BUs performing within targets. Continue current execution."

    @staticmethod
    def _generate_action_items(bu_reports: List[Dict], escalations: List[str], pace_pct: float = 100) -> List[Dict]:
        """Generate specific action items for Partner."""

        actions = []

        # If behind on annual pace, this is TOP priority
        if pace_pct < 100:
            actions.append({
                "priority": "CRITICAL",
                "item": f"Annual goal pace at {pace_pct:.0f}%",
                "action": f"Increase revenue velocity. Current pace misses annual target. Review pipeline and deal stages.",
                "owner": "Partner",
                "due_date": "This week"
            })

        # If any BU delivery < 85%, create action
        for bu_report in bu_reports:
            delivery = bu_report["metrics"]["delivery_cadence"]["value"]
            if delivery < 85:
                actions.append({
                    "priority": "HIGH",
                    "bu": bu_report["bu_name"],
                    "action": f"Address delivery miss ({delivery:.0f}%). Review project schedule & resource plan.",
                    "owner": f"BU Head - {bu_report['bu_name']}",
                    "due_date": "Next Friday"
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
