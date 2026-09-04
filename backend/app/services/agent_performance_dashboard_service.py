import logging
from app.core.logging import logger
"""Agent Performance Dashboard - Individual agent metrics vs targets."""

from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import List, Dict, Any
from app.services.agent_registry_service import AGENT_REGISTRY
from app.services import agent_state_service
from app.models.agent_state_target import AgentActualPerformance

logger = logging.getLogger(__name__)

class AgentPerformanceDashboard:
    """Dashboard showing all 50+ agents with targets vs achievements."""

    @staticmethod
    def get_all_agents_performance(db: Session) -> Dict[str, Any]:
        """
        Get performance for ALL 50+ agents.
        Shows: Target, Achieved, Progress%, Fear Score, Status
        """

        agents_data = []

        for agent_name, agent_config in AGENT_REGISTRY.items():
            agent_data = AgentPerformanceDashboard._get_agent_performance(
                db, agent_name, agent_config
            )
            agents_data.append(agent_data)

        # Sort by strategic importance then by fear score (descending)
        importance_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        agents_data.sort(
            key=lambda x: (
                importance_order.get(x.get("strategic_importance", "LOW"), 4),
                -x.get("fear_score", 50),
            )
        )

        # Calculate summary statistics
        total_agents = len(agents_data)
        critical_agents = sum(1 for a in agents_data if a.get("strategic_importance") == "CRITICAL")
        at_risk_agents = sum(1 for a in agents_data if a.get("fear_score", 0) > 70)
        healthy_agents = sum(1 for a in agents_data if a.get("fear_score", 0) <= 50)

        return {
            "status": "retrieved",
            "total_agents": total_agents,
            "critical_agents": critical_agents,
            "at_risk_agents": at_risk_agents,
            "healthy_agents": healthy_agents,
            "agents": agents_data,
        }

    @staticmethod
    def _get_agent_performance(
        db: Session, agent_name: str, agent_config: Dict
    ) -> Dict[str, Any]:
        """Get individual agent performance data."""

        try:
            # Get agent config
            agent_cfg = AGENT_REGISTRY.get(agent_name, {})

            # Get latest actual performance
            performance = (
                db.query(AgentActualPerformance)
                .filter(AgentActualPerformance.agent_name == agent_name)
                .order_by(desc(AgentActualPerformance.recorded_at))
                .first()
            )

            # Extract targets
            fy_target = agent_cfg.get("fy_target", {})
            y2030_target = agent_cfg.get("y2030_target", {})

            fy_target_value = fy_target.get("value", 0)
            fy_target_unit = fy_target.get("unit", "")
            y2030_target_value = y2030_target.get("value", 0)
            y2030_target_unit = y2030_target.get("unit", "")

            # Get actual performance
            actual_fy = performance.actual_value if performance else 0
            success_rate = performance.success_rate if performance else 0.0
            quality_score = performance.quality_score if performance else 0.0
            executions = performance.executions if performance else 0

            # Calculate progress
            fy_progress = (actual_fy / fy_target_value * 100) if fy_target_value > 0 else 0
            y2030_progress = (actual_fy / y2030_target_value * 100) if y2030_target_value > 0 else 0

            # Calculate FY gap
            fy_gap = max(0, fy_target_value - actual_fy)
            fy_gap_percent = (fy_gap / fy_target_value * 100) if fy_target_value > 0 else 0

            # Get fear score
            fear_state = agent_state_service.get_agent_state_target(db, agent_name)
            if fear_state:
                fear_score = fear_state.get("fear_score", 50)
                threat_level = fear_state.get("threat_level", "NONE")
            else:
                # Calculate from scratch if not in database
                fy_gap = max(0, fy_target_value - actual_fy)
                fy_gap_percent = (fy_gap / fy_target_value * 100) if fy_target_value > 0 else 0
                fear_score = 20 + (fy_gap_percent * 0.8)  # Fear = 20 + gap% * 0.8
                threat_level = "NONE"

            # Determine status
            if fear_score >= 80:
                status = "TERRIFIED"
            elif fear_score >= 60:
                status = "DESPERATE"
            elif fear_score >= 40:
                status = "CONCERNED"
            elif fear_score >= 20:
                status = "NEUTRAL"
            else:
                status = "MOTIVATED"

            # Acceleration needed
            acceleration_multiplier = (fy_target_value / actual_fy) if actual_fy > 0 else 999

            return {
                "agent_name": agent_name,
                "domain": agent_cfg.get("domain", "unknown"),
                "tier": agent_cfg.get("tier", "unknown"),
                "strategic_importance": agent_cfg.get("strategic_importance", "LOW"),
                "authority_level": agent_cfg.get("authority", 0),
                # Targets
                "fy_target": fy_target_value,
                "fy_target_unit": fy_target_unit,
                "y2030_target": y2030_target_value,
                "y2030_target_unit": y2030_target_unit,
                # Achievement
                "fy_achieved": actual_fy,
                "fy_progress_pct": round(fy_progress, 1),
                "y2030_progress_pct": round(y2030_progress, 1),
                # Gap
                "fy_gap": fy_gap,
                "fy_gap_pct": round(fy_gap_percent, 1),
                # Performance metrics
                "success_rate": round(success_rate, 1),
                "quality_score": round(quality_score, 1),
                "executions": executions,
                # Fear & Status
                "fear_score": round(fear_score, 1),
                "threat_level": threat_level,
                "status": status,
                "acceleration_multiplier": round(acceleration_multiplier, 1),
                # Last updated
                "last_updated": performance.recorded_at.isoformat() if performance else None,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            agent_cfg = AGENT_REGISTRY.get(agent_name, {})
            return {
                "agent_name": agent_name,
                "domain": agent_cfg.get("domain", "unknown"),
                "tier": agent_cfg.get("tier", "unknown"),
                "strategic_importance": agent_cfg.get("strategic_importance", "LOW"),
                "fy_target": agent_cfg.get("fy_target", {}).get("value", 0),
                "fy_achieved": 0,
                "fy_progress_pct": 0.0,
                "fy_gap_pct": 100.0,
                "fear_score": 50.0,
                "status": "ERROR",
                "acceleration_multiplier": 999.0,
                "error": str(e),
            }

    @staticmethod
    def get_agents_by_tier(db: Session, tier: str) -> List[Dict[str, Any]]:
        """Get agents by tier (tier_1_core, tier_2_resource, etc.)."""

        all_agents = AgentPerformanceDashboard.get_all_agents_performance(db)
        filtered = [a for a in all_agents["agents"] if a.get("tier") == tier]
        return filtered

    @staticmethod
    def get_agents_by_domain(db: Session, domain: str) -> List[Dict[str, Any]]:
        """Get agents by domain (recruitment, resource_management, finance, etc.)."""

        all_agents = AgentPerformanceDashboard.get_all_agents_performance(db)
        filtered = [a for a in all_agents["agents"] if a.get("domain") == domain]
        return filtered

    @staticmethod
    def get_at_risk_agents(db: Session) -> List[Dict[str, Any]]:
        """Get agents with fear_score > 70 (DESPERATE or TERRIFIED)."""

        all_agents = AgentPerformanceDashboard.get_all_agents_performance(db)
        at_risk = [a for a in all_agents["agents"] if a.get("fear_score", 0) > 70]
        return sorted(at_risk, key=lambda x: x["fear_score"], reverse=True)

    @staticmethod
    def get_healthy_agents(db: Session) -> List[Dict[str, Any]]:
        """Get agents with fear_score <= 50 (MOTIVATED or NEUTRAL)."""

        all_agents = AgentPerformanceDashboard.get_all_agents_performance(db)
        healthy = [a for a in all_agents["agents"] if a.get("fear_score", 0) <= 50]
        return sorted(healthy, key=lambda x: x["fy_progress_pct"], reverse=True)

    @staticmethod
    def get_critical_agents(db: Session) -> List[Dict[str, Any]]:
        """Get CRITICAL importance agents only."""

        all_agents = AgentPerformanceDashboard.get_all_agents_performance(db)
        critical = [a for a in all_agents["agents"] if a.get("strategic_importance") == "CRITICAL"]
        return critical

    @staticmethod
    def get_progress_summary(db: Session) -> Dict[str, Any]:
        """Get summary progress toward $100M revenue and 2000 headcount."""

        all_agents = AgentPerformanceDashboard.get_all_agents_performance(db)

        # Track revenue-contributing agents
        revenue_agents = [
            a for a in all_agents["agents"]
            if "revenue" in a.get("domain", "").lower()
        ]
        revenue_achieved = sum(a.get("fy_achieved", 0) for a in revenue_agents if "$" not in str(a.get("fy_target_unit", "")))
        revenue_target = sum(a.get("fy_target", 0) for a in revenue_agents)

        # Track headcount-contributing agents
        headcount_agents = [
            a for a in all_agents["agents"]
            if "recruitment" in a.get("domain", "").lower() or "resource" in a.get("domain", "").lower()
        ]
        headcount_achieved = sum(a.get("fy_achieved", 0) for a in headcount_agents)
        headcount_target = 2000  # Global target

        return {
            "revenue": {
                "target": 100_000_000,  # $100M in cents
                "target_display": "$100M",
                "achieved": revenue_achieved,
                "progress_pct": (revenue_achieved / 100_000_000 * 100) if revenue_achieved > 0 else 0,
            },
            "headcount": {
                "target": headcount_target,
                "achieved": headcount_achieved,
                "progress_pct": (headcount_achieved / headcount_target * 100) if headcount_target > 0 else 0,
            },
            "total_agents": len(all_agents["agents"]),
            "critical_agents": all_agents["critical_agents"],
            "at_risk_agents": all_agents["at_risk_agents"],
            "healthy_agents": all_agents["healthy_agents"],
        }

    @staticmethod
    def get_dashboard_html_table(db: Session) -> str:
        """
        Generate HTML table of all agents for dashboard display.
        Shows: Agent Name, Domain, Target, Achieved, Progress, Fear, Status
        """

        all_agents = AgentPerformanceDashboard.get_all_agents_performance(db)

        html = """
        <table style="width:100%; border-collapse: collapse; font-size: 12px;">
        <thead style="background-color: #f0f0f0; border-bottom: 2px solid #333;">
            <tr>
                <th style="padding: 8px; text-align: left; border-right: 1px solid #ddd;">Agent Name</th>
                <th style="padding: 8px; text-align: left; border-right: 1px solid #ddd;">Domain</th>
                <th style="padding: 8px; text-align: center; border-right: 1px solid #ddd;">FY Target</th>
                <th style="padding: 8px; text-align: center; border-right: 1px solid #ddd;">Achieved</th>
                <th style="padding: 8px; text-align: center; border-right: 1px solid #ddd;">Progress</th>
                <th style="padding: 8px; text-align: center; border-right: 1px solid #ddd;">Fear</th>
                <th style="padding: 8px; text-align: center; border-right: 1px solid #ddd;">Status</th>
                <th style="padding: 8px; text-align: center;">Acceleration</th>
            </tr>
        </thead>
        <tbody>
        """

        for agent in all_agents["agents"]:
            # Color code by fear level
            if agent.get("fear_score", 0) >= 80:
                row_color = "#ffcccc"  # Red (terrified)
            elif agent.get("fear_score", 0) >= 60:
                row_color = "#ffe6cc"  # Orange (desperate)
            elif agent.get("fear_score", 0) >= 40:
                row_color = "#ffffcc"  # Yellow (concerned)
            else:
                row_color = "#ccffcc"  # Green (motivated/neutral)

            html += f"""
            <tr style="background-color: {row_color}; border-bottom: 1px solid #ddd;">
                <td style="padding: 8px; border-right: 1px solid #ddd;"><strong>{agent.get("agent_name", "N/A")}</strong></td>
                <td style="padding: 8px; border-right: 1px solid #ddd;">{agent.get("domain", "N/A")}</td>
                <td style="padding: 8px; text-align: center; border-right: 1px solid #ddd;">
                    {agent.get("fy_target", 0)} {agent.get("fy_target_unit", "")}
                </td>
                <td style="padding: 8px; text-align: center; border-right: 1px solid #ddd;">
                    <strong>{agent.get("fy_achieved", 0)}</strong>
                </td>
                <td style="padding: 8px; text-align: center; border-right: 1px solid #ddd;">
                    {agent.get("fy_progress_pct", 0):.1f}%
                </td>
                <td style="padding: 8px; text-align: center; border-right: 1px solid #ddd;">
                    {agent.get("fear_score", 0):.0f}/100
                </td>
                <td style="padding: 8px; text-align: center; border-right: 1px solid #ddd;">
                    <span style="padding: 4px 8px; border-radius: 4px; background-color: #fff; font-weight: bold;">
                        {agent.get("status", "N/A")}
                    </span>
                </td>
                <td style="padding: 8px; text-align: center;">
                    {agent.get("acceleration_multiplier", 0):.1f}x
                </td>
            </tr>
            """

        html += "</tbody></table>"
        return html
