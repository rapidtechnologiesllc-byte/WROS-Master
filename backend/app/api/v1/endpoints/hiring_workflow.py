from app.core.logging import logger
"""Interview â†’ Hire â†’ Onboarding workflow API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.database import get_db
from app.models.user import Users
from app.services.hiring_workflow_service import (
    suggest_panelists,
    check_l1_to_l2_auto_trigger,
    check_affordability_for_hire,
    create_l2_interview_panel,
    record_no_show_confirmation
)

import logging

router = APIRouter(prefix="/hiring-workflow", tags=["Hiring Workflow"])


@router.get("/suggestions/{demand_id}/panelists", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def get_panelist_suggestions(
    demand_id: str,
    level: str = "L1",
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get panelist suggestions for a demand based on skill match + interview load."""
    try:
        suggestions = suggest_panelists(db, demand_id, level)
        return {"status": "success", "data": suggestions}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/interviews/{interview_id}/l1-to-l2-trigger", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def check_l1_l2_trigger(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Check if L1 interview results allow L2 auto-creation."""
    try:
        result = check_l1_to_l2_auto_trigger(db, interview_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"status": "success", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/submissions/{submission_id}/affordability", dependencies=[Depends(require_resource_permission("revenue", "view"))])
def check_affordability(
    submission_id: str,
    bu_id: int = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Check BU affordability for hiring a candidate."""
    try:
        result = check_affordability_for_hire(db, submission_id, bu_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"status": "success", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interviews/{demand_id}/create-l2-panel", dependencies=[Depends(require_resource_permission("candidates", "edit"))])
def create_l2_panel(
    demand_id: str,
    submission_id: str,
    panelists: list,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Create L2 interview panel after L1 approval and affordability check."""
    try:
        result = create_l2_interview_panel(db, demand_id, submission_id, panelists)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return {"status": "success", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interviews/{interview_id}/no-show", dependencies=[Depends(require_resource_permission("candidates", "edit"))])
def record_no_show(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Record no-show and drop from panelist's round-robin load."""
    try:
        result = record_no_show_confirmation(db, interview_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"status": "success", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
