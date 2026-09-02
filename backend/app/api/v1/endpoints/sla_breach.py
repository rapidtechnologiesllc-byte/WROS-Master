"""
S-020/HRMS-0420 -- Engagement SLA Monitoring
==================================================================
Prefix: /sla
import logging
Tag:    sla-monitoring

GET /sla/breaches?is_resolved=false
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.user import Users
from app.schemas.sla_breach import SLABreachListResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.sla_monitoring_service import get_active_breaches

router = APIRouter(prefix="/sla", tags=["sla-monitoring"])


@router.get("/breaches", response_model=SLABreachListResponse)
def list_sla_breaches(
    is_resolved: bool = False,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    # WHAT NOT TO BUILD (S-020, section 9): in-app only, no resolved-
    # breach history view -- is_resolved=true isn't a real query path
    # this round, matching the spec's own scope cut.
    if is_resolved:
        raise HTTPException(status_code=400, detail="Only is_resolved=false is supported -- resolved-breach history is out of scope for this story.")

    tenant_id = resolve_default_tenant_id(db)
    if not tenant_id:
        raise HTTPException(status_code=500, detail="No tenant available.")

    breaches = get_active_breaches(db, tenant_id)
    return SLABreachListResponse(total_count=len(breaches), breaches=breaches)
