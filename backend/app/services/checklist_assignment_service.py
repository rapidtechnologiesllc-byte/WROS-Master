"""Assign a checklist template to a candidate: copies the template's items into a new
CandidateChecklist; the first queue item becomes active. Used by HR (POST
/checklist/assign) and by the hiring pipeline when a candidate accepts an offer."""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.checklist import CandidateChecklist, CandidateChecklistItem, ChecklistTemplate
from app.schemas.checklist import CandidateChecklistItemResponse, CandidateChecklistResponse


class ChecklistAlreadyAssigned(Exception):
    pass


def activate_first_queue_item(db: Session, checklist_id: int) -> None:
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


def assign_template(db: Session, candidate_id: str, template: ChecklistTemplate,
                    assigned_by_user_id: Optional[str]) -> CandidateChecklist:
    """Flushes, does not commit. Raises ChecklistAlreadyAssigned for a duplicate."""
    existing = db.query(CandidateChecklist).filter(CandidateChecklist.candidate_id == candidate_id,
                                                   CandidateChecklist.template_id == template.id).first()
    if existing is not None:
        raise ChecklistAlreadyAssigned(
            f"Template '{template.name}' (ID {template.id}) is already assigned to candidate '{candidate_id}'. "
            f"Duplicate assignment is not allowed.")
    checklist = CandidateChecklist(candidate_id=candidate_id, template_id=template.id, template_name=template.name,
                                   assigned_by_user_id=assigned_by_user_id, status="active")
    db.add(checklist)
    db.flush()
    now = datetime.now()
    for t_item in template.items:
        db.add(CandidateChecklistItem(
            checklist_id=checklist.id, template_item_id=t_item.id, title=t_item.title,
            description=t_item.description, item_type=t_item.item_type, order_index=t_item.order_index,
            status="pending",
            due_date=now + timedelta(days=t_item.due_days_offset) if t_item.due_days_offset is not None else None))
    db.flush()
    activate_first_queue_item(db, checklist.id)
    return checklist


def checklist_response(checklist: CandidateChecklist) -> CandidateChecklistResponse:
    """A candidate checklist with its items and per-status / per-type counts (the API response)."""
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
