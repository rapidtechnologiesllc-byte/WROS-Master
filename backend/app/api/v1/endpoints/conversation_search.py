"""
S-015/S-016 (HRMS-0415/0416) -- Conversation Search + Filters
==================================================================
Prefix: /conversations
import logging
Tag:    conversation-search

GET /conversations/search?q=&channel=&date_from=&date_to=&page=&per_page=
    &status=&escalated=&has_missing_fields=&updated_after=&updated_before=

status may repeat (?status=open&status=awaiting_candidate) for OR-within-
type filtering (BR-01). See conversation_search_service's docstring for
why `status`/`escalated` are two separate real fields, not the spec's
single fictional status enum.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.schemas.conversation_search import SearchResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.conversation_search_service import SearchTermTooShort, search_conversations

router = APIRouter(prefix="/conversations", tags=["conversation-search"])

@router.get(
    "/search",
    response_model=SearchResponse,
    dependencies=[Depends(require_resource_permission("search", "view"))]
)
def search_conversations_endpoint(
    q: str,
    channel: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = 1,
    per_page: int = 20,
    status: Optional[List[str]] = Query(None),
    escalated: Optional[bool] = None,
    has_missing_fields: Optional[bool] = None,
    updated_after: Optional[datetime] = None,
    updated_before: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    tenant_id = resolve_default_tenant_id()
    if not tenant_id:
        raise HTTPException(status_code=500, detail="No tenant available to search.")

    try:
        result = search_conversations(
            db, tenant_id, q, channel=channel, date_from=date_from, date_to=date_to, page=page, per_page=per_page,
            status=status, escalated=escalated, has_missing_fields=has_missing_fields,
            updated_after=updated_after, updated_before=updated_before,
        )
    except SearchTermTooShort as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return SearchResponse(**result)
