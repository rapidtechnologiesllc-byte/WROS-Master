"""
import logging
Master Agent Dashboard - All 75 Agents at a Glance

Shows status of every agent:
- Fear score (20-100)
- Progress to FY target
- Progress to 2030 target
- Blockers
- Cascading impact (which downstream agents depend on this one)

This is Flash's control center.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.services.agent_registry_service import AGENT_REGISTRY
from app.models.agent_state_target import AgentActualPerformance
from app.core.logging import logger

logger = logging.getLogger(__name__)

class MasterAgentDashboard:
    """Master dashboard showing all agents."""

    @staticmethod
    def get_all_agents_health(db: Session, tenant_id: str) -> Dict[str, Any]:
        """
        Get health status of ALL agents in the system.

        Shows:
        - Total agents
        - How many are healthy (fear <50)
        - How many are at risk (fear 50-70)
        - How many are critical (fear >70)
        - Which ones are cascading failures (others depend on them)
        """

        agents_data = []

        for agent_name, agent_config in sorted(AGENT_REGISTRY.items()):
            agent_data = MasterAgentDashboard._get_agent_health(
                db, agent_name, agent_config, tenant_id
            )
            agents_data.append(agent_data)

        # Calculate statistics
        total_agents = len(agents_data)
        healthy = sum(1 for a in agents_data if a.get("fear_score", 50) <= 50)
        at_risk = sum(1 for a in agents_data if 50 < a.get("fear_score", 50) <= 70)
        critical = sum(1 for a in agents_data if a.get("fear_score", 50) > 70)

        # Group by tier (for organizational clarity)
        by_tier = {}
        for agent in agents_data:
            tier = agent.get("tier", "unknown")
            if tier not in by_tier:
                by_tier[tier] = []
            by_tier[tier].append(agent)

        # Sort by fear score descending (critical first)
        agents_data.sort(key=lambda x: -x.get("fear_score", 50))

        # Identify cascading failures (critical agents that others depend on)
        cascading = MasterAgentDashboard._identify_cascading_failures(agents_data)

        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_agents": total_agents,
                "healthy_count": healthy,
                "healthy_pct": round(healthy / total_agents * 100, 1) if total_agents > 0 else 0,
                "at_risk_count": at_risk,
                "at_risk_pct": round(at_risk / total_agents * 100, 1) if total_agents > 0 else 0,
                "critical_count": critical,
                "critical_pct": round(critical / total_agents * 100, 1) if total_agents > 0 else 0,
                "cascading_failures": len(cascading),
            },
            "agents": agents_data,
            "by_tier": by_tier,
            "cascading_failures": cascading,
            "flash_alert": MasterAgentDashboard._generate_flash_alert(
                healthy, at_risk, critical, cascading
            ),
            "health_rating": (
                "🟢 HEALTHY" if critical == 0 and at_risk <= 2
                else "🟡 CAUTION" if critical <= 2
                else "🔴 CRITICAL"
            )
        }

    @staticmethod
    def _get_agent_health(
        db: Session, agent_name: str, agent_config: Dict, tenant_id: str
    ) -> Dict[str, Any]:
        """Get health status for one agent."""

        try:
            # Get latest performance data
            performance = (
                db.query(AgentActualPerformance)
                .filter(AgentActualPerformance.agent_name == agent_name)
                .order_by(desc(AgentActualPerformance.recorded_at))
                .first()
            )

            # Extract config
            fy_target = agent_config.get("fy_target", {})
            y2030_target = agent_config.get("y2030_target", {})
            authority = agent_config.get("authority", 0)
            domain = agent_config.get("domain", "unknown")
            tier = agent_config.get("tier", "unknown")
            owner = agent_config.get("owner", "unknown")
            strategic_importance = agent_config.get("strategic_importance", "LOW")

            # Calculate fear score
            fear_score = 50  # Default neutral
            fy_progress_pct = 0
            y2030_progress_pct = 0

            if performance:
                fy_progress_pct = performance.fy_progress_pct or 0
                y2030_progress_pct = performance.y2030_progress_pct or 0

                # Fear score = 20 + (gap_percent × 0.8)
                gap_pct = max(0, 100 - fy_progress_pct)
                fear_score = 20 + (gap_pct * 0.8)
                fear_score = min(100, max(20, fear_score))  # Clamp 20-100
            else:
                fear_score = 50  # No data = neutral

            # Determine status
            if fear_score <= 50:
                status = "HEALTHY"
            elif fear_score <= 70:
                status = "WARNING"
            else:
                status = "CRITICAL"

            # Build agent card
            return {
                "agent_name": agent_name,
                "domain": domain,
                "tier": tier,
                "owner": owner,
                "authority": authority,
                "strategic_importance": strategic_importance,
                "fear_score": round(fear_score, 1),
                "status": status,
                "fy_progress_pct": round(fy_progress_pct, 1),
                "fy_target": fy_target.get("value"),
                "fy_target_unit": fy_target.get("unit", ""),
                "y2030_progress_pct": round(y2030_progress_pct, 1),
                "y2030_target": y2030_target.get("value"),
                "y2030_target_unit": y2030_target.get("unit", ""),
                "has_performance_data": performance is not None,
                "last_recorded": performance.recorded_at.isoformat() if performance else None,
                "success_rate": performance.success_rate if performance else None,
                "execution_count": performance.execution_count if performance else None,
                "escalation_score": MasterAgentDashboard._calculate_escalation_score(
                    fear_score, authority, strategic_importance
                ),
            }

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error getting health for {agent_name}: {str(e)}")
            return {
                "agent_name": agent_name,
                "status": "ERROR",
                "error": str(e)
            }

    @staticmethod
    def _calculate_escalation_score(fear_score: float, authority: int, importance: str) -> str:
        """Calculate if this agent needs escalation."""
        importance_weight = {
            "CRITICAL": 3,
            "HIGH": 2,
            "MEDIUM": 1,
            "LOW": 0
        }

        weight = importance_weight.get(importance, 0)
        score = (fear_score / 100) * (authority + 1) * (weight + 1)

        if score > 7:
            return "ESCALATE_TO_CEO"
        elif score > 5:
            return "ESCALATE_TO_FLASH"
        elif score > 3:
            return "MONITOR"
        else:
            return "OK"

    @staticmethod
    def _identify_cascading_failures(agents_data: List[Dict]) -> List[Dict]:
        """
        Identify cascading failures - critical agents that other agents depend on.

        Example:
        - Thunder is CRITICAL
        - Recruitment Agent depends on Thunder
        - Interview Scheduler depends on Recruitment Agent
        - So Thunder's failure cascades to 2+ downstream agents
        """

        # Dependency map (simplified - would be more complex in production)
        dependency_map = {
            "Thunder": ["Recruitment Agent", "Interview Reminder Agent", "Offer Letter Agent"],
            "Recruitment Agent": ["Interview Reminder Agent", "Supervisor Agent"],
            "Interview Reminder Agent": ["Hiring Panel", "Offer Letter Agent"],
            "Supervisor Agent": ["Resource Management Agent", "HTD Pipeline Agent"],
            "Resource Management Agent": ["Core-Pull Conflict Agent", "Workforce Forecasting Agent"],
            "HTD Pipeline Agent": ["Employee Onboarding Agent", "Buddy Program Agent"],
        }

        cascading = []

        for agent in agents_data:
            if agent.get("status") == "CRITICAL":
                agent_name = agent.get("agent_name")
                downstream = dependency_map.get(agent_name, [])

                if downstream:
                    cascading.append({
                        "critical_agent": agent_name,
                        "fear_score": agent.get("fear_score"),
                        "downstream_count": len(downstream),
                        "downstream_agents": downstream,
                        "impact": f"{agent_name} is CRITICAL - affects {len(downstream)} downstream agents"
                    })

        return cascading

    @staticmethod
    def _generate_flash_alert(healthy: int, at_risk: int, critical: int, cascading: List) -> str:
        """Generate Flash's alert message."""

        total = healthy + at_risk + critical

        if critical >= 3:
            return f"🚨 CRITICAL: {critical} agents failing, {len(cascading)} cascading. ESCALATE TO CEO NOW."
        elif critical == 2:
            return f"⚠️ HIGH: {critical} critical agents, {at_risk} at-risk. Investigate cascading failures."
        elif critical == 1 and len(cascading) > 0:
            return f"⚠️ WARNING: {critical} critical agent with downstream impact. Fix immediately."
        elif at_risk >= 5:
            return f"📊 MONITOR: {at_risk} agents at-risk. Trend watch."
        else:
            return f"✅ HEALTHY: {healthy}/{total} agents healthy. {at_risk} at-risk, {critical} critical."

    @staticmethod
    def get_agent_by_domain(db: Session, tenant_id: str, domain: str) -> Dict[str, Any]:
        """Get all agents in a specific domain (e.g., recruitment, finance, hr)."""

        all_health = MasterAgentDashboard.get_all_agents_health(db, tenant_id)

        domain_agents = [a for a in all_health["agents"] if a.get("domain") == domain]

        return {
            "domain": domain,
            "agent_count": len(domain_agents),
            "agents": domain_agents,
            "health_summary": {
                "healthy": sum(1 for a in domain_agents if a.get("status") == "HEALTHY"),
                "at_risk": sum(1 for a in domain_agents if a.get("status") == "WARNING"),
                "critical": sum(1 for a in domain_agents if a.get("status") == "CRITICAL"),
            }
        }

    @staticmethod
    def get_critical_agents_only(db: Session, tenant_id: str) -> Dict[str, Any]:
        """Get only CRITICAL agents (for CEO/Flash escalation)."""

        all_health = MasterAgentDashboard.get_all_agents_health(db, tenant_id)

        critical = [a for a in all_health["agents"] if a.get("status") == "CRITICAL"]

        return {
            "critical_count": len(critical),
            "agents": critical,
            "cascading_failures": all_health["cascading_failures"],
            "flash_action": (
                "🚨 Escalate to CEO - Multiple cascading failures"
                if len(all_health["cascading_failures"]) > 1
                else "⚠️ Investigate and fix - Agent dependency risk"
            )
        }

    @staticmethod
    def get_agent_dependency_graph(db: Session) -> Dict[str, Any]:
        """
        Get the dependency graph showing which agents depend on which.

        This helps identify cascading failures:
        If Thunder fails, 5 downstream agents are affected.
        If Onboarding Agent fails, only 1-2 downstream agents are affected.
        """

        # Simplified dependency map
        dependencies = {
            "Thunder": {
                "depends_on": [],
                "depended_by": ["Recruitment Agent", "Offer Letter Agent", "Interview Reminder Agent"]
            },
            "Recruitment Agent": {
                "depends_on": ["Thunder"],
                "depended_by": ["Interview Reminder Agent", "Supervisor Agent"]
            },
            "Interview Reminder Agent": {
                "depends_on": ["Recruitment Agent", "Thunder"],
                "depended_by": ["Hiring Panel", "Supervisor Agent"]
            },
            "Hiring Panel": {
                "depends_on": ["Interview Reminder Agent"],
                "depended_by": ["Offer Letter Agent", "Offer Acceptance"]
            },
            "Offer Letter Agent": {
                "depends_on": ["Hiring Panel", "Thunder"],
                "depended_by": ["Offer Acceptance"]
            },
            "Offer Acceptance": {
                "depends_on": ["Offer Letter Agent", "Thunder"],
                "depended_by": ["Onboarding Agent", "HR Agent"]
            },
            "Onboarding Agent": {
                "depends_on": ["Offer Acceptance"],
                "depended_by": ["Resource Management Agent", "Buddy Program Agent"]
            },
            "Resource Management Agent": {
                "depends_on": ["Onboarding Agent"],
                "depended_by": ["Core-Pull Conflict Agent", "HTD Pipeline Agent"]
            }
        }

        return {
            "dependencies": dependencies,
            "critical_path": [
                "Thunder → Recruitment → Interview → Panel → Offer → Acceptance → Onboarding → Resource Mgmt"
            ],
            "note": "If any agent in critical path fails, entire hiring pipeline stalls"
        }
