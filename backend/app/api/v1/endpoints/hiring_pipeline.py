"""Hiring pipeline: where each candidate is in the hiring order, and why they are waiting.

GET  /hiring-pipeline                          open pipelines (filter by stage)
GET  /hiring-pipeline/candidate/{id}           stage, blockers and history (created on first read)
POST /hiring-pipeline/candidate/{id}/screen    recruiter screen decision: PASS / SKIP / FAIL
POST /hiring-pipeline/candidate/{id}/evaluate  re-derive the stage now
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.hiring_pipeline import HiringPipeline
from app.services import hiring_pipeline_service as pipelines

router = APIRouter(prefix="/hiring-pipeline", tags=["hiring-pipeline"])


class ScreenDecisionRequest(BaseModel):
    decision: str
    notes: Optional[str] = None


@router.get("", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def list_pipelines(stage: Optional[str] = None, limit: int = 200, db: Session = Depends(get_db),
                   user=Depends(get_current_internal_user)):
    query = db.query(HiringPipeline).filter(HiringPipeline.closed_at.is_(None))
    if user.tenant_id is not None:
        query = query.filter(HiringPipeline.tenant_id == user.tenant_id)
    if stage:
        query = query.filter(HiringPipeline.stage == stage.upper())
    rows = query.order_by(HiringPipeline.stage_entered_at.desc()).limit(min(max(limit, 1), 500)).all()
    return {"total": len(rows), "pipelines": [
        {"candidate_id": p.candidate_id, "stage": p.stage, "stage_entered_at": p.stage_entered_at,
         "blockers": p.blockers or [], "grandfathered": p.grandfathered} for p in rows]}


@router.get("/candidate/{candidate_id}", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def get_candidate_pipeline(candidate_id: str, db: Session = Depends(get_db)):
    try:
        pipeline = pipelines.get_or_create_pipeline(db, candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return pipelines.snapshot(db, pipeline)


@router.post("/candidate/{candidate_id}/screen",
             dependencies=[Depends(require_resource_permission("candidates", "edit"))])
def screen_candidate(candidate_id: str, request: ScreenDecisionRequest, db: Session = Depends(get_db),
                     user=Depends(get_current_internal_user)):
    try:
        pipeline = pipelines.record_screen_decision(db, candidate_id, request.decision.upper(), user.UserID,
                                                    request.notes)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    pipelines.queue_stage_actions(pipeline)
    return pipelines.snapshot(db, pipeline)


@router.post("/candidate/{candidate_id}/evaluate",
             dependencies=[Depends(require_resource_permission("candidates", "edit"))])
def evaluate_candidate(candidate_id: str, db: Session = Depends(get_db), user=Depends(get_current_internal_user)):
    try:
        pipeline = pipelines.evaluate_and_act(db, candidate_id, "manual", actor=user.UserID)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return pipelines.snapshot(db, pipeline)
