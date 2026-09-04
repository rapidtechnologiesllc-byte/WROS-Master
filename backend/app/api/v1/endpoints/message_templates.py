"""
Message Template Management API

Endpoints for creating, editing, and managing email templates with dynamic fields.
Templates can be edited from the UI and include placeholders like {{employee_name}}, {{department}}, etc.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.user import Users
from app.models.message_template import MessageTemplate, TEMPLATE_KEYS, TEMPLATE_CHANNELS
from app.services.template_service import TemplateService
from app.core.logging import logger

router = APIRouter(prefix="/message-templates", tags=["message-templates"])


class TemplateRequest(BaseModel):
    """Request to create or update a template."""
    template_name: str
    channel: str
    subject: Optional[str] = None
    body: str


class TemplateResponse(BaseModel):
    """Template response."""
    id: int
    template_key: str
    template_name: str
    channel: str
    subject: Optional[str]
    body: str
    version: int
    is_active: bool
    created_by: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


@router.get("/keys")
def get_template_keys():
    """Get available template keys and channels."""
    return {
        "keys": TEMPLATE_KEYS,
        "channels": TEMPLATE_CHANNELS,
    }


@router.get("/{template_key}")
def get_template(
    template_key: str,
    channel: str = "EMAIL",
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Get the active template for a key."""
    if template_key not in TEMPLATE_KEYS:
        raise HTTPException(status_code=400, detail=f"Invalid template key: {template_key}")

    template = TemplateService.get_template(
        db=db,
        tenant_id=current_user.UserID,
        template_key=template_key,
        channel=channel,
    )

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return TemplateResponse.from_orm(template)


@router.get("/{template_key}/versions")
def get_template_versions(
    template_key: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Get all versions of a template."""
    if template_key not in TEMPLATE_KEYS:
        raise HTTPException(status_code=400, detail=f"Invalid template key: {template_key}")

    templates = db.query(MessageTemplate).filter(
        MessageTemplate.tenant_id == current_user.UserID,
        MessageTemplate.template_key == template_key,
    ).order_by(MessageTemplate.version.desc()).all()

    return [TemplateResponse.from_orm(t) for t in templates]


@router.post("/{template_key}")
def create_template_version(
    template_key: str,
    request: TemplateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Create a new version of a template."""
    if template_key not in TEMPLATE_KEYS:
        raise HTTPException(status_code=400, detail=f"Invalid template key: {template_key}")

    if request.channel not in TEMPLATE_CHANNELS:
        raise HTTPException(status_code=400, detail=f"Invalid channel: {request.channel}")

    template = TemplateService.create_template(
        db=db,
        tenant_id=current_user.UserID,
        template_key=template_key,
        template_name=request.template_name,
        channel=request.channel,
        subject=request.subject,
        body=request.body,
        created_by=current_user.UserID,
    )

    return TemplateResponse.from_orm(template)


@router.post("/{template_id}/activate")
def activate_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Activate a template version."""
    # Verify the template belongs to the current user's tenant
    template = db.query(MessageTemplate).filter(
        MessageTemplate.id == template_id,
        MessageTemplate.tenant_id == current_user.UserID,
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    success = TemplateService.activate_template(db, template_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to activate template")

    return {"status": "success", "message": "Template activated"}


@router.get("")
def list_templates(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """List all templates for the current tenant."""
    templates = TemplateService.list_templates(db, current_user.UserID)
    return [TemplateResponse.from_orm(t) for t in templates]
