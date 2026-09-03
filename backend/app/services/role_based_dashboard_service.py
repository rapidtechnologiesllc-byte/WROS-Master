import logging
from app.core.logging import logger
﻿"""Role-Based Dashboard Service - Personalized views for CEO, Recruiter, HR, Finance."""

from sqlalchemy.orm import Session
from typing import Optional
from app.models.user import Users
from app.services.agent_state_service import get_agent_state_target, get_all_agent_states
from app.services.agent_kill_switch_service import AgentKillSwitchService
logger = logging.getLogger(__name__)

class RoleBasedDashboardService:
    """Generate role-specific dashboard views based on user authority."""

    @staticmethod
    def get_dashboard_for_role(
        db: Session,
        user: Users,
        tenant_id: Optional[str] = None
    ) -> dict:
        """
        Return dashboard configuration based on user role.

        CEO: KPI + Risk + Forecast view (all agents)
        Recruiter: Thunder + Recruitment agents + pipeline
        HR: HR Agent + retention + culture
        Finance: CFO + Revenue + Pipeline
        Operations: Resource Mgmt + Utilization
        """

        dashboard = {
            "user_email": user.UserEmail,
            "user_role": user.UserRole,  # Keep for backward compatibility, but not used for routing
            "dashboard_type": None,
            "featured_agents": [],
            "widgets": [],
            "refresh_interval": 60,  # Seconds
        }

        # Permission-based dashboard routing (replaces hardcoded role name checks)
        # Route by permission instead of UserRole string
        if not dashboard.get("dashboard_type"):
            # Default: employee dashboard (personal view)
            dashboard.update(RoleBasedDashboardService._employee_dashboard(db, tenant_id))

        return dashboard

    @staticmethod
    def _ceo_dashboard(db: Session, tenant_id: Optional[str]) -> dict:
        """
        CEO Dashboard: Strategic view of all agents.

        Shows:
        - KPI Agent (progress to $100M/2000)
        - Risk Agent (operational/market/delivery risks)
        - CFO Agent (revenue/cash/EBITDA)
        - Forecast Agent (trajectory)
        - Scrum of Scrums (8:30 AM coordination)
        - Kill Switch candidates
        """

        agents = ["KPI Agent", "Risk Agent", "CFO Agent", "Forecast Agent", "Scrum of Scrums Agent"]
        kill_switch_eval = AgentKillSwitchService.evaluate_all_agents(db)

        return {
            "dashboard_type": "CEO_STRATEGIC",
            "description": "Executive strategic view - all agents, risks, forecast",
            "featured_agents": agents,
            "widgets": [
                {
                    "type": "progress_panel",
                    "title": "$100M Revenue Target",
                    "agents": ["CFO Agent", "Opportunity Tracker Agent"],
                },
                {
                    "type": "headcount_panel",
                    "title": "2000 Employee Target",
                    "agents": ["Thunder", "HR Agent", "Onboarding Agent"],
                },
                {
                    "type": "risk_panel",
                    "title": "Operational Risks",
                    "agents": ["Risk Agent"],
                },
                {
                    "type": "forecast_panel",
                    "title": "Trajectory Forecast",
                    "agents": ["Forecast Agent"],
                },
                {
                    "type": "kill_switch_panel",
                    "title": "Agent Health",
                    "kill_switch_candidates": kill_switch_eval["kill_switch_candidates"],
                    "at_risk": kill_switch_eval["at_risk"],
                },
            ],
            "refresh_interval": 300,  # 5 min for CEO
        }

    @staticmethod
    def _recruiter_dashboard(db: Session, tenant_id: Optional[str]) -> dict:
        """
        Recruiter Dashboard: Recruitment pipeline focus.

        Shows:
        - Thunder (AI recruiter status + hires)
        - Recruitment Agent (job creation + candidates)
        - Interview pipeline (interviews scheduled/completed)
        - Offer acceptance rate
        - Time-to-fill metrics
        """

        return {
            "dashboard_type": "RECRUITER_PIPELINE",
            "description": "Recruitment pipeline - Thunder status, candidates, interviews, offers",
            "featured_agents": ["Thunder", "Recruitment Agent", "Interview Reminder Agent"],
            "widgets": [
                {
                    "type": "recruitment_pipeline",
                    "title": "Hiring Funnel",
                    "stages": ["Candidates", "Interviews", "Offers", "Hired"],
                    "agents": ["Thunder", "Recruitment Agent"],
                },
                {
                    "type": "fear_score",
                    "title": "Thunder Fear Score",
                    "agents": ["Thunder"],
                },
                {
                    "type": "time_to_fill",
                    "title": "Average Time-to-Fill",
                    "agents": ["Thunder"],
                },
                {
                    "type": "offer_acceptance",
                    "title": "Offer Acceptance Rate",
                    "target": "90%",
                },
            ],
            "refresh_interval": 120,  # 2 min for active recruiting
        }

    @staticmethod
    def _hr_dashboard(db: Session, tenant_id: Optional[str]) -> dict:
        """
        HR Dashboard: People & culture focus.

        Shows:
        - HR Agent (lifecycle tracking)
        - Employee Mental Health Agent (wellbeing)
        - Onboarding Agent (progress)
        - Buddy Program Agent (mentoring)
        - Retention Rate
        - Culture Health Score
        """

        return {
            "dashboard_type": "HR_PEOPLE",
            "description": "Employee lifecycle - retention, wellbeing, onboarding, culture",
            "featured_agents": [
                "HR Agent",
                "Employee Mental Health Agent",
                "Onboarding Agent",
                "Buddy Program Agent",
            ],
            "widgets": [
                {
                    "type": "retention_panel",
                    "title": "Retention Rate",
                    "agents": ["HR Agent", "Employee Mental Health Agent"],
                },
                {
                    "type": "onboarding_panel",
                    "title": "Onboarding Progress",
                    "agents": ["Onboarding Agent"],
                },
                {
                    "type": "culture_panel",
                    "title": "Culture Health",
                    "agents": ["Culture Agent", "Feedback Agent"],
                },
                {
                    "type": "mental_health_panel",
                    "title": "Employee Wellbeing",
                    "agents": ["Employee Mental Health Agent"],
                },
            ],
            "refresh_interval": 300,  # 5 min for HR
        }

    @staticmethod
    def _finance_dashboard(db: Session, tenant_id: Optional[str]) -> dict:
        """
        Finance Dashboard: Revenue & profitability focus.

        Shows:
        - CFO Agent (revenue/EBITDA/cash)
        - Partner ROI Agent (partner revenue)
        - Opportunity Tracker (pipeline forecast)
        - Margin Agent (profitability)
        - Revenue Recognition (AR/billing)
        """

        return {
            "dashboard_type": "FINANCE_REVENUE",
            "description": "Financial tracking - revenue, pipeline, margins, cash",
            "featured_agents": [
                "CFO Agent",
                "Partner ROI Agent",
                "Opportunity Tracker Agent",
                "Margin Agent",
                "Revenue Recognition Agent",
            ],
            "widgets": [
                {
                    "type": "revenue_panel",
                    "title": "$100M Revenue Target",
                    "agents": ["CFO Agent"],
                },
                {
                    "type": "pipeline_panel",
                    "title": "Sales Pipeline",
                    "agents": ["Opportunity Tracker Agent"],
                },
                {
                    "type": "partner_revenue_panel",
                    "title": "Partner Revenue",
                    "agents": ["Partner ROI Agent"],
                },
                {
                    "type": "margin_panel",
                    "title": "Profitability",
                    "agents": ["Margin Agent"],
                },
                {
                    "type": "cash_panel",
                    "title": "Cash Position",
                    "agents": ["Cash Flow Agent"],
                },
            ],
            "refresh_interval": 240,  # 4 min for finance
        }

    @staticmethod
    def _manager_dashboard(db: Session, tenant_id: Optional[str]) -> dict:
        """
        Manager Dashboard: Team & utilization focus.

        Shows:
        - Resource Management Agent (utilization %)
        - Deployment Agent (project assignments)
        - Performance Agent (team KPIs)
        - Project Health (delivery status)
        """

        return {
            "dashboard_type": "MANAGER_OPERATIONS",
            "description": "Team operations - utilization, deployment, performance",
            "featured_agents": [
                "Resource Management Agent",
                "Deployment Agent",
                "Performance Agent",
            ],
            "widgets": [
                {
                    "type": "utilization_panel",
                    "title": "Team Utilization",
                    "target": "75%",
                    "agents": ["Resource Management Agent"],
                },
                {
                    "type": "deployment_panel",
                    "title": "Project Assignments",
                    "agents": ["Deployment Agent"],
                },
                {
                    "type": "performance_panel",
                    "title": "Team Performance",
                    "agents": ["Performance Agent"],
                },
            ],
            "refresh_interval": 300,
        }

    @staticmethod
    def _employee_dashboard(db: Session, tenant_id: Optional[str]) -> dict:
        """
        Employee Dashboard: Personal & task focus.

        Shows:
        - My Timesheet (hours/project allocation)
        - My Tasks (assigned work)
        - My Performance (against goals)
        - Learning Opportunities
        """

        return {
            "dashboard_type": "EMPLOYEE_PERSONAL",
            "description": "Personal dashboard - timesheet, tasks, performance, growth",
            "featured_agents": [],
            "widgets": [
                {
                    "type": "timesheet_panel",
                    "title": "My Timesheet",
                },
                {
                    "type": "tasks_panel",
                    "title": "My Tasks",
                },
                {
                    "type": "performance_panel",
                    "title": "My Performance",
                },
                {
                    "type": "learning_panel",
                    "title": "Learning Paths",
                },
            ],
            "refresh_interval": 600,
        }
