"""Flash Interview Analysis endpoints — AI-powered interview assessment."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_permission
from app.core.database import get_db
from app.models.user import Users
from app.services.flash_interview_analysis_service import (
    analyze_interview_transcript,
    compare_panel_vs_flash
)

router = APIRouter(prefix="/flash/interviews", tags=["Flash Interview Analysis"])


@router.get("/{interview_id}/analysis", dependencies=[Depends(require_permission("candidate.view"))])
def get_flash_interview_analysis(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Get Flash's AI-powered analysis of an interview transcript.

    Flash analyzes the interview for:
    - Technical competency
    - Communication skills
    - Problem-solving approach
    - Cultural alignment with BlitzenX values

    Returns hire/no-hire recommendation with confidence score and rationale.

    Permissions: candidate.view (Recruiter, HR, BU Head, Finance, CEO)
    """
    try:
        analysis = analyze_interview_transcript(db, interview_id)
        if "error" in analysis:
            raise HTTPException(status_code=404, detail=analysis["error"])
        return {"status": "success", "data": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{interview_id}/comparison", dependencies=[Depends(require_permission("candidate.view"))])
def get_flash_panel_comparison(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Side-by-side comparison: Panel feedback vs Flash analysis.

    Useful for:
    - Identifying where panel and AI agree/disagree
    - Flagging high-confidence divergences
    - Supporting hiring decision with multiple perspectives

    Permissions: candidate.view
    """
    try:
        comparison = compare_panel_vs_flash(db, interview_id)
        if "error" in comparison:
            raise HTTPException(status_code=404, detail=comparison["error"])
        return {"status": "success", "data": comparison}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
