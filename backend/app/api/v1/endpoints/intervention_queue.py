"""
S-062/HRMS-0462 -- Recruiter Intervention Queue
==================================================================
Prefix: /intervention-queue
Tag:    intervention-queue

GET /intervention-queue?status={optional}         -- Step 3's queue table
GET /intervention-queue/summary                    -- Step 3's dashboard widget
POST /intervention-queue/{id}/take-over             -- Step 3's "Take Over" button
POST /intervention-queue/{id}/resolve                -- Step 4's "Mark Resolved" button

Auth: candidate.edit for the two mutating actions (matches S-010's own
real take-over endpoint's gate exactly, since this reuses that same
ownership-transfer call); candidate.view for the two read-only ones.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.schemas.intervention_queue import QueueResponse, QueueSummaryResponse, ResolveRequest, ResolveResponse, TakeOverResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.intervention_queue_service import QueueItemNotFound, get_queue, get_queue_summary, mark_resolved, take_over_queue_item

router = APIRouter(prefix="/intervention-queue", tags=["intervention-queue"])


@router.get("", response_model=QueueResponse, dependencies=[Depends(require_resource_permission("candidates", "view"))])
def list_queue(status: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id(db)
    return QueueResponse(items=get_queue(db, tenant_id, status=status))


@router.get("/summary", response_model=QueueSummaryResponse, dependencies=[Depends(require_resource_permission("candidates", "view"))])
def queue_summary(db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id(db)
    return get_queue_summary(db, tenant_id)


@router.post("/{queue_item_id}/take-over", response_model=TakeOverResponse, dependencies=[Depends(require_resource_permission("candidates", "edit"))])
def take_over(queue_item_id: int, db: Session = Depends(get_db), current_user: Users = Depends(get_current_internal_user)):
    tenant_id = resolve_default_tenant_id(db)
    try:
        return take_over_queue_item(db, queue_item_id, tenant_id, current_user.UserID)
    except QueueItemNotFound:
        raise HTTPException(status_code=404, detail=f"Queue item {queue_item_id} not found.")


@router.post("/{queue_item_id}/resolve", response_model=ResolveResponse, dependencies=[Depends(require_resource_permission("candidates", "edit"))])
def resolve(queue_item_id: int, payload: ResolveRequest, db: Session = Depends(get_db), current_user: Users = Depends(get_current_internal_user)):
    tenant_id = resolve_default_tenant_id(db)
    try:
        return mark_resolved(db, queue_item_id, tenant_id, current_user.UserID, payload.resolution_note)
    except QueueItemNotFound:
        raise HTTPException(status_code=404, detail=f"Queue item {queue_item_id} not found.")
