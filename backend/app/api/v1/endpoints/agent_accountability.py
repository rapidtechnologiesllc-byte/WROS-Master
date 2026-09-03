"""
import logging
Agent Accountability API - Show who's responsible for hand-offs breaking down.

GET /agents/accountability - See all agents' contributions to "2,000 by 2030"
GET /agents/accountability/hand-offs - See which agent hand-offs are broken
GET /agents/accountability/scorecards - Individual agent performance cards
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user, require_resource_permission
from app.services.agent_accountability_service import AgentAccountabilityService
from app.core.logging import logger
from app.core.database import get_db

router = APIRouter(prefix="/agents", tags=["agent-accountability"])


@router.get("/accountability", dependencies=[Depends(require_resource_permission("agents", "view"))])
async def get_agent_accountability(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get full accountability view showing:
    1. Which agents are responsible for what
    2. Their current performance
    3. Which hand-offs are broken (Flash escalation points)
    4. Individual agent scorecards

    This is the "rod up their ass" view - each agent sees their contribution
    to the singular goal: get 2,000 employees by 2030.
    """
    try:
        scorecards = AgentAccountabilityService.get_agent_scorecards(db, current_user.tenant_id)

        return {
            "status": "success",
            "data": scorecards,
            "north_star": scorecards["north_star"],
            "broken_hand_offs": scorecards["hand_offs"]["broken_count"],
            "escalation_to_flash": (
                "YES - Fix these hand-offs NOW"
                if scorecards["hand_offs"]["broken_count"] >= 2
                else "NO - Monitor these"
                if scorecards["hand_offs"]["broken_count"] == 1
                else "All hand-offs healthy"
            )
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error fetching agent accountability: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accountability/hand-offs", dependencies=[Depends(require_resource_permission("agents", "view"))])
async def get_broken_hand_offs(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get ONLY the broken hand-offs (where one agent isn't passing work to the next).

    Each broken hand-off is a Flash escalation point:
    - If 1 hand-off broken: Investigate and fix
    - If 2+ hand-offs broken: Escalate to CEO

    Format shows:
    - Which hand-off (e.g., "Recruitment Agent → Interview Scheduler")
    - Current conversion rate vs target
    - Who's responsible
    - What needs to be done
    """
    try:
        hand_offs = AgentAccountabilityService.get_pipeline_hand_offs(db, current_user.tenant_id)

        return {
            "status": "success",
            "broken_hand_offs": hand_offs["broken_hand_offs"],
            "total_broken": hand_offs["broken_count"],
            "escalation_required": hand_offs["broken_count"] >= 2,
            "priority": (
                "CRITICAL - Escalate to CEO" if hand_offs["broken_count"] >= 2
                else "HIGH - Flash investigates" if hand_offs["broken_count"] == 1
                else "NONE - All hand-offs healthy"
            ),
            "pipeline": hand_offs["pipeline_summary"]
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error fetching hand-offs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accountability/scorecards", dependencies=[Depends(require_resource_permission("agents", "view"))])
async def get_agent_scorecards(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get individual agent scorecards showing:
    - Agent name
    - Their specific job in the pipeline
    - Their current metrics
    - Their target
    - Their contribution to 2,000 by 2030

    Each agent sees how they connect to the north star.
    No silos - every agent knows they succeed only if the FINAL person joins and stays.
    """
    try:
        scorecards = AgentAccountabilityService.get_agent_scorecards(db, current_user.tenant_id)

        return {
            "status": "success",
            "agents": scorecards["agents"],
            "north_star": scorecards["north_star"]
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error fetching agent scorecards: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
