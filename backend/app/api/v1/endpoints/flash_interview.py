from app.core.logging import logger
"""Flash Interview Analysis endpoints â€” AI-powered interview assessment."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.database import get_db
from app.models.user import Users
import logging

router = APIRouter(prefix="/flash/interviews", tags=["Flash Interview Analysis"])

@router.get("/{interview_id}/analysis", response_model=dict, dependencies=[Depends(require_resource_permission("candidates", "view"))])
def get_flash_interview_analysis(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """The recommendation after an interview: Claude's when a key is configured, else worked out by rules from the
    panel's feedback and the transcript (source says which). data is null when nothing is known yet."""
    from app.api.v1.endpoints.interviews import _interview_scope
    from app.models.user import Interview
    from app.services.interview_transcript_service import analysis_for

    interview = db.query(Interview).filter(Interview.id == interview_id, _interview_scope(db, current_user)).first()
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")
    return {"status": "success", "data": analysis_for(db, interview)}
