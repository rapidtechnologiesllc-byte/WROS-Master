"""Tenant AI Configuration API (S-077) -- the AI Config screen."""
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.models.user import Users
from app.services.tenant_ai_config_service import get_tenant_ai_config, update_tenant_ai_config

router = APIRouter(prefix="/admin/ai-config", tags=["tenant-ai-config"])


@router.get("", dependencies=[Depends(require_resource_permission("ai-config", "view"))])
def read_ai_config(db: Session = Depends(get_db)):
    return get_tenant_ai_config(db)


@router.patch("")
def patch_ai_config(
    updates: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("ai-config", "edit")),
):
    try:
        return update_tenant_ai_config(db, updates, changed_by=current_user.UserID)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
