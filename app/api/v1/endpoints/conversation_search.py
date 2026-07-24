"""
S-015/HRMS-0415 -- Conversation Search
=========================================
Prefix: /conversations
Tag:    conversation-search

GET /conversations/search?q=&channel=&date_from=&date_to=&page=&per_page=
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin
from app.models.user import Users
from app.schemas.conversation_search import SearchResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.conversation_search_service import SearchTermTooShort, search_conversations

router = APIRouter(prefix="/conversations", tags=["conversation-search"])


@router.get("/search", response_model=SearchResponse)
def search_conversations_endpoint(
    q: str,
    channel: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    tenant_id = resolve_default_tenant_id(db)
    if not tenant_id:
        raise HTTPException(status_code=500, detail="No tenant available to search.")

    try:
        result = search_conversations(
            db, tenant_id, q, channel=channel, date_from=date_from, date_to=date_to, page=page, per_page=per_page,
        )
    except SearchTermTooShort as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return SearchResponse(**result)
