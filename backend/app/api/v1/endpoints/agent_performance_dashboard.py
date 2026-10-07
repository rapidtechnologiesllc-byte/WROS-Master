import logging
"""Agent Performance Dashboard API - All 50+ agents with targets vs achievements."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.services.agent_performance_dashboard_service import AgentPerformanceDashboard

router = APIRouter(prefix="/dashboard/agents", tags=["agent-dashboard"])


@router.get("/healthy", dependencies=[Depends(require_resource_permission("agents", "view"))])
def get_healthy_agents(
    db: Session = Depends(get_db),
):
    """
    Get agents with fear_score <= 50 (MOTIVATED or NEUTRAL).

    These agents are performing well and on track.

    **Use this for:** Benchmarking, best practices, recognition
    """
    agents = AgentPerformanceDashboard.get_healthy_agents(db)
    return {
        "status": "retrieved",
        "healthy_count": len(agents),
        "agents": agents,
    }

