"""
Agent Daily Standup Service

8:00 AM EST: Sequential standup where each sub-agent reports their metrics
with validation questions to ensure legitimacy.

8:30 AM EST: Scrum of Scrums with Flash, CEO Agent, Feedback Agent, and
Partner Agents (Troy, Curtis) to ensure direction toward $100M/2000 employee target.

This is an aggressive execution system where Flash drives the build.
Every update is questioned and validated.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.agent_logging import log_agent_execution
from app.models.agent_execution_log import AgentExecutionLog
from app.services.agent_registry_service import AgentRegistry, AgentTier


class AgentDailyStandup:
    """8:00 AM EST sequential standup with validation for each agent."""

    # EST Times
    STANDUP_TIME_EST = "08:00"  # 8:00 AM EST
    SCRUM_TIME_EST = "08:30"    # 8:30 AM EST

    # Standup ordering: agents report sequentially in priority order
    STANDUP_ORDER = [
        # Tier 1: Core recruiting (must report first)
        "Thunder",
        "Recruitment Agent",
        "Supervisor Agent",

        # Tier 2: Resource & allocation (impacts placements)
        "Resource Management Agent",
        "Core-Pull Conflict Agent",

        # Tier 3: Finance & business (revenue/costs)
        "CFO Agent",
        "CEO/FY Progress Agent",
        "Partner ROI Agent",

        # Tier 4: Employee/HR (people ops)
        "Onboarding Agent",
        "HR Agent",
        "Employee Mental Health Agent",
        "Buddy Program Agent",
        "Employee Milestone Agent",

        # Tier 5: KPI tracking (strategic)
        "KPI Agent",

        # Tier 6: Support & engagement
        "Engagement/Outreach Agent",
        "Interview Reminder Agent",
        "Activity Feed Agent",
        "Executive Signal Agent",

        # Tier 7: Scoring & decisions (informational)
        "Abandonment Scoring Agent",
        "Compensation Scoring Agent",
        "Desire Intelligence Agent",
    ]

    @staticmethod
    @log_agent_execution("Agent Standup Coordinator", "generate_standup_report")
    async def generate_standup_report(
        tenant_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        8:00 AM EST: Sequential standup where each agent reports.

        Each agent reports:
        - Yesterday's executions and success rate
        - Key metric movement (up/down/flat)
        - Blockers or issues
        - Progress toward 2000 employee / $100M target

        System validates each report and flags inconsistencies.
        """
        try:
            yesterday = datetime.utcnow().date() - timedelta(days=1)
            standup_entries = []
            validation_issues = []

            # Get logs for yesterday
            logs_query = db.query(AgentExecutionLog).filter(
                AgentExecutionLog.execution_at >= datetime.combine(yesterday, datetime.min.time()),
                AgentExecutionLog.execution_at < datetime.combine(yesterday + timedelta(days=1), datetime.min.time()),
            )

            for agent_name in AgentDailyStandup.STANDUP_ORDER:
                agent = AgentRegistry.get_agent(agent_name)
                if not agent:
                    continue

                # Get this agent's logs for yesterday
                agent_logs = logs_query.filter(
                    AgentExecutionLog.agent_name == agent_name
                ).all()

                # Calculate metrics
                execution_count = len(agent_logs)
                success_count = sum(1 for log in agent_logs if log.success)
                success_rate = (success_count / execution_count * 100) if execution_count > 0 else 0
                total_duration_ms = sum(log.duration_ms or 0 for log in agent_logs)
                avg_duration_ms = total_duration_ms // execution_count if execution_count > 0 else 0
                errors = [log.error_message for log in agent_logs if not log.success and log.error_message]

                # Determine status
                if execution_count == 0:
                    status = "not_running"
                    severity = "critical"
                elif success_rate >= 95:
                    status = "healthy"
                    severity = "ok"
                elif success_rate >= 80:
                    status = "degraded"
                    severity = "warning"
                else:
                    status = "failing"
                    severity = "critical"

                # VALIDATION QUESTIONS
                validation_concerns = []

                # Q1: If agent didn't run, why?
                if execution_count == 0 and agent.status.value == "operational":
                    validation_concerns.append({
                        "question": "Agent marked operational but no executions yesterday. Is it alive?",
                        "severity": "critical",
                        "requires_investigation": True
                    })

                # Q2: If success rate dropped significantly
                if success_rate < 80 and agent.tier.value in ["core", "resource", "finance"]:
                    validation_concerns.append({
                        "question": f"Critical tier agent at {success_rate:.0f}% success. Root cause?",
                        "severity": "critical",
                        "requires_investigation": True
                    })

                # Q3: If executions suddenly increased (possible runaway loop)
                if execution_count > 1000:
                    validation_concerns.append({
                        "question": f"Abnormally high executions: {execution_count} yesterday. Runaway loop?",
                        "severity": "warning",
                        "requires_investigation": True
                    })

                # Q4: If errors present but success_rate doesn't reflect it
                if errors and success_rate > 90:
                    validation_concerns.append({
                        "question": "Errors recorded but success rate high. Log corruption?",
                        "severity": "warning",
                        "requires_investigation": False
                    })

                entry = {
                    "agent_name": agent_name,
                    "tier": agent.tier.value,
                    "status": status,
                    "severity": severity,
                    "executions": execution_count,
                    "success_rate": round(success_rate, 1),
                    "avg_duration_ms": avg_duration_ms,
                    "errors": errors[:3] if errors else None,  # Top 3 errors
                    "validation_concerns": validation_concerns,
                }

                standup_entries.append(entry)

                # Collect validation issues for later review
                if validation_concerns:
                    validation_issues.append({
                        "agent": agent_name,
                        "concerns": validation_concerns
                    })

            # Aggregate by tier
            tier_summary = {}
            for tier in AgentTier:
                tier_agents = [e for e in standup_entries if e["tier"] == tier.value]
                if tier_agents:
                    tier_summary[tier.value] = {
                        "agent_count": len(tier_agents),
                        "healthy": sum(1 for a in tier_agents if a["status"] == "healthy"),
                        "degraded": sum(1 for a in tier_agents if a["status"] == "degraded"),
                        "failing": sum(1 for a in tier_agents if a["status"] == "failing"),
                        "not_running": sum(1 for a in tier_agents if a["status"] == "not_running"),
                    }

            return {
                "status": "success",
                "standup_time": "8:00 AM EST",
                "date": yesterday.isoformat(),
                "total_agents_reporting": len(standup_entries),
                "tier_summary": tier_summary,
                "agent_reports": standup_entries,
                "validation_issues": validation_issues,
                "requires_review": len(validation_issues) > 0,
                "ceo_focus_areas": [
                    f"{v['agent']} - {v['concerns'][0]['question']}"
                    for v in validation_issues
                    if v["concerns"] and v["concerns"][0]["severity"] == "critical"
                ][:5]  # Top 5 critical items
            }

        except Exception as e:
            raise

    @staticmethod
    @log_agent_execution("Agent Standups Coordinator", "scrum_of_scrums")
    async def scrum_of_scrums(
        tenant_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        8:30 AM EST: Scrum of Scrums with key agents.

        Participants:
        - Flash (execution engine, drives toward $100M/2000 employees)
        - CEO Agent (strategic oversight)
        - Feedback Agent (weekly feedback synthesis)
        - Partner Agents (Troy, Curtis - partner-specific goals)

        Output: Decisions, escalations, strategic direction.
        """
        try:
            yesterday = datetime.utcnow().date() - timedelta(days=1)

            # Get Flash's performance
            flash_logs = db.query(AgentExecutionLog).filter(
                AgentExecutionLog.agent_name == "Flash",
                AgentExecutionLog.execution_at >= datetime.combine(yesterday, datetime.min.time()),
            ).all()

            flash_executions = len(flash_logs)
            flash_success = sum(1 for log in flash_logs if log.success)
            flash_success_rate = (flash_success / flash_executions * 100) if flash_executions > 0 else 0

            # Get Thunder's recruitment metrics
            thunder_logs = db.query(AgentExecutionLog).filter(
                AgentExecutionLog.agent_name == "Thunder",
                AgentExecutionLog.execution_at >= datetime.combine(yesterday, datetime.min.time()),
            ).all()

            thunder_executions = len(thunder_logs)
            thunder_success = sum(1 for log in thunder_logs if log.success)
            thunder_success_rate = (thunder_success / thunder_executions * 100) if thunder_executions > 0 else 0

            # Get CEO insights
            standup = await AgentDailyStandup.generate_standup_report(
                tenant_id=tenant_id,
                db=db
            )

            # Flash's responsibilities
            flash_status = {
                "executions": flash_executions,
                "success_rate": round(flash_success_rate, 1),
                "role": "Execution engine - drives ALL operational decisions",
                "mission": "Drive toward $100M revenue / 2000 employees by 2030"
            }

            # CEO's directives (aggressive)
            ceo_directives = []

            # If Flash success rate low, escalate immediately
            if flash_success_rate < 95:
                ceo_directives.append({
                    "severity": "critical",
                    "directive": f"Flash at {flash_success_rate:.0f}% success. This drives everything. Fix NOW.",
                    "owner": "Flash + CEO",
                    "deadline": "12 hours"
                })

            # If recruitment (Thunder) slow, escalate
            if thunder_executions < 10:
                ceo_directives.append({
                    "severity": "high",
                    "directive": f"Thunder only {thunder_executions} executions. We need 20+/day to hit 2000 employees.",
                    "owner": "Thunder + Resource Management",
                    "deadline": "24 hours"
                })

            # Partner agent performance
            partner_status = {}
            for partner in ["Troy", "Curtis"]:
                partner_logs = db.query(AgentExecutionLog).filter(
                    AgentExecutionLog.agent_name == partner,
                    AgentExecutionLog.execution_at >= datetime.combine(yesterday, datetime.min.time()),
                ).all()
                partner_executions = len(partner_logs)
                partner_success = sum(1 for log in partner_logs if log.success)
                partner_rate = (partner_success / partner_executions * 100) if partner_executions > 0 else 0
                partner_status[partner] = {
                    "executions": partner_executions,
                    "success_rate": round(partner_rate, 1)
                }

            return {
                "status": "success",
                "scrum_time": "8:30 AM EST",
                "date": yesterday.isoformat(),
                "participants": ["Flash", "CEO Agent", "Feedback Agent", "Troy", "Curtis"],
                "flash_status": flash_status,
                "thunder_recruitment": {
                    "executions": thunder_executions,
                    "success_rate": round(thunder_success_rate, 1),
                    "daily_target": 20,
                    "monthly_target": 600,
                    "annual_target": 7200
                },
                "partner_agents": partner_status,
                "ceo_directives": ceo_directives,
                "critical_focus": len([d for d in ceo_directives if d["severity"] == "critical"]),
                "strategic_target": {
                    "revenue": "$100M by 2030",
                    "headcount": "2000 employees by 2030",
                    "daily_progress_metric": "Recruitment pipeline + placements + utilization"
                },
                "flash_accountability": "Flash is responsible for execution of ALL decisions made in scrum."
            }

        except Exception as e:
            raise
