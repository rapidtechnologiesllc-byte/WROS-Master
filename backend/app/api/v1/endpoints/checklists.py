"""
Checklist API Endpoints

HR/Admin Routes  (prefix: /checklist/hr)
  - Template and template item CRUD: checklist_templates.py (gated by "checklists")
  - Assign template to candidate
  - View / manually complete candidate items

Candidate Routes  (prefix: /checklist/candidate)
  - View own checklists
  - Mark an item complete (queue auto-activates next)
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_candidate, get_current_internal_user, require_resource_permission
from app.services.checklist_assignment_service import (
    ChecklistAlreadyAssigned,
    activate_first_queue_item,
    assign_template,
    checklist_response,
)
from app.models.checklist import (
    ChecklistTemplate,
    CandidateChecklist,
    CandidateChecklistItem,
)
from app.models.candidate import Candidate
from app.schemas.checklist import (
    AssignChecklistRequest,
    CandidateChecklistItemResponse,
    CandidateChecklistListResponse,
    CandidateChecklistResponse,
    CompleteItemResponse,
)

router = APIRouter(prefix="/checklist", tags=["checklist"])

# ===========================================================================
# HELPERS
# ===========================================================================

def _activate_first_queue_item(db: Session, checklist_id: int) -> None:
    activate_first_queue_item(db, checklist_id)

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
    - To-do items start as 'pending' (candidate can complete anytime).
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

    try:
        checklist = assign_template(db, request.candidate_id, template, user.UserID)
    except ChecklistAlreadyAssigned as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    db.commit()
    db.refresh(checklist)
    return checklist_response(checklist)

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
        checklists=[checklist_response(c) for c in checklists],
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
    HR can mark any to-do or active queue item complete on behalf of a candidate.
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
        checklists=[checklist_response(c) for c in checklists],
    )

# ===========================================================================
# CANDIDATE — SUBMIT AN ITEM (marks done from candidate side)
# ===========================================================================

@router.patch(
    "/candidate/item/{item_id}/complete",
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

