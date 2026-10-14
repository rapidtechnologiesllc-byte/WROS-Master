"""Recruiter Intervention Queue API (S-062) -- the screen's endpoints.

The service (intervention_queue_service) and the queue table existed and
are fed by the Risk dashboard's "Add to Queue", but no endpoints exposed
them, so the Intervention Queue screen always failed to load.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.models.user import Users
from app.services.intervention_queue_service import (
    QueueItemNotFound,
    get_queue,
    get_queue_summary,
    mark_resolved,
    take_over_queue_item,
)
from app.services.ai_conversation_service import resolve_default_tenant_id

router = APIRouter(prefix="/intervention-queue", tags=["intervention-queue"])


class ResolveRequest(BaseModel):
    resolution_note: Optional[str] = None


@router.get("", dependencies=[Depends(require_resource_permission("intervention-queue", "view"))])
def list_queue(status: Optional[str] = None, db: Session = Depends(get_db)):
    return {"items": get_queue(db, resolve_default_tenant_id(db), status=status)}


@router.get("/summary", dependencies=[Depends(require_resource_permission("intervention-queue", "view"))])
def queue_summary(db: Session = Depends(get_db)):
    return get_queue_summary(db, resolve_default_tenant_id(db))


@router.post("/{queue_item_id}/take-over")
def take_over(
    queue_item_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("intervention-queue", "edit")),
):
    try:
        return take_over_queue_item(db, queue_item_id, resolve_default_tenant_id(db), current_user.UserID)
    except QueueItemNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{queue_item_id}/resolve")
def resolve(
    queue_item_id: int,
    body: ResolveRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("intervention-queue", "edit")),
):
    try:
        return mark_resolved(db, queue_item_id, resolve_default_tenant_id(db), current_user.UserID, body.resolution_note)
    except QueueItemNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
