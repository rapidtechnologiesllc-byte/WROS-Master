"""
import logging
Agent Config API Endpoints - Manage agent configurations and pipeline order.

Endpoints:
- GET /admin/agents/config - List all agents
- POST /admin/agents/config - Create agent (auto-syncs permissions)
- PUT /admin/agents/config/{agent_id} - Update agent (auto-syncs permissions)
- DELETE /admin/agents/config/{agent_id} - Delete agent
- GET /admin/agents/config/pipeline/order - Get pipeline execution order
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.dependencies import get_db, get_current_user, require_resource_permission
from app.services.agent_config_service import AgentConfigService
from app.core.logging import logger
from fastapi import Request

router = APIRouter(prefix="/admin/agents/config", tags=["agent-config"])


# === Pydantic Models ===
logger = logging.getLogger(__name__)

class AgentConfigRequest(BaseModel):
    """Request schema for creating/updating agent configs."""
    name: str
    display_name: str
    description: Optional[str] = None
    queue_name: str
    next_queue_name: Optional[str] = None
    order: Optional[int] = None
    enabled: Optional[bool] = True

    class Config:
        schema_extra = {
            "example": {
                "name": "thunder",
                "display_name": "AI Recruiter",
                "description": "Initial candidate screening and engagement",
                "queue_name": "input_queue",
                "next_queue_name": "recruitment_screener_queue",
                "order": 1,
                "enabled": True
            }
        }


class AgentConfigResponse(BaseModel):
    """Response schema for agent configs."""
    id: str
    name: str
    display_name: str
    description: Optional[str]
    queue_name: str
    next_queue_name: Optional[str]
    enabled: bool
    order: int

    class Config:
        from_attributes = True


# === Endpoints ===

@router.get(
    "",
    dependencies=[Depends(require_resource_permission("agents", "view"))],
    response_model=list[AgentConfigResponse]
)
async def list_agents(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all agents configured in the system, ordered by pipeline sequence.

    Returns:
    - List of agent configs with pipeline order
    - Only returns enabled agents
    - Ordered by execution sequence (order field)
    """
    try:
        agents = AgentConfigService.get_all_agents(db, current_user.tenant_id)
        return agents
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error listing agents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post(
    "",
    dependencies=[Depends(require_resource_permission("agents", "manage"))],
    response_model=AgentConfigResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_agent(
    request: AgentConfigRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new agent configuration.

    When created:
    1. Agent is added to the pipeline
    2. Permissions are auto-synced for SuperUser roles
    3. Agent is enabled by default

    Request body:
    - name: Unique identifier (e.g., "thunder", "interview_scheduler")
    - display_name: User-friendly name (e.g., "AI Recruiter")
    - queue_name: Input queue for this agent
    - next_queue_name: Output queue routed to next agent
    - order: Position in pipeline (auto-calculated if not provided)
    """
    try:
        agent = AgentConfigService.create_agent(
            db=db,
            name=request.name,
            display_name=request.display_name,
            queue_name=request.queue_name,
            next_queue_name=request.next_queue_name,
            tenant_id=current_user.tenant_id,
            description=request.description,
            order=request.order
        )
        return agent
    except ValueError as e:
        logger.warning(f"Validation error creating agent: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error creating agent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.put(
    "/{agent_id}",
    dependencies=[Depends(require_resource_permission("agents", "manage"))],
    response_model=AgentConfigResponse
)
async def update_agent(
    agent_id: str,
    request: AgentConfigRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update an existing agent configuration.

    When updated:
    1. Agent configuration is changed
    2. Permissions are auto-synced (if resource changed)
    3. Pipeline order is updated if specified

    Path:
    - agent_id: UUID of the agent to update

    Request body:
    - Same fields as create endpoint (all are updatable)
    """
    try:
        agent = AgentConfigService.update_agent(
            db=db,
            agent_id=agent_id,
            name=request.name,
            display_name=request.display_name,
            description=request.description,
            queue_name=request.queue_name,
            next_queue_name=request.next_queue_name,
            order=request.order,
            enabled=request.enabled
        )
        return agent
    except ValueError as e:
        logger.warning(f"Validation error updating agent: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error updating agent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.delete(
    "/{agent_id}",
    dependencies=[Depends(require_resource_permission("agents", "manage"))],
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete an agent configuration.

    Removes the agent from the pipeline. Existing candidate records
    remain unchanged (historical audit trail preserved).

    Path:
    - agent_id: UUID of the agent to delete
    """
    try:
        AgentConfigService.delete_agent(db, agent_id)
        return None
    except ValueError as e:
        logger.warning(f"Validation error deleting agent: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error deleting agent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get(
    "/pipeline/order",
    dependencies=[Depends(require_resource_permission("agents", "view"))],
    response_model=list[dict]
)
async def get_pipeline_order(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get the pipeline execution order.

    Returns agents in the order they execute in the pipeline.
    Shows which agent outputs feed into which agent inputs.

    Returns:
    - List of agents ordered by execution sequence
    - Includes queue names for flow tracing
    - Only enabled agents included
    """
    try:
        pipeline = AgentConfigService.get_pipeline_order(db, current_user.tenant_id)
        return pipeline
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error fetching pipeline order: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
