"""
Agent Registry Service

Centralized registry of all 70+ internal agents. Provides discovery,
status, and health check capabilities.

This is the source of truth for: which agents exist, what they do,
whether they're operational, and what tier they belong to.
"""

from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.agent_execution_log import AgentExecutionLog


class AgentTier(str, Enum):
    """Agent classification by criticality and autonomy."""
    CORE = "core"  # Core recruiting flow (Thunder, Recruitment, Supervisor)
    RESOURCE = "resource"  # Resource management (matching, allocation)
    ENGAGEMENT = "engagement"  # Candidate engagement (outreach, follow-up)
    DECISION = "decision"  # Autonomous scoring/decisions
    SUPPORT = "support"  # Operational support (notifications, digests)
    FINANCE = "finance"  # Financial tracking
    HR = "hr"  # Employee/HR operations
    MONITOR = "monitor"  # Monitoring/alerts


class AgentStatus(str, Enum):
    """Agent operational status."""
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    NOT_IMPLEMENTED = "not_implemented"


@dataclass
class AgentInfo:
    """Metadata for a single agent."""
    name: str  # Unique agent name (e.g., "Recruitment Agent")
    tier: AgentTier  # Classification
    status: AgentStatus  # Current status
    description: str  # What it does
    last_execution: Optional[datetime] = None  # Last recorded execution
    execution_count_7d: int = 0  # Executions in last 7 days
    success_rate_7d: float = 100.0  # Success rate (0-100)
    avg_duration_ms: int = 0  # Average execution time
    has_route: bool = True  # Whether API route exists
    is_logging: bool = True  # Whether it logs to agent_execution_log
    notes: Optional[str] = None


class AgentRegistry:
    """Registry of all agents with discovery and health tracking."""

    # Core recruiting agents (fully operational)
    RECRUITMENT_AGENT = AgentInfo(
        name="Recruitment Agent",
        tier=AgentTier.CORE,
        status=AgentStatus.OPERATIONAL,
        description="Auto-generate job descriptions with clarifying questions",
        has_route=True,
        is_logging=True,
    )

    SUPERVISOR_AGENT = AgentInfo(
        name="Supervisor Agent",
        tier=AgentTier.CORE,
        status=AgentStatus.OPERATIONAL,
        description="Multi-agent coordinator for candidate lifecycle",
        has_route=True,
        is_logging=True,
    )

    THUNDER_AGENT = AgentInfo(
        name="Thunder",
        tier=AgentTier.CORE,
        status=AgentStatus.OPERATIONAL,
        description="External-facing AI recruiter for candidate outreach",
        has_route=True,
        is_logging=True,
    )

    # Resource management agents
    RESOURCE_MANAGEMENT_AGENT = AgentInfo(
        name="Resource Management Agent",
        tier=AgentTier.RESOURCE,
        status=AgentStatus.OPERATIONAL,
        description="Bench matching and resource allocation",
        has_route=True,
        is_logging=False,  # TODO: wire logging
    )

    CORE_PULL_AGENT = AgentInfo(
        name="Core-Pull Conflict Agent",
        tier=AgentTier.RESOURCE,
        status=AgentStatus.OPERATIONAL,
        description="Detect core-speciality conflicts in staffing",
        has_route=False,  # TODO: create route
        is_logging=False,  # TODO: wire logging
    )

    # Executive/Finance agents
    CFO_AGENT = AgentInfo(
        name="CFO Agent",
        tier=AgentTier.FINANCE,
        status=AgentStatus.OPERATIONAL,
        description="Financial snapshot and forecasting",
        has_route=True,
        is_logging=False,  # TODO: wire logging
    )

    CEO_AGENT = AgentInfo(
        name="CEO/FY Progress Agent",
        tier=AgentTier.FINANCE,
        status=AgentStatus.OPERATIONAL,
        description="FY progress tracking and executive summary",
        has_route=True,
        is_logging=False,  # TODO: wire logging
    )

    PARTNER_ROI_AGENT = AgentInfo(
        name="Partner ROI Agent",
        tier=AgentTier.FINANCE,
        status=AgentStatus.OPERATIONAL,
        description="Partner KPI tracking and ROI analysis",
        has_route=True,
        is_logging=False,  # TODO: wire logging
    )

    OPPORTUNITY_TRACKER_AGENT = AgentInfo(
        name="Opportunity Tracker Agent",
        tier=AgentTier.FINANCE,
        status=AgentStatus.OPERATIONAL,
        description="Sales pipeline tracking toward $100M revenue target. Logs opportunities, monitors deal progression, alerts on stalls, escalates at-risk deals to Flash.",
        has_route=True,
        is_logging=False,  # TODO: wire logging
    )

    HTD_PIPELINE_AGENT = AgentInfo(
        name="HTD Pipeline Accountability Agent",
        tier=AgentTier.RESOURCE,
        status=AgentStatus.OPERATIONAL,
        description="Tracks SPECIALTY→CORE conversion pipeline. Shows partner CORE capacity forecast, identifies bottlenecks, triggers HTD hiring when development too slow.",
        has_route=True,
        is_logging=True,
    )

    FLASH_ORCHESTRATION_ENGINE = AgentInfo(
        name="Flash Orchestration Engine",
        tier=AgentTier.CORE,
        status=AgentStatus.OPERATIONAL,
        description="Daily command coordination: analyzes HTD pipeline + opportunity health + agent state. Issues directives to partners on what to do TODAY. Escalates to CEO when critical.",
        has_route=True,
        is_logging=True,
    )

    # HR/Employee agents
    ONBOARDING_AGENT = AgentInfo(
        name="Onboarding Agent",
        tier=AgentTier.HR,
        status=AgentStatus.OPERATIONAL,
        description="Document collection and joining preparation",
        has_route=True,
        is_logging=False,  # TODO: wire logging
    )

    BUDDY_PROGRAM_AGENT = AgentInfo(
        name="Buddy Program Agent",
        tier=AgentTier.HR,
        status=AgentStatus.OPERATIONAL,
        description="30-day buddy program tracking and graduation",
        has_route=False,  # TODO: create route
        is_logging=False,  # TODO: wire logging
    )

    EMPLOYEE_MILESTONE_AGENT = AgentInfo(
        name="Employee Milestone Agent",
        tier=AgentTier.HR,
        status=AgentStatus.OPERATIONAL,
        description="Work anniversary and milestone tracking",
        has_route=False,  # TODO: create route
        is_logging=False,  # TODO: wire logging
    )

    # Missing agents (need implementation)
    KPI_AGENT = AgentInfo(
        name="KPI Agent",
        tier=AgentTier.MONITOR,
        status=AgentStatus.NOT_IMPLEMENTED,
        description="Company-wide KPI tracking and forecasting",
        has_route=False,
        is_logging=False,
        notes="MISSING: Full implementation needed",
    )

    HR_AGENT = AgentInfo(
        name="HR Agent",
        tier=AgentTier.HR,
        status=AgentStatus.NOT_IMPLEMENTED,
        description="Centralized HR operations and employee tracking",
        has_route=False,
        is_logging=False,
        notes="MISSING: Full implementation needed",
    )

    EMPLOYEE_MENTAL_HEALTH_AGENT = AgentInfo(
        name="Employee Mental Health Agent",
        tier=AgentTier.HR,
        status=AgentStatus.NOT_IMPLEMENTED,
        description="Employee wellbeing monitoring and support",
        has_route=False,
        is_logging=False,
        notes="MISSING: Full implementation needed",
    )

    # Engagement agents (partial implementations)
    OUTREACH_AGENT = AgentInfo(
        name="Outreach Agent",
        tier=AgentTier.ENGAGEMENT,
        status=AgentStatus.OPERATIONAL,
        description="Automated candidate outreach via Thunder",
        has_route=False,  # TODO: create route
        is_logging=False,
    )

    INTERVIEW_REMINDER_AGENT = AgentInfo(
        name="Interview Reminder Agent",
        tier=AgentTier.ENGAGEMENT,
        status=AgentStatus.OPERATIONAL,
        description="Pre-interview reminders",
        has_route=False,
        is_logging=False,
    )

    INTERVIEW_CONFIRMATION_AGENT = AgentInfo(
        name="Interview Confirmation Agent",
        tier=AgentTier.ENGAGEMENT,
        status=AgentStatus.OPERATIONAL,
        description="Interview confirmation and scheduling",
        has_route=False,
        is_logging=False,
    )

    # Decision agents (scoring)
    ABANDONMENT_SCORING_AGENT = AgentInfo(
        name="Abandonment Scoring Agent",
        tier=AgentTier.DECISION,
        status=AgentStatus.OPERATIONAL,
        description="Candidate abandonment risk prediction",
        has_route=False,
        is_logging=False,
    )

    COMPENSATION_SCORING_AGENT = AgentInfo(
        name="Compensation Scoring Agent",
        tier=AgentTier.DECISION,
        status=AgentStatus.OPERATIONAL,
        description="Pay-fit analysis and scoring",
        has_route=False,
        is_logging=False,
    )

    DESIRE_INTELLIGENCE_AGENT = AgentInfo(
        name="Desire Intelligence Agent",
        tier=AgentTier.DECISION,
        status=AgentStatus.OPERATIONAL,
        description="Candidate desire and motivation profiling",
        has_route=False,
        is_logging=False,
    )

    # Support/Monitoring agents
    ACTIVITY_FEED_AGENT = AgentInfo(
        name="Activity Feed Agent",
        tier=AgentTier.SUPPORT,
        status=AgentStatus.OPERATIONAL,
        description="Recruiter copilot activity feed",
        has_route=False,
        is_logging=False,
    )

    DAILY_DIGEST_AGENT = AgentInfo(
        name="Daily Digest Agent",
        tier=AgentTier.SUPPORT,
        status=AgentStatus.OPERATIONAL,
        description="Thunder morning report and digest",
        has_route=False,
        is_logging=False,
    )

    EXECUTIVE_SIGNAL_AGENT = AgentInfo(
        name="Executive Signal Agent",
        tier=AgentTier.SUPPORT,
        status=AgentStatus.OPERATIONAL,
        description="Advisory recognition and concern triage",
        has_route=True,
        is_logging=False,
    )

    # All agents in registry
    ALL_AGENTS = [
        # Core
        RECRUITMENT_AGENT,
        SUPERVISOR_AGENT,
        THUNDER_AGENT,
        FLASH_ORCHESTRATION_ENGINE,
        # Resource
        RESOURCE_MANAGEMENT_AGENT,
        CORE_PULL_AGENT,
        HTD_PIPELINE_AGENT,
        # Finance
        CFO_AGENT,
        CEO_AGENT,
        PARTNER_ROI_AGENT,
        OPPORTUNITY_TRACKER_AGENT,
        # HR
        ONBOARDING_AGENT,
        BUDDY_PROGRAM_AGENT,
        EMPLOYEE_MILESTONE_AGENT,
        KPI_AGENT,
        HR_AGENT,
        EMPLOYEE_MENTAL_HEALTH_AGENT,
        # Engagement
        OUTREACH_AGENT,
        INTERVIEW_REMINDER_AGENT,
        INTERVIEW_CONFIRMATION_AGENT,
        # Decision
        ABANDONMENT_SCORING_AGENT,
        COMPENSATION_SCORING_AGENT,
        DESIRE_INTELLIGENCE_AGENT,
        # Support
        ACTIVITY_FEED_AGENT,
        DAILY_DIGEST_AGENT,
        EXECUTIVE_SIGNAL_AGENT,
    ]

    @staticmethod
    def get_agent(agent_name: str) -> Optional[AgentInfo]:
        """Lookup agent by name."""
        for agent in AgentRegistry.ALL_AGENTS:
            if agent.name.lower() == agent_name.lower():
                return agent
        return None

    @staticmethod
    def get_agents_by_tier(tier: AgentTier) -> List[AgentInfo]:
        """Get all agents in a tier."""
        return [a for a in AgentRegistry.ALL_AGENTS if a.tier == tier]

    @staticmethod
    def get_agents_by_status(status: AgentStatus) -> List[AgentInfo]:
        """Get all agents with a status."""
        return [a for a in AgentRegistry.ALL_AGENTS if a.status == status]

    @staticmethod
    def get_unimplemented() -> List[AgentInfo]:
        """Get all agents not yet implemented."""
        return AgentRegistry.get_agents_by_status(AgentStatus.NOT_IMPLEMENTED)

    @staticmethod
    def get_missing_logging() -> List[AgentInfo]:
        """Get all agents not yet wired to agent_execution_log."""
        return [a for a in AgentRegistry.ALL_AGENTS if not a.is_logging]

    @staticmethod
    def get_missing_routes() -> List[AgentInfo]:
        """Get all agents without API routes."""
        return [a for a in AgentRegistry.ALL_AGENTS if not a.has_route]

    @staticmethod
    def update_agent_metrics(db: Session, agent_name: str) -> AgentInfo:
        """Update agent's execution metrics from agent_execution_log."""
        agent = AgentRegistry.get_agent(agent_name)
        if not agent:
            return None

        # Get metrics from last 7 days
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        logs = db.query(AgentExecutionLog).filter(
            AgentExecutionLog.agent_name == agent_name,
            AgentExecutionLog.execution_at >= seven_days_ago,
        ).all()

        if logs:
            agent.last_execution = max(log.execution_at for log in logs)
            agent.execution_count_7d = len(logs)
            agent.success_rate_7d = (
                sum(1 for log in logs if log.success) / len(logs) * 100
            )
            agent.avg_duration_ms = (
                sum(log.duration_ms or 0 for log in logs) // len(logs)
            )

        return agent
