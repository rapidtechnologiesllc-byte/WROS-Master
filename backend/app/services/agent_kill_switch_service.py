import logging
"""Agent Kill Switch Automation - Disable agents that can't hit minimum targets."""

from sqlalchemy.orm import Session
from datetime import datetime
from app.models.agent_state_target import AgentStateTarget, AgentFearScore
from app.utils.agent_logger import log_agent_execution
logger = logging.getLogger(__name__)

class AgentKillSwitchService:
    """Automated kill switch logic for underperforming agents."""

    # Thresholds for automatic kill switch evaluation
    FEAR_THRESHOLD = 85  # Kill switch candidate if fear > 85
    GAP_THRESHOLD = 50   # AND gap > 50%
    MIN_SUCCESS_RATE = 90  # Below this = kill switch eligible

    @staticmethod
    def evaluate_agent(db: Session, agent_name: str) -> dict:
        """
        Evaluate if an agent should be killed (disabled).

        Returns:
        {
            "agent_name": str,
            "should_kill": bool,
            "reason": str,
            "fear_score": float,
            "success_rate": float,
            "gap_pct": float,
            "recommendations": list,
        }
        """

        target = db.query(AgentStateTarget).filter(
            AgentStateTarget.agent_name == agent_name
        ).first()

        if not target:
            return {"agent_name": agent_name, "error": "Agent not found"}

        fear_record = db.query(AgentFearScore).filter(
            AgentFearScore.agent_name == agent_name
        ).order_by(AgentFearScore.date.desc()).first()

        if not fear_record:
            return {
                "agent_name": agent_name,
                "should_kill": False,
                "reason": "No performance data yet",
                "fear_score": 0,
                "success_rate": 0,
                "gap_pct": 0,
                "recommendations": ["Collect baseline data before evaluation"],
            }

        fear = fear_record.fear_score
        success_rate = target.target_2030_value  # Placeholder
        gap_pct = max(
            fear_record.gap_from_fy_target,
            fear_record.gap_from_2030_target
        )

        # Kill switch logic
        should_kill = (fear > AgentKillSwitchService.FEAR_THRESHOLD and
                      gap_pct > AgentKillSwitchService.GAP_THRESHOLD)

        recommendations = []
        if fear > AgentKillSwitchService.FEAR_THRESHOLD:
            recommendations.append(
                f"Fear score {fear:.0f}/100 exceeds threshold. Evaluate kill switch."
            )
        if gap_pct > AgentKillSwitchService.GAP_THRESHOLD:
            recommendations.append(
                f"Gap {gap_pct:.0f}% exceeds {AgentKillSwitchService.GAP_THRESHOLD}%. Not on track."
            )

        reason = None
        if should_kill:
            reason = (
                f"Fear {fear:.0f}/100 + Gap {gap_pct:.0f}% exceeds thresholds. "
                f"Agent cannot hit minimum targets."
            )

        return {
            "agent_name": agent_name,
            "should_kill": should_kill,
            "reason": reason,
            "fear_score": fear,
            "success_rate": success_rate,
            "gap_pct": gap_pct,
            "recommendations": recommendations,
            "kill_switch_eligible": should_kill,
        }

    @staticmethod
    def execute_kill_switch(
        db: Session,
        agent_name: str,
        reason: str,
        executed_by: str
    ) -> dict:
        """
        Execute kill switch: disable agent and log reason.

        Returns:
        {
            "status": "success" or "error",
            "agent_name": str,
            "enabled": False,
            "disabled_at": datetime,
            "reason": str,
            "executed_by": str,
        }
        """

        try:
            target = db.query(AgentStateTarget).filter(
                AgentStateTarget.agent_name == agent_name
            ).first()

            if not target:
                return {
                    "status": "error",
                    "message": f"Agent {agent_name} not found",
                }

            target.enabled = False
            target.status = "DISABLED"
            target.kill_switch_reason = reason
            target.disabled_at = datetime.utcnow()

            db.commit()

            # Log the kill switch event
            log_agent_execution(
                db=db,
                agent_name="AgentKillSwitchService",
                action="KILL_SWITCH_EXECUTED",
                target_agent=agent_name,
                success=True,
                confidence=1.0,
                details=f"Agent disabled. Reason: {reason}",
                executed_by=executed_by,
            )

            return {
                "status": "success",
                "agent_name": agent_name,
                "enabled": False,
                "disabled_at": target.disabled_at.isoformat(),
                "reason": reason,
                "executed_by": executed_by,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            return {
                "status": "error",
                "message": str(e),
            }

    @staticmethod
    def reenable_agent(
        db: Session,
        agent_name: str,
        executed_by: str
    ) -> dict:
        """Re-enable a previously disabled agent."""

        try:
            target = db.query(AgentStateTarget).filter(
                AgentStateTarget.agent_name == agent_name
            ).first()

            if not target:
                return {
                    "status": "error",
                    "message": f"Agent {agent_name} not found",
                }

            target.enabled = True
            target.status = "OPERATIONAL"
            target.kill_switch_reason = None
            target.disabled_at = None

            db.commit()

            # Log the re-enable event
            log_agent_execution(
                db=db,
                agent_name="AgentKillSwitchService",
                action="AGENT_REENABLED",
                target_agent=agent_name,
                success=True,
                confidence=1.0,
                details="Agent re-enabled after kill switch",
                executed_by=executed_by,
            )

            return {
                "status": "success",
                "agent_name": agent_name,
                "enabled": True,
                "executed_by": executed_by,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            return {
                "status": "error",
                "message": str(e),
            }

    @staticmethod
    def evaluate_all_agents(db: Session) -> dict:
        """Evaluate all agents for kill switch eligibility."""

        from app.services.agent_registry_service import get_all_agents

        all_agents = get_all_agents()
        results = {
            "evaluated": len(all_agents),
            "kill_switch_candidates": [],
            "at_risk": [],
            "healthy": [],
        }

        for agent_name in all_agents:
            eval_result = AgentKillSwitchService.evaluate_agent(db, agent_name)

            if "error" in eval_result:
                continue

            if eval_result.get("should_kill"):
                results["kill_switch_candidates"].append({
                    "agent_name": agent_name,
                    "reason": eval_result["reason"],
                    "fear_score": eval_result["fear_score"],
                })
            elif eval_result["fear_score"] > 60:
                results["at_risk"].append({
                    "agent_name": agent_name,
                    "fear_score": eval_result["fear_score"],
                })
            else:
                results["healthy"].append(agent_name)

        return results
