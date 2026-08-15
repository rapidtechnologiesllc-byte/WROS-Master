"""
S-213/HRMS-0115 -- System Configuration & Admin Settings Panel.
==================================================================
Prefix: /system-config
Tag:    system-config

GET  /system-config/settings         -- unified read for the Admin
                                         Settings screen (AI Thresholds/
                                         SLA/Channels/Locale), optionally
                                         BU-scoped via X-Active-BU-Id
                                         (BR-0115-03 resolution)
PUT  /system-config/settings/{key}   -- Admin-only write (BR-0115-01),
                                         audit logged (BR-0115-02)
PUT  /system-config/locale           -- Admin-only write to the real
                                         Tenant locale columns
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_admin_role
from app.core.visibility import should_bypass_bu_filter, get_user_bu_id
from app.api.v1.endpoints.bu_context import get_active_business_unit_id
from app.models.user import Users
from app.schemas.system_config import SettingsPanelResponse, UpdateConfigValueRequest, UpdateLocaleRequest
from app.services.system_config_service import (
    InvalidConfigValue, UnknownConfigKey, get_settings_panel, set_config_value, update_locale_config,
)

router = APIRouter(prefix="/system-config", tags=["system-config"])


def _require_tenant(current_user: Users) -> int:
    if current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="User is not assigned to a tenant")
    return current_user.tenant_id


@router.get("/settings", response_model=SettingsPanelResponse)
def get_settings(
    current_user: Users = Depends(get_current_internal_user),
    business_unit_id: Optional[int] = Depends(get_active_business_unit_id),
    db: Session = Depends(get_db),
):
    tenant_id = _require_tenant(current_user)
    panel = get_settings_panel(db, tenant_id=tenant_id, business_unit_id=business_unit_id)
    return SettingsPanelResponse(**panel)


@router.put("/settings/{config_key}")
def update_setting(
    config_key: str,
    body: UpdateConfigValueRequest,
    current_user: Users = Depends(require_admin_role),
    business_unit_id: Optional[int] = Depends(get_active_business_unit_id),
    db: Session = Depends(get_db),
):
    tenant_id = _require_tenant(current_user)
    try:
        row = set_config_value(
            db, tenant_id=tenant_id, key=config_key, value=body.value,
            updated_by=current_user.UserID, business_unit_id=business_unit_id,
        )
    except UnknownConfigKey as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidConfigValue as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"config_key": config_key, "value": row.config_value, "business_unit_id": row.business_unit_id}


@router.put("/locale")
def update_locale(
    body: UpdateLocaleRequest,
    current_user: Users = Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    tenant_id = _require_tenant(current_user)
    try:
        result = update_locale_config(
            db, tenant_id, body.model_dump(exclude_none=True), updated_by=current_user.UserID,
        )
    except InvalidConfigValue as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result
