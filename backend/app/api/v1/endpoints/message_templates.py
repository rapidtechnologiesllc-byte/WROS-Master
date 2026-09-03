"""
S-014/HRMS-0414 -- Message Template Engine
=============================================
Prefix: /templates
import logging
Tag:    message-templates

Routes:
  POST /templates                  create a new DRAFT version (any internal user)
  GET  /templates                  list, filterable by ?channel=&template_key=
  GET  /templates/{id}             single record
  POST /templates/{id}/activate    template.manage permission only
  GET  /templates/{id}/preview     render against a real candidate
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.schemas.message_template import (
    CreateTemplateRequest,
    TemplateListResponse,
    TemplatePreviewResponse,
    TemplateResponse,
)
from app.services.ai_conversation_service import resolve_default_tenant_id, resolve_thunder_config
from app.services.first_engagement_service import COMPANY_NAME
from app.services.message_template_service import (
    TemplateActivationConflict,
    TemplateNotFoundError,
    activate_template,
    create_template_version,
    get_template,
    list_templates,
    preview_template,
)

router = APIRouter(prefix="/templates", tags=["message-templates"])


def _to_response(t) -> TemplateResponse:
    return TemplateResponse(
        id=t.id, template_key=t.template_key, template_name=t.template_name, channel=t.channel,
        language=t.language, subject=t.subject, body=t.body, version=t.version, is_active=t.is_active,
        created_by=t.created_by, approved_by=t.approved_by, approved_at=t.approved_at, created_at=t.created_at,
    )


@router.post(
    "",
    response_model=TemplateResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("unknown", "create"))]
)
def create_template(
    body: CreateTemplateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    # tenant_id is the org's canonical default (see resolve_default_
    # tenant_id's docstring), NOT current_user.UserID -- a recruiter's
    # own ID would never match the tenant_id first_engagement_service
    # actually looks templates up under, silently making every
    # recruiter-created template unreachable.
    tenant_id = resolve_default_tenant_id(db)
    if not tenant_id:
        raise HTTPException(status_code=500, detail="No Super User account exists to own this template.")
    try:
        template = create_template_version(
            db, tenant_id=tenant_id, template_key=body.template_key, template_name=body.template_name,
            channel=body.channel, body=body.body, subject=body.subject, language=body.language,
            created_by=current_user.UserID,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_response(template)


@router.get(
    "",
    response_model=TemplateListResponse,
    dependencies=[Depends(require_resource_permission("unknown", "view"))]
)
def list_templates_endpoint(
    channel: str = None,
    template_key: str = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    tenant_id = resolve_default_tenant_id(db)
    templates = list_templates(db, tenant_id, channel=channel, template_key=template_key) if tenant_id else []
    return TemplateListResponse(templates=[_to_response(t) for t in templates])


@router.get(
    "/{template_id}",
    response_model=TemplateResponse,
    dependencies=[Depends(require_resource_permission("{template_id}", "view"))]
)
def get_template_endpoint(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    template = get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found.")
    return _to_response(template)


@router.post(
    "/{template_id}/activate",
    response_model=TemplateResponse,
    dependencies=[Depends(require_resource_permission("templates", "edit"))],
    summary="Activate a template version â€” template.manage permission only",
)
def activate_template_endpoint(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    try:
        template = activate_template(db, template_id, activated_by=current_user.UserID)
    except TemplateActivationConflict as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _to_response(template)


@router.get(
    "/{template_id}/preview",
    response_model=TemplatePreviewResponse,
    dependencies=[Depends(require_resource_permission("{template_id}", "view"))]
)
def preview_template_endpoint(
    template_id: int,
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    thunder_config = resolve_thunder_config(db, resolve_default_tenant_id(db))
    try:
        result = preview_template(db, template_id, candidate_id, agent_name=thunder_config["name"], company_name=COMPANY_NAME)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return TemplatePreviewResponse(**result)
