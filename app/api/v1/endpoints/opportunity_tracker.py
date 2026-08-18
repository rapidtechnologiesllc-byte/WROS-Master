"""Opportunity Tracker Agent endpoints for sales pipeline management."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel

from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.database import get_db
from app.models.user import Users
from app.services.opportunity_tracker_agent_service import OpportunityTrackerAgent

router = APIRouter(prefix="/opportunities", tags=["Opportunity Tracker"])


class LogOpportunityRequest(BaseModel):
    """Log new opportunity when partner/sales person identifies target client."""
    client_name: str
    deal_size_usd_cents: int
    expected_close_date: datetime


class UpdateOpportunityStageRequest(BaseModel):
    """Update opportunity as it progresses through sales cycle."""
    new_stage: str
    activity_note: str


class LogActivityRequest(BaseModel):
    """Log activity (call, email, meeting, etc.) on opportunity."""
    activity: str  # "call", "email", "meeting", "proposal_sent", etc.
    outcome: str   # "positive", "neutral", "negative"
    next_step: str = None


@router.post("/log", dependencies=[Depends(require_resource_permission("opportunities", "create"))])
async def log_new_opportunity(
    req: LogOpportunityRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Partner/sales person identifies target client.

    System logs opportunity and begins tracking to closure.
    Example: "Client X is my next target, $500K deal, close by end of Q3"

    Returns: Opportunity logged with probability-weighted revenue calculated.
    """
    try:
        result = await OpportunityTrackerAgent.log_new_opportunity(
            tenant_id=current_user.tenant_id,
            partner_id=current_user.UserID,
            client_name=req.client_name,
            deal_size_usd_cents=req.deal_size_usd_cents,
            expected_close_date=req.expected_close_date,
            db=db
        )
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipeline-health", dependencies=[Depends(require_resource_permission("opportunities", "view"))])
async def get_pipeline_health(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Daily pipeline health check toward $100M annual revenue target.

    Returns:
    - Total pipeline value (probability-weighted)
    - Pipeline breakdown by stage
    - Stalled opportunities (no activity > threshold)
    - Deals at risk (closing soon but not advanced)
    - Flash action required?

    Used by Opportunity Tracker Agent to validate we're on path.
    Escalations go directly to Flash if needed.
    """
    try:
        health = await OpportunityTrackerAgent.track_pipeline_health(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/opportunities/{opportunity_id}/stage", dependencies=[Depends(require_resource_permission("opportunities", "edit"))])
async def update_opportunity_stage(
    opportunity_id: str,
    req: UpdateOpportunityStageRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Update opportunity as it progresses through sales cycle.

    Valid stage progression:
    prospect â†’ qualified â†’ proposal â†’ negotiation â†’ commitment â†’ closed_won
    (or closed_lost at any stage)

    Example: "Moving opportunity to proposal stage - formal quote submitted"

    Returns: Updated opportunity with new probability-weighted value.
    """
    try:
        result = await OpportunityTrackerAgent.update_opportunity_stage(
            opportunity_id=opportunity_id,
            new_stage=req.new_stage,
            activity_note=req.activity_note,
            db=db
        )
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/opportunities/{opportunity_id}/activity", dependencies=[Depends(require_resource_permission("opportunities", "edit"))])
async def log_opportunity_activity(
    opportunity_id: str,
    req: LogActivityRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Log activity on opportunity (call, email, meeting, proposal_sent, etc.)

    System uses activity log to detect stalls:
    - prospect: alert if no activity > 7 days
    - qualified: alert if no activity > 5 days
    - proposal: alert if no activity > 3 days
    - negotiation: alert if no activity > 2 days
    - commitment: alert if no activity > 1 day

    Stalled deals escalate to Flash for intervention.

    Returns: Activity logged, stall detection updated.
    """
    try:
        result = await OpportunityTrackerAgent.log_opportunity_activity(
            opportunity_id=opportunity_id,
            activity=req.activity,
            outcome=req.outcome,
            next_step=req.next_step,
            db=db
        )
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
