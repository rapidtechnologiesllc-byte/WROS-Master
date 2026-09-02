"""
Autonomous Job Management Endpoints
====================================
Endpoints for managing automatic job closure when positions are filled.
import logging
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.services.autonomous_job_closure_service import (
    check_and_close_job_if_filled,
    get_job_closure_status
)
from pydantic import BaseModel
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class JobClosureStatusResponse(BaseModel):
    job_id: str
    job_status: str
    positions_needed: int
    hired_count: int
    remaining_positions: int
    is_closed: bool
    eligible_for_closure: bool
    fill_percentage: int


class JobClosureActionResponse(BaseModel):
    success: bool
    message: str
    job_id: str
    action: Optional[str] = None
    closed_at: Optional[str] = None


router = APIRouter(prefix="/autonomous-jobs", tags=["autonomous-jobs"])


@router.get(
    "/status/{job_id}",
    response_model=JobClosureStatusResponse,
    dependencies=[Depends(get_current_internal_user)],
)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """
    Get the closure status of a job.
    Shows positions needed, hired count, and whether it's eligible for closure.
    """
    status = get_job_closure_status(db, job_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


@router.post(
    "/close/{job_id}",
    response_model=JobClosureActionResponse,
    dependencies=[Depends(get_current_internal_user)],
)
def close_job_manually(job_id: str, db: Session = Depends(get_db)):
    """
    Manually trigger job closure check.
    Closes the job if all positions are filled and notifies remaining candidates.
    """
    result = check_and_close_job_if_filled(db, job_id)

    if result:
        return JobClosureActionResponse(
            success=True,
            message=f"Job closed successfully. {result['hired']} positions filled.",
            job_id=job_id,
            action=result["action"],
            closed_at=result["closed_at"]
        )
    else:
        # Get current status to provide context
        status = get_job_closure_status(db, job_id)
        if "error" in status:
            raise HTTPException(status_code=404, detail=status["error"])

        if status["is_closed"]:
            return JobClosureActionResponse(
                success=False,
                message="Job is already closed.",
                job_id=job_id
            )
        else:
            return JobClosureActionResponse(
                success=False,
                message=f"Job not eligible for closure. {status['hired_count']} of {status['positions_needed']} positions filled.",
                job_id=job_id
            )
