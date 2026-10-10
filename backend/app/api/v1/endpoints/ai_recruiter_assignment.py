"""
S-011/HRMS-0411 -- AI Recruiter Assignment Engine
====================================================
Tag: ai-recruiter-assignment

Routes:
  GET   /candidates/{candidate_id}/ai-assignment
      Any internal user -- current active Thunder assignment for a candidate.

  GET   /admin/tenant/ai-config
  PATCH /admin/tenant/ai-config
      Super User only (tenant.ai_config permission) -- Thunder's
      configurable name/persona for the caller's own org. "Tenant" in
      this subsystem is the org-owner Users row (see
      app.services.ai_conversation_service.resolve_thunder_config's
      docstring on this codebase's real tenant_id semantics), so this
      reads/writes the caller's own Users row.

  GET   /admin/tenant/thunder-enabled
  PATCH /admin/tenant/thunder-enabled
      Super User only (tenant.ai_config permission) -- S-075/HRMS-0475
      global Thunder kill switch for the caller's own org, same
      "caller's own Users row is the tenant" semantics as ai-config above.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.schemas.ai_recruiter_assignment import (
    AIAssignmentResponse,
    TenantThunderEnabledResponse,
    TenantThunderEnabledUpdateRequest,
)
from app.services.ai_conversation_service import (
    DEFAULT_THUNDER_DISPLAY_NAME,
    get_active_ai_assignment,
)

router = APIRouter(tags=["ai-recruiter-assignment"])


@router.get(
    "/admin/tenant/thunder-enabled",
    response_model=TenantThunderEnabledResponse,
    summary="Get this org's Thunder global kill switch — Super User only",
    dependencies=[Depends(require_resource_permission("ai-config", "view"))],
    description=(
        "S-075/HRMS-0475 BR-03 -- global pause takes precedence over "
        "every individual conversation's own pause flag. Same "
        "'tenant is the caller's own Users row' semantics as "
        "GET/PATCH /admin/tenant/ai-config above."
    ),
)
async def get_tenant_thunder_enabled(
    current_user: Users = Depends(get_current_internal_user),
):
    return TenantThunderEnabledResponse(thunder_enabled=current_user.thunder_enabled)

@router.patch(
    "/admin/tenant/thunder-enabled",
    response_model=TenantThunderEnabledResponse,
    summary="Set this org's Thunder global kill switch — Super User only",
    dependencies=[Depends(require_resource_permission("ai-config", "view"))],
    description="S-075/HRMS-0475 Step 2 -- disabling this halts every automated Thunder send across the whole org.",
)
def update_tenant_thunder_enabled(
    body: TenantThunderEnabledUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    current_user.thunder_enabled = body.enabled
    db.add(current_user)
    db.commit()
    return TenantThunderEnabledResponse(thunder_enabled=current_user.thunder_enabled)
