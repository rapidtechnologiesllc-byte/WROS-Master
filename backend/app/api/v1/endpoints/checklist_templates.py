"""
Checklist template administration (Admin & Settings > Checklists, prefix /checklist/hr/templates).

Creating, editing and deleting templates and their items is gated by the "checklists" resource,
the same resource as the Checklists menu item. Reading templates stays on "candidates": the candidate
profile's pre-onboarding drawer lists templates to assign. Assigning a template to a candidate and
working a candidate's checklist live in checklists.py.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.checklist import ChecklistTemplate, ChecklistTemplateItem
from app.schemas.checklist import (
    ChecklistActionResponse,
    ChecklistItemCreate,
    ChecklistItemResponse,
    ChecklistItemUpdate,
    ChecklistTemplateCreate,
    ChecklistTemplateListResponse,
    ChecklistTemplateResponse,
    ChecklistTemplateSummary,
    ChecklistTemplateUpdate,
)

router = APIRouter(prefix="/checklist", tags=["checklist"])


# ===========================================================================
# HR — TEMPLATE CRUD
# ===========================================================================

@router.post(
    "/hr/templates",
    response_model=ChecklistTemplateResponse,
    dependencies=[Depends(require_resource_permission("checklists", "create"))],
    summary="Create a new checklist template",
)
def create_template(
    request: ChecklistTemplateCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """Create a reusable checklist template, optionally with initial items."""
    template = ChecklistTemplate(
        name=request.name,
        description=request.description,
        created_by_user_id=user.UserID,
    )
    db.add(template)
    db.flush()  # get template.id before adding items

    for idx, item_data in enumerate(request.items or []):
        item = ChecklistTemplateItem(
            template_id=template.id,
            title=item_data.title,
            description=item_data.description,
            item_type=item_data.item_type,
            order_index=item_data.order_index if item_data.order_index else idx,
            due_days_offset=item_data.due_days_offset,
        )
        db.add(item)

    db.commit()
    db.refresh(template)
    return template

@router.get(
    "/hr/templates",
    response_model=ChecklistTemplateListResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="List all checklist templates",
)
def list_templates(
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    templates = db.query(ChecklistTemplate).order_by(ChecklistTemplate.created_at.desc()).all()
    summaries = [
        ChecklistTemplateSummary(
            id=t.id,
            name=t.name,
            description=t.description,
            created_by_user_id=t.created_by_user_id,
            created_at=t.created_at,
            item_count=len(t.items),
        )
        for t in templates
    ]
    return ChecklistTemplateListResponse(total=len(summaries), templates=summaries)

@router.get(
    "/hr/templates/{template_id}",
    response_model=ChecklistTemplateResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get a single template with all its items",
)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    template = db.query(ChecklistTemplate).filter(ChecklistTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found.")
    return template

@router.put(
    "/hr/templates/{template_id}",
    response_model=ChecklistTemplateResponse,
    dependencies=[Depends(require_resource_permission("checklists", "edit"))],
    summary="Update template name / description",
)
def update_template(
    template_id: int,
    request: ChecklistTemplateUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    template = db.query(ChecklistTemplate).filter(ChecklistTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found.")

    if request.name is not None:
        template.name = request.name
    if request.description is not None:
        template.description = request.description

    db.commit()
    db.refresh(template)
    return template

@router.delete(
    "/hr/templates/{template_id}",
    response_model=ChecklistActionResponse,
    dependencies=[Depends(require_resource_permission("checklists", "delete"))],
    summary="Delete a template (cascade deletes its items)",
)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    template = db.query(ChecklistTemplate).filter(ChecklistTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found.")

    db.delete(template)
    db.commit()
    return ChecklistActionResponse(
        status="success",
        message=f"Template '{template.name}' (ID {template_id}) deleted.",
    )

# ===========================================================================
# HR — TEMPLATE ITEM CRUD
# ===========================================================================

@router.post(
    "/hr/templates/{template_id}/items",
    response_model=ChecklistItemResponse,
    dependencies=[Depends(require_resource_permission("checklists", "edit"))],
    summary="Add an item to a checklist template",
)
def add_template_item(
    template_id: int,
    request: ChecklistItemCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    template = db.query(ChecklistTemplate).filter(ChecklistTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found.")

    item = ChecklistTemplateItem(
        template_id=template_id,
        title=request.title,
        description=request.description,
        item_type=request.item_type,
        order_index=request.order_index,
        due_days_offset=request.due_days_offset,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.put(
    "/hr/templates/{template_id}/items/{item_id}",
    response_model=ChecklistItemResponse,
    dependencies=[Depends(require_resource_permission("checklists", "edit"))],
    summary="Update a template item",
)
def update_template_item(
    template_id: int,
    item_id: int,
    request: ChecklistItemUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    item = (
        db.query(ChecklistTemplateItem)
        .filter(
            ChecklistTemplateItem.id == item_id,
            ChecklistTemplateItem.template_id == template_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found in template {template_id}.")

    if request.title is not None:
        item.title = request.title
    if request.description is not None:
        item.description = request.description
    if request.item_type is not None:
        item.item_type = request.item_type
    if request.order_index is not None:
        item.order_index = request.order_index
    if request.due_days_offset is not None:
        item.due_days_offset = request.due_days_offset

    db.commit()
    db.refresh(item)
    return item

@router.delete(
    "/hr/templates/{template_id}/items/{item_id}",
    response_model=ChecklistActionResponse,
    dependencies=[Depends(require_resource_permission("checklists", "edit"))],
    summary="Delete a template item",
)
def delete_template_item(
    template_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    item = (
        db.query(ChecklistTemplateItem)
        .filter(
            ChecklistTemplateItem.id == item_id,
            ChecklistTemplateItem.template_id == template_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found in template {template_id}.")

    db.delete(item)
    db.commit()
    return ChecklistActionResponse(status="success", message=f"Item {item_id} deleted.")
