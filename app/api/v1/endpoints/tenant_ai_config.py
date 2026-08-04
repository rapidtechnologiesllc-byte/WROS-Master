"""
S-077/HRMS-0477 -- Tenant AI Configuration -- API Endpoints
=============================================================
Prefix: /admin/ai-config
Tag:    tenant-ai-config

Routes:
  GET   /admin/ai-config       Unified read -- merges the real Users-
                                backed fields (ai_agent_name/persona,
                                digest_enabled, thunder_enabled) with
                                the new TenantAIConfig row into one view.
  PATCH /admin/ai-config       Partial update, any subset of fields.
                                ai_agent_persona requires ba_approved=true
                                (BR-01) or the request is rejected.

Auth: tenant.ai_config permission (Super User by default) -- same gate
this story's own dependency note ties this to (HRMS-0411's existing
/admin/tenant/ai-config, HRMS-0475's /admin/tenant/thunder-enabled).
"tenant" is the caller's own Users row, same semantics as both of those.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin, require_permission
from app.models.user import Users
from app.schemas.tenant_ai_config import TenantAIConfigResponse, UpdateTenantAIConfigRequest
from app.services.tenant_ai_config_service import (
    InvalidTenantAIConfigField,
    PersonaChangeRequiresApproval,
    get_tenant_ai_config,
    update_tenant_ai_config,
)

router = APIRouter(prefix="/admin/ai-config", tags=["tenant-ai-config"])


@router.get(
    "",
    response_model=TenantAIConfigResponse,
    summary="Get this org's unified Thunder configuration — Super User only",
    dependencies=[Depends(require_permission("tenant.ai_config"))],
)
def get_ai_config(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    return TenantAIConfigResponse(**get_tenant_ai_config(db, current_user.UserID))


@router.patch(
    "",
    response_model=TenantAIConfigResponse,
    summary="Update this org's Thunder configuration — Super User only",
    dependencies=[Depends(require_permission("tenant.ai_config"))],
    description=(
        "BR-01: ai_agent_persona changes require ba_approved=true or a "
        "422 is returned. BR-02: thunder_enabled is read live on every "
        "autonomous send (HRMS-0475) -- disabling takes effect on the "
        "very next send attempt, not after a delay."
    ),
)
def update_ai_config(
    body: UpdateTenantAIConfigRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    updates = body.model_dump(exclude_unset=True, exclude={"ba_approved"})
    if not updates:
        raise HTTPException(status_code=422, detail="No fields provided to update.")
    try:
        result = update_tenant_ai_config(
            db, current_user.UserID, updates,
            updated_by=current_user.UserID, ba_approved=body.ba_approved,
        )
    except PersonaChangeRequiresApproval as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except InvalidTenantAIConfigField as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return TenantAIConfigResponse(**result)
