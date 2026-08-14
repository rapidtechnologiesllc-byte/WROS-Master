"""
S-071/HRMS-0471 -- AI Recruiter Performance Analytics
==================================================================
Prefix: /analytics
Tag:    thunder-analytics

GET /analytics/thunder?date_from={ISO}&date_to={ISO}
    Auth: candidate.view -- same read-only recruiter/admin visibility
    gate as S-059/S-060/S-063's dashboards. Defaults to the last 30 days.

Role-based scoping:
    - Super User/Admin: All candidates, all business units
    - Partner/BU Head: Only their assigned business unit(s)
    - Recruiter/Recruitment Lead: Candidates they're assigned to
    - Workforce Ops: Their assigned business unit(s)
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin
from app.schemas.thunder_analytics import ThunderAnalyticsResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.thunder_analytics_service import get_thunder_analytics
from app.models.user import Users

router = APIRouter(prefix="/analytics", tags=["thunder-analytics"])


@router.get("/thunder", response_model=ThunderAnalyticsResponse)
def thunder_analytics(
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    user: Users = Depends(get_current_hr_or_admin),
    db: Session = Depends(get_db),
):
    """
    Thunder Analytics with role-based data scoping.

    Super User/Admin see all data.
    Partners/BU Heads see only their business unit.
    Recruiters see only their assigned candidates.
    """
    tenant_id = resolve_default_tenant_id(db)

    # Determine scope based on user role
    user_role = (user.UserRole or "").lower()
    is_super_user = user_role in ("super user", "admin", "ceo", "cfo")

    # Pass user context to analytics service for role-based scoping
    return get_thunder_analytics(
        db,
        tenant_id,
        date_from=date_from,
        date_to=date_to,
        scoped_user=user if not is_super_user else None  # None means no scoping (super user sees all)
    )
