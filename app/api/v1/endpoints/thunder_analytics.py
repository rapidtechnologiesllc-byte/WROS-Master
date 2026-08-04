"""
S-071/HRMS-0471 -- AI Recruiter Performance Analytics
==================================================================
Prefix: /analytics
Tag:    thunder-analytics

GET /analytics/thunder?date_from={ISO}&date_to={ISO}
    Auth: candidate.view -- same read-only recruiter/admin visibility
    gate as S-059/S-060/S-063's dashboards. Defaults to the last 30 days.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.thunder_analytics import ThunderAnalyticsResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.thunder_analytics_service import get_thunder_analytics

router = APIRouter(prefix="/analytics", tags=["thunder-analytics"])


@router.get("/thunder", response_model=ThunderAnalyticsResponse, dependencies=[Depends(require_permission("candidate.view"))])
def thunder_analytics(
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    tenant_id = resolve_default_tenant_id(db)
    return get_thunder_analytics(db, tenant_id, date_from=date_from, date_to=date_to)
