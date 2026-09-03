"""
import logging
Checklist API Endpoints

HR/Admin Routes  (prefix: /checklist/hr)
  - Template CRUD
  - Template item CRUD
  - Assign template to candidate
  - View / manually complete candidate items

Candidate Routes  (prefix: /checklist/candidate)
  - View own checklists
  - Mark an item complete (queue auto-activates next)
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.core.dependencies import (
    get_current_internal_user,
    get_current_candidate,
    require_resource_permission,
)
from app.models.checklist import (
    ChecklistTemplate,
    ChecklistTemplateItem,
    CandidateChecklist,
    CandidateChecklistItem,
)
from app.models.candidate import Candidate
from app.schemas.checklist import (
    AssignChecklistRequest,
    ChecklistActionResponse,
    ChecklistItemCreate,
    ChecklistItemResponse,
    ChecklistItemUpdate,
    ChecklistTemplateCreate,
    ChecklistTemplateListResponse,
    ChecklistTemplateResponse,
    ChecklistTemplateSummary,
    ChecklistTemplateUpdate,
    CandidateChecklistItemResponse,
    CandidateChecklistListResponse,
    CandidateChecklistResponse,
    CompleteItemResponse,
)

router = APIRouter(prefix="/checklist", tags=["checklist"])

# ===========================================================================
# HELPERS
# ===========================================================================

def _build_checklist_response(checklist: CandidateChecklist) -> CandidateChecklistResponse:
    """Convert a CandidateChecklist ORM object to a CandidateChecklistResponse."""
    item_responses = [
        CandidateChecklistItemResponse(
            id=item.id,
            checklist_id=item.checklist_id,
            template_item_id=item.template_item_id,
            title=item.title,
            description=item.description,
            item_type=item.item_type,
            order_index=item.order_index,
            status=item.status,
            due_date=item.due_date,
            activated_at=item.activated_at,
            submitted_at=item.submitted_at,
            completed_at=item.completed_at,
        )
        for item in checklist.items
    ]

    total = len(item_responses)
    completed = sum(1 for i in item_responses if i.status == "completed")
    submitted = sum(1 for i in item_responses if i.status == "submitted")
    todo_count = sum(1 for i in item_responses if i.item_type == "todo")
    queue_count = sum(1 for i in item_responses if i.item_type == "queue")
    active_queue = next(
        (i for i in item_responses if i.item_type == "queue" and i.status == "active"),
        None,
    )

    return CandidateChecklistResponse(
        id=checklist.id,
        candidate_id=checklist.candidate_id,
        template_id=checklist.template_id,
        template_name=checklist.template_name,
        assigned_by_user_id=checklist.assigned_by_user_id,
        assigned_at=checklist.assigned_at,
        status=checklist.status,
        completed_at=checklist.completed_at,
        items=item_responses,
        total_items=total,
        completed_items=completed,
        submitted_items=submitted,
        todo_items=todo_count,
        queue_items=queue_count,
        active_queue_item=active_queue,
    )

def _activate_first_queue_item(db: Session, checklist_id: int) -> None:
    """Set the lowest-order-index queue item to 'active' on a fresh checklist."""
    first_queue = (
        db.query(CandidateChecklistItem)
        .filter(
            CandidateChecklistItem.checklist_id == checklist_id,
            CandidateChecklistItem.item_type == "queue",
            CandidateChecklistItem.status == "pending",
        )
        .order_by(CandidateChecklistItem.order_index)
        .first()
    )
    if first_queue:
        first_queue.status = "active"
        first_queue.activated_at = datetime.now()

def _complete_item_logic(
    db: Session, item: CandidateChecklistItem
) -> Optional[CandidateChecklistItem]:
    """
    HR-only completion logic: moves an item from any non-completed status
    to 'completed' and triggers queue auto-advance.

    Returns the next activated queue item (or None).
    Raises HTTPException if item is already completed.
    """
    if item.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Item is already completed.",
        )

    # Mark as completed (HR can complete from any state)
    item.status = "completed"
    item.completed_at = datetime.now()

    # Auto-activate next queue item if this was a queue item
    next_item: Optional[CandidateChecklistItem] = None
    if item.item_type == "queue":
        next_item = (
            db.query(CandidateChecklistItem)
            .filter(
                CandidateChecklistItem.checklist_id == item.checklist_id,
                CandidateChecklistItem.item_type == "queue",
                CandidateChecklistItem.status == "pending",
                CandidateChecklistItem.order_index > item.order_index,
            )
            .order_by(CandidateChecklistItem.order_index)
            .first()
        )
        if next_item:
            next_item.status = "active"
            next_item.activated_at = datetime.now()

    # Mark checklist as completed only when ALL items are 'completed'
    # (items in 'submitted' state are still pending HR review)
    pending_count = (
        db.query(CandidateChecklistItem)
        .filter(
            CandidateChecklistItem.checklist_id == item.checklist_id,
            CandidateChecklistItem.status != "completed",
        )
        .count()
    )
    if pending_count == 0:
        checklist = (
            db.query(CandidateChecklist)
            .filter(CandidateChecklist.id == item.checklist_id)
            .first()
        )
        if checklist:
            checklist.status = "completed"
            checklist.completed_at = datetime.now()

    db.commit()
    db.refresh(item)
    if next_item:
        db.refresh(next_item)

    return next_item

# ===========================================================================
# HR — TEMPLATE CRUD
# ===========================================================================

@router.post(
    "/hr/templates",
    response_model=ChecklistTemplateResponse,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
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
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
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
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
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
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
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
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
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
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
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

# ===========================================================================
# HR — ASSIGN CHECKLIST TO CANDIDATE
# ===========================================================================

@router.post(
    "/hr/assign",
    response_model=CandidateChecklistResponse,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Assign a checklist template to a candidate",
)
def assign_checklist(
    request: AssignChecklistRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Copies all items from the template into a new CandidateChecklist.
    - Todo items start as 'pending' (candidate can complete anytime).
    - Queue items: only the first (lowest order_index) becomes 'active';
      all others remain 'pending' until triggered by the previous completion.
    """
    # Validate candidate
    candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{request.candidate_id}' not found.")

    # Validate template
    template = db.query(ChecklistTemplate).filter(ChecklistTemplate.id == request.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {request.template_id} not found.")

    # Prevent duplicate assignment — same template cannot be assigned to the same candidate twice
    existing_assignment = (
        db.query(CandidateChecklist)
        .filter(
            CandidateChecklist.candidate_id == request.candidate_id,
            CandidateChecklist.template_id == request.template_id,
        )
        .first()
    )
    if existing_assignment:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Template '{template.name}' (ID {request.template_id}) is already assigned "
                f"to candidate '{request.candidate_id}'. Duplicate assignment is not allowed."
            ),
        )

    # Create candidate checklist
    checklist = CandidateChecklist(
        candidate_id=request.candidate_id,
        template_id=template.id,
        template_name=template.name,
        assigned_by_user_id=user.UserID,
        status="active",
    )
    db.add(checklist)
    db.flush()  # get checklist.id

    now = datetime.now()
    for t_item in template.items:
        due_date = (
            now + timedelta(days=t_item.due_days_offset)
            if t_item.due_days_offset is not None
            else None
        )
        c_item = CandidateChecklistItem(
            checklist_id=checklist.id,
            template_item_id=t_item.id,
            title=t_item.title,
            description=t_item.description,
            item_type=t_item.item_type,
            order_index=t_item.order_index,
            status="pending",
            due_date=due_date,
        )
        db.add(c_item)

    db.flush()

    # Activate the first queue item
    _activate_first_queue_item(db, checklist.id)

    db.commit()
    db.refresh(checklist)
    return _build_checklist_response(checklist)

# ===========================================================================
# HR — VIEW & MANAGE CANDIDATE CHECKLISTS
# ===========================================================================

@router.get(
    "/hr/candidate/{candidate_id}",
    response_model=CandidateChecklistListResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="View all checklists for a specific candidate",
)
def get_candidate_checklists(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    checklists = (
        db.query(CandidateChecklist)
        .filter(CandidateChecklist.candidate_id == candidate_id)
        .order_by(CandidateChecklist.assigned_at.desc())
        .all()
    )
    return CandidateChecklistListResponse(
        candidate_id=candidate_id,
        total_checklists=len(checklists),
        checklists=[_build_checklist_response(c) for c in checklists],
    )

@router.put(
    "/hr/candidate-item/{item_id}/complete",
    response_model=CompleteItemResponse,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="HR manually marks a checklist item as complete",
)
def hr_complete_item(
    item_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    HR can mark any todo or active queue item complete on behalf of a candidate.
    Queue items automatically activate the next queue item.
    """
    item = db.query(CandidateChecklistItem).filter(CandidateChecklistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Checklist item {item_id} not found.")

    next_item = _complete_item_logic(db, item)

    # Re-query to reflect DB state
    db.refresh(item)
    checklist = db.query(CandidateChecklist).filter(CandidateChecklist.id == item.checklist_id).first()

    return CompleteItemResponse(
        status="success",
        message=(
            f"Item '{item.title}' marked complete."
            + (f" Next queue item '{next_item.title}' is now active." if next_item else "")
        ),
        completed_item=CandidateChecklistItemResponse(
            id=item.id,
            checklist_id=item.checklist_id,
            template_item_id=item.template_item_id,
            title=item.title,
            description=item.description,
            item_type=item.item_type,
            order_index=item.order_index,
            status=item.status,
            due_date=item.due_date,
            activated_at=item.activated_at,
            submitted_at=item.submitted_at,
            completed_at=item.completed_at,
        ),
        next_active_item=(
            CandidateChecklistItemResponse(
                id=next_item.id,
                checklist_id=next_item.checklist_id,
                template_item_id=next_item.template_item_id,
                title=next_item.title,
                description=next_item.description,
                item_type=next_item.item_type,
                order_index=next_item.order_index,
                status=next_item.status,
                due_date=next_item.due_date,
                activated_at=next_item.activated_at,
                submitted_at=next_item.submitted_at,
                completed_at=next_item.completed_at,
            )
            if next_item
            else None
        ),
        checklist_completed=(checklist.status == "completed") if checklist else False,
    )

# ===========================================================================
# CANDIDATE — VIEW OWN CHECKLISTS
# ===========================================================================

@router.get(
    "/candidate/my-checklists",
    dependencies=[Depends(get_current_internal_user)],
    response_model=CandidateChecklistListResponse,
    summary="Get the authenticated candidate's checklists",
)
def get_my_checklists(
    db: Session = Depends(get_db),
    user=Depends(get_current_candidate),
):
    checklists = (
        db.query(CandidateChecklist)
        .filter(CandidateChecklist.candidate_id == user.candidateID)
        .order_by(CandidateChecklist.assigned_at.desc())
        .all()
    )
    return CandidateChecklistListResponse(
        candidate_id=user.candidateID,
        total_checklists=len(checklists),
        checklists=[_build_checklist_response(c) for c in checklists],
    )

# ===========================================================================
# CANDIDATE — SUBMIT AN ITEM (marks done from candidate side)
# ===========================================================================

@router.put(
    "/candidate/item/{item_id}/complete",
    dependencies=[Depends(get_current_internal_user)],
    response_model=CompleteItemResponse,
    summary="Candidate submits a checklist item (awaiting HR verification)",
)
def candidate_complete_item(
    item_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_candidate),
):
    """
    Candidate signals they have finished a task.

    - Moves the item status from 'pending'/'active' → 'submitted'.
    - Does NOT mark the item as 'completed' — HR must verify and complete it.
    - For queue items, the next queue item is NOT activated yet; it becomes
      active only after HR marks this item as 'completed'.
    - Raises 400 if the item is already submitted or completed.
    - Raises 400 if a queue item is not yet the active queue item.
    """
    # Verify item belongs to this candidate
    item = (
        db.query(CandidateChecklistItem)
        .join(CandidateChecklist)
        .filter(
            CandidateChecklistItem.id == item_id,
            CandidateChecklist.candidate_id == user.candidateID,
        )
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=404,
            detail=f"Checklist item {item_id} not found or does not belong to you.",
        )

    if item.status in ("submitted", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Item is already submitted and awaiting HR verification."
                if item.status == "submitted"
                else "Item is already completed."
            ),
        )

    if item.item_type == "queue" and item.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This queue item is not yet unlocked — "
                "complete the previous queue item first."
            ),
        )

    # Move to 'submitted' — awaiting HR review
    item.status = "submitted"
    item.submitted_at = datetime.now()
    db.commit()
    db.refresh(item)

    checklist = db.query(CandidateChecklist).filter(
        CandidateChecklist.id == item.checklist_id
    ).first()

    return CompleteItemResponse(
        status="success",
        message=(
            f"Item '{item.title}' submitted successfully. "
            "It will be marked complete after HR verification."
        ),
        completed_item=CandidateChecklistItemResponse(
            id=item.id,
            checklist_id=item.checklist_id,
            template_item_id=item.template_item_id,
            title=item.title,
            description=item.description,
            item_type=item.item_type,
            order_index=item.order_index,
            status=item.status,
            due_date=item.due_date,
            activated_at=item.activated_at,
            submitted_at=item.submitted_at,
            completed_at=item.completed_at,
        ),
        next_active_item=None,   # queue does not advance until HR verifies
        checklist_completed=False,
    )

