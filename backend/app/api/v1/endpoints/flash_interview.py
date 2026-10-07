from app.core.logging import logger
"""Flash Interview Analysis endpoints â€” AI-powered interview assessment."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.database import get_db
from app.models.user import Users
import logging
from app.services.flash_transcript_service import FlashTranscriptService

router = APIRouter(prefix="/flash/interviews", tags=["Flash Interview Analysis"])

@router.get("/{interview_id}/analysis", response_model=dict, dependencies=[Depends(require_resource_permission("candidates", "view"))])
def get_flash_interview_analysis(
    interview_id: str,
    use_mock: bool = Query(False, description="Use mock transcript for testing (local only)"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Get Flash's AI-powered analysis of an interview transcript from Office 365.

    Flash reads the actual Teams meeting transcript and provides:
    - Technical competency score (0-100)
    - Communication clarity score (0-100)
    - Problem-solving approach score (0-100)
    - Cultural fit with BlitzenX score (0-100)
    - HIRE | NO_HIRE | MAYBE recommendation
    - Confidence percentage (0-100)
    - Strengths and concerns
    - Next steps recommendation

    Parameters:
    - use_mock: For local testing only. Uses generated mock transcript instead of Office 365.

    Permissions: candidate.view (Recruiter, HR, BU Head, Finance, CEO)
    """
    try:
        # Get Flash decision (reads from Office 365 or uses mock for local testing)
        decision = FlashTranscriptService.get_flash_decision(db, interview_id, use_mock=use_mock)

        if "error" in decision:
            raise HTTPException(status_code=404, detail=decision.get("error"))

        return {
            "status": "success",
            "data": decision
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

