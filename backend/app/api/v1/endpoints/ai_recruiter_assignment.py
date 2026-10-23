"""
S-075/HRMS-0475 -- the organisation's Thunder kill switch.
Tag: ai-recruiter-assignment

  GET   /admin/tenant/thunder-enabled
  PATCH /admin/tenant/thunder-enabled
      Read / set the caller's organisation's switch. Stored in the tenant's AI configuration
      (app.services.tenant_ai_config_service), which every automated Thunder send checks.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.schemas.ai_recruiter_assignment import (
    TenantThunderEnabledResponse,
    TenantThunderEnabledUpdateRequest,
)
from app.core.tenant_context import tenant_id_of

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
def get_tenant_thunder_enabled(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.tenant_ai_config_service import is_thunder_enabled
    return TenantThunderEnabledResponse(thunder_enabled=is_thunder_enabled(db, tenant_id_of(current_user)))

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
    from app.services.tenant_ai_config_service import is_thunder_enabled, update_tenant_ai_config
    tenant_id = tenant_id_of(current_user)
    update_tenant_ai_config(db, {"thunder_enabled": bool(body.enabled)}, changed_by=current_user.UserID,
                            tenant_id=tenant_id)
    return TenantThunderEnabledResponse(thunder_enabled=is_thunder_enabled(db, tenant_id))
