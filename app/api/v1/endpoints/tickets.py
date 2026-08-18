"""
Help Desk / IT-HR Ticketing.
==================================================================
Prefix: /tickets
Tag:    tickets

Internal-employees-only, same auth posture as /tasks -- any
authenticated Users row, every department/function, not HR/IT-only.

POST /tickets                          -- create (Impact x Urgency -> Priority, category routes to department)
GET  /tickets/categories                -- configured categories, for a create-form dropdown
POST /tickets/{id}/first-response       -- assignee marks first response sent
GET  /tickets/{id}/detail               -- SLA detail for one ticket

Admin (category routing + SLA policy config), gated same as
/rbac/departments (rbac.manage):
GET    /tickets/admin/routing
POST   /tickets/admin/routing
GET    /tickets/admin/sla-policies
PATCH  /tickets/admin/sla-policies/{priority}
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_permission, require_resource_permission
from app.models.task import TASK_PRIORITIES, Task
from app.models.ticket import TicketCategoryRoute, TicketDetail, TicketSLAPolicy
from app.models.user import Users
from app.schemas.task import TaskResponse
from app.schemas.ticket import (
    TicketCategoryResponse, TicketCategoryRouteCreateRequest, TicketCreateRequest,
    TicketDetailResponse, TicketSLAPolicyResponse, TicketSLAPolicyUpdateRequest,
)
from app.services.ticket_service import create_ticket, list_categories, record_first_response

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TaskResponse)
def create_ticket_endpoint(
    body: TicketCreateRequest, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db),
):
    try:
        return create_ticket(
            db, title=body.title, description=body.description, impact=body.impact, urgency=body.urgency,
            category=body.category, subcategory=body.subcategory, created_by_user_id=current_user.UserID,
            is_external=body.is_external,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/categories", response_model=list[TicketCategoryResponse])
def get_categories(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    return list_categories(db)


@router.post("/{task_id}/first-response", response_model=TicketDetailResponse)
def first_response(task_id: int, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id, Task.task_type == "TICKET").first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Ticket #{task_id} not found.")
    detail = record_first_response(db, task)
    if not detail:
        raise HTTPException(status_code=404, detail="Ticket has no SLA detail row.")
    return detail


@router.get("/{task_id}/detail", response_model=TicketDetailResponse)
def get_ticket_detail(task_id: int, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    detail = db.query(TicketDetail).filter(TicketDetail.task_id == task_id).first()
    if not detail:
        raise HTTPException(status_code=404, detail=f"No ticket detail for task #{task_id}.")
    return detail


@router.get("/admin/routing", response_model=list[TicketCategoryResponse], dependencies=[Depends(require_resource_permission("roles-permissions", "edit"))])
def list_routing_rules(db: Session = Depends(get_db)):
    return db.query(TicketCategoryRoute).order_by(TicketCategoryRoute.category).all()


@router.post("/admin/routing", response_model=TicketCategoryResponse, dependencies=[Depends(require_resource_permission("roles-permissions", "edit"))])
def create_routing_rule(body: TicketCategoryRouteCreateRequest, db: Session = Depends(get_db)):
    existing = db.query(TicketCategoryRoute).filter(
        TicketCategoryRoute.category == body.category, TicketCategoryRoute.subcategory == body.subcategory,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A route for this category/subcategory already exists.")
    route = TicketCategoryRoute(category=body.category, subcategory=body.subcategory, department_id=body.department_id)
    db.add(route)
    db.commit()
    db.refresh(route)
    return route


@router.get("/admin/sla-policies", response_model=list[TicketSLAPolicyResponse], dependencies=[Depends(require_resource_permission("roles-permissions", "edit"))])
def list_sla_policies(db: Session = Depends(get_db)):
    return db.query(TicketSLAPolicy).all()


@router.patch("/admin/sla-policies/{priority}", response_model=TicketSLAPolicyResponse, dependencies=[Depends(require_resource_permission("roles-permissions", "edit"))])
def update_sla_policy(priority: str, body: TicketSLAPolicyUpdateRequest, db: Session = Depends(get_db)):
    if priority not in TASK_PRIORITIES:
        raise HTTPException(status_code=422, detail=f"Unknown priority {priority!r}")
    policy = db.query(TicketSLAPolicy).filter(TicketSLAPolicy.priority == priority).first()
    if not policy:
        policy = TicketSLAPolicy(priority=priority)
    policy.response_minutes = body.response_minutes
    policy.resolution_minutes = body.resolution_minutes
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy
