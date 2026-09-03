import logging
from app.core.logging import logger
"""Agent Kill Switch API - Execute and manage kill switches."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.database import get_db
from app.models.user import Users
from app.services.agent_kill_switch_service import AgentKillSwitchService

router = APIRouter(prefix="/agent-kill-switch", tags=["Agent Kill Switch"])


@router.get("/evaluate/{agent_name}", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
def evaluate_agent_for_kill_switch(
    agent_name: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Evaluate if an agent is eligible for kill switch.

    Shows:
    - Fear score vs threshold (>85)
    - Gap vs threshold (>50%)
    - Success rate vs minimum
    - Recommendation: kill or keep

    Required: admin.view
    """

    try:
        # Permission check is enforced via decorator above (require_resource_permission("admin-settings", "view"))
        result = AgentKillSwitchService.evaluate_agent(db, agent_name)

        return {
            "status": "success",
            "agent_name": agent_name,
            "evaluation": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluate-all", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
def evaluate_all_agents_for_kill_switch(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Evaluate ALL agents for kill switch eligibility.

    Returns:
    - kill_switch_candidates: Agents exceeding thresholds
    - at_risk: Agents with high fear (60-85)
    - healthy: Agents on track

    Required: admin.view
    """

    try:
        # Permission check is enforced via decorator above (require_resource_permission("admin-settings", "view"))
        results = AgentKillSwitchService.evaluate_all_agents(db)

        return {
            "status": "success",
            "timestamp": str(__import__('datetime').datetime.utcnow()),
            "evaluation_summary": {
                "total_evaluated": results["evaluated"],
                "kill_switch_candidates": len(results["kill_switch_candidates"]),
                "at_risk_agents": len(results["at_risk"]),
                "healthy_agents": len(results["healthy"]),
            },
            "kill_switch_candidates": results["kill_switch_candidates"],
            "at_risk_agents": results["at_risk"],
            "healthy_agents": results["healthy"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute/{agent_name}", dependencies=[Depends(require_resource_permission("admin-settings", "edit"))])
def execute_kill_switch(
    agent_name: str,
    reason: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Execute kill switch: DISABLE an agent.

    When disabled:
    - Agent stops executing
    - All execution requests return 403 Forbidden
    - Reason logged to audit trail
    - Can be re-enabled by CEO

    Audit trail:
    - Who executed (current_user.UserEmail)
    - When (timestamp)
    - Why (reason parameter)
    - Agent name

    Required: admin.modify + CEO/Admin role
    """

    try:
        # Permission check is enforced via decorator above (require_resource_permission("admin-settings", "edit"))
        result = AgentKillSwitchService.execute_kill_switch(
            db=db,
            agent_name=agent_name,
            reason=reason,
            executed_by=current_user.UserEmail
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return {
            "status": "success",
            "action": "AGENT_DISABLED",
            "agent_name": agent_name,
            "disabled_at": result["disabled_at"],
            "reason": reason,
            "executed_by": current_user.UserEmail,
            "audit_trail": f"Kill switch executed by {current_user.UserEmail}: {reason}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reenable/{agent_name}", dependencies=[Depends(require_resource_permission("admin-settings", "edit"))])
def reenable_agent(
    agent_name: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Re-enable a disabled agent.

    When re-enabled:
    - Agent status changed from DISABLED to OPERATIONAL
    - Execution requests accepted again
    - Re-enable logged to audit trail

    Only CEO can re-enable (recovery requires executive judgment).

    Required: admin.modify + CEO/Admin role
    """

    try:
        # Permission check is enforced via decorator above (require_resource_permission("admin-settings", "edit"))
        result = AgentKillSwitchService.reenable_agent(
            db=db,
            agent_name=agent_name,
            executed_by=current_user.UserEmail
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return {
            "status": "success",
            "action": "AGENT_REENABLED",
            "agent_name": agent_name,
            "enabled": True,
            "executed_by": current_user.UserEmail,
            "audit_trail": f"Agent re-enabled by {current_user.UserEmail}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
