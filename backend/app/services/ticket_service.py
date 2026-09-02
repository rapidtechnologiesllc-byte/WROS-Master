"""
Help Desk / IT-HR Ticketing -- built on top of Task (task_type='TICKET'),
import logging
not a parallel object. Internal-employees-only.

Real decisions, 2026-08-04 session (see module docstring in
app.models.ticket for the full ServiceNow/Salesforce/Zendesk/Freshdesk
research this was built against):
- Priority is DERIVED from Impact x Urgency (ServiceNow's own real
  pattern), never picked directly -- a more precise anti-inflation
  mechanism for tickets specifically than Task's own Thunder-challenge
  gate (which still applies if a caller manually overrides Priority
  to URGENT after the fact, but the normal ticket-creation path never
  needs it).
- Category routes to a Department via the real, admin-configurable
  TicketCategoryRoute table -- no hardcoded HR/IT/Facilities/Other
  list, covers every department per Avinash's explicit direction.
- Unmatched category: created with department_id=None (unassigned,
  no round-robin fires) rather than guessing a department -- surfaced
  for manual triage, never silently misrouted.
"""
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.ticket import (
    IMPACT_URGENCY_PRIORITY_MATRIX, TICKET_IMPACTS, TICKET_URGENCIES,
    TicketCategoryRoute, TicketDetail, TicketSLAPolicy,
)


def derive_priority_from_impact_urgency(impact: str, urgency: str) -> str:
    if impact not in TICKET_IMPACTS:
        raise ValueError(f"Unknown impact {impact!r}")
    if urgency not in TICKET_URGENCIES:
        raise ValueError(f"Unknown urgency {urgency!r}")
    return IMPACT_URGENCY_PRIORITY_MATRIX[(impact, urgency)]


def resolve_category_department(db: Session, *, category: str, subcategory: Optional[str] = None) -> Optional[int]:
    """Exact (category, subcategory) match first, then a
    (category, NULL) fallback route -- lets an admin configure one
    catch-all route per category without enumerating every
    subcategory."""
    route = db.query(TicketCategoryRoute).filter(
        TicketCategoryRoute.category == category,
        TicketCategoryRoute.subcategory == subcategory,
        TicketCategoryRoute.is_active.is_(True),
    ).first()
    if not route and subcategory is not None:
        route = db.query(TicketCategoryRoute).filter(
            TicketCategoryRoute.category == category,
            TicketCategoryRoute.subcategory.is_(None),
            TicketCategoryRoute.is_active.is_(True),
        ).first()
    return route.department_id if route else None


def list_categories(db: Session) -> List[TicketCategoryRoute]:
    return db.query(TicketCategoryRoute).filter(TicketCategoryRoute.is_active.is_(True)).order_by(TicketCategoryRoute.category).all()


def create_ticket(
    db: Session,
    *,
    title: str,
    description: Optional[str],
    impact: str,
    urgency: str,
    category: str,
    subcategory: Optional[str] = None,
    created_by_user_id: str,
    is_external: bool = False,
    now: Optional[datetime] = None,
) -> Task:
    from app.services.task_service import create_task

    now = now or datetime.utcnow()
    priority = derive_priority_from_impact_urgency(impact, urgency)
    department_id = resolve_category_department(db, category=category, subcategory=subcategory)

    task = create_task(
        db, title=title, description=description, priority=priority,
        created_by_user_id=created_by_user_id, department_id=department_id,
        is_external=is_external, task_type="TICKET", category=category, subcategory=subcategory,
    )

    policy = db.query(TicketSLAPolicy).filter(TicketSLAPolicy.priority == priority).first()
    response_minutes = policy.response_minutes if policy else 24 * 60
    resolution_minutes = policy.resolution_minutes if policy else 7 * 24 * 60

    detail = TicketDetail(
        task_id=task.id, impact=impact, urgency=urgency,
        response_due_at=now + timedelta(minutes=response_minutes),
        resolution_due_at=now + timedelta(minutes=resolution_minutes),
    )
    db.add(detail)

    # Response-SLA due date IS the ticket's own due_date for the daily-
    # list ranking (Task.due_date drives Layer 1's hard filter) -- a
    # ticket with no due_date would never surface on anyone's daily
    # list, silently defeating the SLA it just committed to.
    task.due_date = detail.response_due_at
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def record_first_response(db: Session, task: Task, *, now: Optional[datetime] = None) -> Optional[TicketDetail]:
    """Once responded to, the ticket's relevant deadline shifts from
    Response SLA to Resolution SLA -- Task.due_date (which drives the
    daily-list Layer 1 hard filter) moves with it, so the ticket keeps
    surfacing correctly until actually resolved instead of looking
    perpetually overdue against a response deadline it already met."""
    detail = db.query(TicketDetail).filter(TicketDetail.task_id == task.id).first()
    if detail and detail.first_response_at is None:
        detail.first_response_at = now or datetime.utcnow()
        db.add(detail)
        task.due_date = detail.resolution_due_at
        task.is_escalated = False  # a response-SLA escalation shouldn't linger once resolution becomes the live deadline
        db.add(task)
        db.commit()
        db.refresh(detail)
    return detail
