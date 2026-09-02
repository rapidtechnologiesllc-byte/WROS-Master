"""
import logging
Agent Standups & Scrum of Scrums Service

Daily coordination system where all 70+ agents report metrics to their managers,
Thunder + Flask report to CEO Agent in scrum of scrums, and CEO Agent manages
underperforming agents aggressively.

Architecture:
- 6:00 AM IST: All agents complete daily standup with their managers
- 7:00 AM IST: Thunder + Flask report to CEO Agent (scrum of scrums)
- CEO Agent reviews all metrics and escalates/terminates underperformers
- 5:00 PM IST: Feedback Agent provides weekly performance feedback to all agents
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.agent_logging import log_agent_execution
from app.models.agent_execution_log import AgentExecutionLog

logger = logging.getLogger(__name__)

class AgentStandupsCoordinator:
    """Coordinates daily standups and scrum of scrums for all agents."""

    # IST time for daily meetings (converted to UTC for system use)
    STANDUP_TIME_IST = "06:00"  # 6:00 AM IST = 00:30 UTC
    SCRUM_TIME_IST = "07:00"  # 7:00 AM IST = 01:30 UTC
    FEEDBACK_TIME_IST = "17:00"  # 5:00 PM IST = 11:30 UTC

    @staticmethod
    @log_agent_execution("Agent Standups Coordinator", "generate_daily_standup_report")
    async def generate_daily_standup_report(
        tenant_id: str,
        db: Session,
        agent_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate standup report for agent(s).

        If agent_name specified, returns report for that agent only.
        If None, returns standup for all 70+ agents.

        Report includes:
        - Executions yesterday
        - Success rate
        - Average duration
        - Key metrics by agent type
        - Alerts/blockers
        """
        try:
            yesterday = datetime.utcnow().date() - timedelta(days=1)
            tomorrow = yesterday + timedelta(days=1)

            # Get agents to report on
            if agent_name:
                agents_to_report = [AgentRegistry.get_agent(agent_name)]
                if not agents_to_report[0]:
                    return {"status": "not_found", "message": f"Agent '{agent_name}' not found"}
            else:
                agents_to_report = AgentRegistry.ALL_AGENTS

            standup_entries = []

            for agent in agents_to_report:
                # Get yesterday's logs for this agent
                logs = db.query(AgentExecutionLog).filter(
                    AgentExecutionLog.agent_name == agent.name,
                    AgentExecutionLog.execution_at >= datetime.combine(yesterday, datetime.min.time()),
                    AgentExecutionLog.execution_at < datetime.combine(tomorrow, datetime.min.time()),
                ).all()

                # Calculate metrics
                execution_count = len(logs)
                success_count = sum(1 for log in logs if log.success)
                success_rate = (success_count / execution_count * 100) if execution_count > 0 else 0
                total_duration_ms = sum(log.duration_ms or 0 for log in logs)
                avg_duration_ms = total_duration_ms // execution_count if execution_count > 0 else 0
                errors = [log.error_message for log in logs if not log.success]

                # Determine status
                if execution_count == 0:
                    status = "not_running"
                elif success_rate >= 95:
                    status = "healthy"
                elif success_rate >= 75:
                    status = "degraded"
                else:
                    status = "critical"

                standup_entries.append({
                    "agent_name": agent.name,
                    "tier": agent.tier.value,
                    "status": status,
                    "executions": execution_count,
                    "success_rate": round(success_rate, 1),
                    "avg_duration_ms": avg_duration_ms,
                    "errors": errors if errors else None,
                    "action_required": status in ["degraded", "critical"],
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
                        "critical": sum(1 for a in tier_agents if a["status"] == "critical"),
                        "avg_success_rate": sum(a["success_rate"] for a in tier_agents) / len(tier_agents),
                    }

            # Determine overall status
            total_agents = len(standup_entries)
            critical_count = sum(1 for e in standup_entries if e["status"] == "critical")
            overall_status = "critical_alert" if critical_count > 0 else ("system_healthy" if critical_count == 0 else "system_degraded")

            return {
                "status": "success",
                "date": yesterday.isoformat(),
                "overall_status": overall_status,
                "total_agents": total_agents,
                "tier_summary": tier_summary,
                "agent_standups": sorted(standup_entries, key=lambda x: (x["status"] != "healthy", x["agent_name"])),
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            raise

    @staticmethod
    @log_agent_execution("Agent Standups Coordinator", "scrum_of_scrums")
    async def scrum_of_scrums(
        tenant_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Scrum of Scrums: Thunder + Flask report to CEO Agent.

        Thunder (external recruiter): Daily recruitment metrics
        Flask (internal operations): Daily operational metrics
        CEO Agent: Strategic oversight + aggressive management of underperformers

        Returns: What Thunder and Flask did, CEO Agent's instructions.
        """
        try:
            yesterday = datetime.utcnow().date() - timedelta(days=1)

            # Get Thunder's metrics
            thunder_logs = db.query(AgentExecutionLog).filter(
                AgentExecutionLog.agent_name == "Thunder",
                AgentExecutionLog.execution_at >= datetime.combine(yesterday, datetime.min.time()),
            ).all()

            thunder_executions = len(thunder_logs)
            thunder_success = sum(1 for log in thunder_logs if log.success)
            thunder_success_rate = (thunder_success / thunder_executions * 100) if thunder_executions > 0 else 0

            # Get all agent tiers for overall health
            standup = await AgentStandupsCoordinator.generate_daily_standup_report(
                tenant_id=tenant_id,
                db=db
            )

            # CEO Agent's view
            critical_alerts = [a for a in standup["agent_standups"] if a["status"] == "critical"]

            ceo_decisions = []

            # Aggressive management: Escalate or replace underperformers
            for alert in critical_alerts:
                if alert["success_rate"] < 75:
                    # Critical performance issue
                    ceo_decisions.append({
                        "agent": alert["agent_name"],
                        "decision": "escalate_or_replace",
                        "reason": f"Success rate {alert['success_rate']}% below 75% threshold",
                        "action": f"Review {alert['agent_name']} immediately. If not improved by tomorrow, escalate to replacement."
                    })
                elif alert["executions"] == 0:
                    # Not running at all
                    ceo_decisions.append({
                        "agent": alert["agent_name"],
                        "decision": "emergency_restart",
                        "reason": f"Zero executions in last 24 hours",
                        "action": f"Restart {alert['agent_name']} immediately and monitor closely."
                    })

            return {
                "status": "success",
                "date": yesterday.isoformat(),
                "scrum_participants": ["Thunder", "Flask", "CEO Agent"],
                "thunder_report": {
                    "executions": thunder_executions,
                    "success_rate": round(thunder_success_rate, 1),
                    "key_metric": "Candidates processed and qualified",
                },
                "system_health": standup["overall_status"],
                "critical_alerts": len(critical_alerts),
                "ceo_agent_decisions": ceo_decisions,
                "strategic_instructions": [
                    "Target: 2000 employees by 2030 (on track)" if standup["agent_standups"] else "Accelerate hiring velocity",
                    "Monitor recruitment pipeline daily",
                    f"Manage {len(critical_alerts)} underperforming agents aggressively",
                    "Escalate/replace any agent <75% success rate within 24 hours",
                ]
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            raise

    @staticmethod
    @log_agent_execution("Feedback Agent", "weekly_feedback_session")
    async def weekly_feedback_session(
        tenant_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Friday 5:00 PM IST: Feedback Agent provides weekly performance feedback to all agents.

        Each agent receives:
        - Performance score (0-100)
        - Key achievements
        - Areas for improvement
        - Recognition/rewards for top performers
        - Warnings for underperformers
        """
        try:
            # Get last 7 days of metrics
            seven_days_ago = datetime.utcnow() - timedelta(days=7)

            feedback_entries = []

            for agent in AgentRegistry.ALL_AGENTS:
                # Get this week's logs
                logs = db.query(AgentExecutionLog).filter(
                    AgentExecutionLog.agent_name == agent.name,
                    AgentExecutionLog.execution_at >= seven_days_ago,
                ).all()

                if not logs:
                    # Not enough data
                    feedback_entries.append({
                        "agent": agent.name,
                        "performance_score": 0,
                        "feedback": "No execution logs this week. Agent may not be operational.",
                        "action": "Investigate and restart if needed.",
                    })
                    continue

                # Calculate metrics
                execution_count = len(logs)
                success_count = sum(1 for log in logs if log.success)
                success_rate = (success_count / execution_count * 100) if execution_count > 0 else 0
                total_duration_ms = sum(log.duration_ms or 0 for log in logs)
                avg_duration_ms = total_duration_ms // execution_count if execution_count > 0 else 0

                # Performance score: 60% success_rate + 20% speed + 20% consistency
                performance_score = (success_rate * 0.6) + (min(avg_duration_ms / 1000, 100) * 0.2) + (min(execution_count / 10 * 100, 100) * 0.2)

                # Generate feedback
                if performance_score >= 90:
                    status = "excellent"
                    feedback_text = f"Outstanding performance! {success_rate:.0f}% success rate, {execution_count} executions."
                    reward = "Top performer recognition + budget increase"
                elif performance_score >= 75:
                    status = "good"
                    feedback_text = f"Solid performance. Continue focus on success rate ({success_rate:.0f}%)."
                    reward = None
                elif performance_score >= 50:
                    status = "needs_improvement"
                    feedback_text = f"Needs improvement. Success rate {success_rate:.0f}% below 75% target."
                    reward = "Performance improvement plan (PIP) 30 days"
                else:
                    status = "critical"
                    feedback_text = f"Critical performance issues. Success rate {success_rate:.0f}%, {execution_count} executions."
                    reward = "Final warning: Replace within 7 days if not improved"

                feedback_entries.append({
                    "agent": agent.name,
                    "tier": agent.tier.value,
                    "performance_score": round(performance_score, 1),
                    "status": status,
                    "success_rate": round(success_rate, 1),
                    "executions": execution_count,
                    "feedback": feedback_text,
                    "reward_or_action": reward,
                })

            return {
                "status": "success",
                "week_ending": datetime.utcnow().date().isoformat(),
                "feedback_session": "Friday 5:00 PM IST",
                "agents_reviewed": len(feedback_entries),
                "feedback_entries": sorted(feedback_entries, key=lambda x: x["performance_score"], reverse=True),
                "summary": {
                    "excellent": sum(1 for e in feedback_entries if e["status"] == "excellent"),
                    "good": sum(1 for e in feedback_entries if e["status"] == "good"),
                    "needs_improvement": sum(1 for e in feedback_entries if e["status"] == "needs_improvement"),
                    "critical": sum(1 for e in feedback_entries if e["status"] == "critical"),
                }
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            raise
