"""
Agent Maturity Dashboard API
=============================
Prefix: /admin/agents
Tag: admin-agents

Endpoints for viewing and managing agent performance/maturity metrics.
Only accessible to admin users.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models.agent_maturity import AgentMaturityLevel, AgentPerformanceMetric
from app.schemas.agent_maturity import (
    AgentMaturityLevelResponse,
    AgentMaturityDashboardResponse,
    AllAgentsMaturitiesResponse,
    AgentPerformanceMetricResponse,
    RetireAgentRequest,
    RetireAgentResponse
)
from app.services.agent_maturity_service import (
    check_agent_health,
    retire_agent as retire_agent_service
)

router = APIRouter(prefix="/admin/agents", tags=["admin-agents"])


@router.get(
    "/maturity",
    response_model=AllAgentsMaturitiesResponse,
    dependencies=[Depends(require_permission("admin.view"))]
)
def get_all_agents_maturity(
    db: Session = Depends(get_db),
):
    """
    Get current maturity levels for all agents.

    Returns:
        List of agents with their current maturity, success rates, trends
    """
    maturity_levels = db.query(AgentMaturityLevel).filter(
        AgentMaturityLevel.is_active == True,
        AgentMaturityLevel.is_retired == False
    ).all()

    if not maturity_levels:
        return AllAgentsMaturitiesResponse(
            agents=[],
            last_calculated=datetime.utcnow(),
            next_calculation=datetime.utcnow() + timedelta(days=7)
        )

    return AllAgentsMaturitiesResponse(
        agents=[AgentMaturityLevelResponse.from_orm(m) for m in maturity_levels],
        last_calculated=max([m.last_calculated_at for m in maturity_levels if m.last_calculated_at]),
        next_calculation=datetime.utcnow() + timedelta(days=7)
    )


@router.get(
    "/maturity/{agent_name}",
    response_model=AgentMaturityDashboardResponse,
    dependencies=[Depends(require_permission("admin.view"))]
)
def get_agent_maturity_dashboard(
    agent_name: str,
    db: Session = Depends(get_db),
):
    """
    Get complete dashboard for a specific agent including trends and history.

    Args:
        agent_name: Name of the agent (e.g., "Recruitment", "Resource Manager")

    Returns:
        Current maturity + last 12 weeks of metrics
    """
    # Get current maturity
    current_maturity = db.query(AgentMaturityLevel).filter(
        AgentMaturityLevel.agent_name == agent_name,
        AgentMaturityLevel.is_active == True
    ).first()

    if not current_maturity:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    # Get recent metrics (last 12 weeks)
    recent_metrics = db.query(AgentPerformanceMetric).filter(
        AgentPerformanceMetric.agent_name == agent_name
    ).order_by(
        AgentPerformanceMetric.week_starting.desc()
    ).limit(12).all()

    # Calculate additional stats
    weeks_improving = 0
    if len(recent_metrics) > 1:
        for i in range(len(recent_metrics) - 1):
            if recent_metrics[i].maturity_level > recent_metrics[i+1].maturity_level:
                weeks_improving += 1
            else:
                break

    # Determine status
    if current_maturity.is_retired:
        status = "retired"
    elif current_maturity.maturity_level < 50:
        status = "struggling"
    elif current_maturity.trend_direction == "declining":
        status = "at_risk"
    else:
        status = "active"

    # Calculate improvement rate
    improvement_rate = current_maturity.improvement_percentage or 0

    return AgentMaturityDashboardResponse(
        agent_name=agent_name,
        current_maturity=AgentMaturityLevelResponse.from_orm(current_maturity),
        recent_metrics=[AgentPerformanceMetricResponse.from_orm(m) for m in reversed(recent_metrics)],
        trend=current_maturity.trend_direction or "stable",
        improvement_rate=improvement_rate,
        weeks_improving=weeks_improving,
        status=status
    )


@router.get(
    "/{agent_name}/health",
    dependencies=[Depends(require_permission("admin.view"))]
)
def check_agent_health_status(
    agent_name: str,
    db: Session = Depends(get_db),
):
    """
    Check health status of an agent.

    Returns:
        Health status and recommendations for retirement if declining
    """
    health = check_agent_health(db, agent_name)
    return health


@router.post(
    "/{agent_name}/retire",
    response_model=RetireAgentResponse,
    dependencies=[Depends(require_permission("admin.write"))]
)
def retire_agent(
    agent_name: str,
    request: RetireAgentRequest,
    db: Session = Depends(get_db),
):
    """
    Retire an underperforming agent.

    Args:
        agent_name: Agent to retire
        request: Retirement reason

    Returns:
        Confirmation of retirement
    """
    result = retire_agent_service(db, agent_name, request.reason)
    return RetireAgentResponse(**result)


@router.get(
    "/retired",
    dependencies=[Depends(require_permission("admin.view"))]
)
def get_retired_agents(db: Session = Depends(get_db)):
    """
    Get list of all retired agents and retirement reasons.
    """
    retired = db.query(AgentMaturityLevel).filter(
        AgentMaturityLevel.is_retired == True
    ).all()

    return {
        "retired_agents": [
            {
                "agent_name": agent.agent_name,
                "retirement_reason": agent.retirement_reason,
                "retired_at": agent.last_updated,
                "final_maturity": agent.maturity_level
            }
            for agent in retired
        ],
        "total_retired": len(retired)
    }
