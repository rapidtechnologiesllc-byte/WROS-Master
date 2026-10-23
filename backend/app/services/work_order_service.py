"""
Work Order Service - DEFECT-1: Work Order / PO Model

A Work Order (aka PO, SOW, or Engagement Record) is the signed authority
to bill for a placed candidate/employee against a specific client demand.

Unlike Opportunity (revenue estimate), WorkOrder is revenue authority:
- PO number (signed by client)
- Rate terms (bill rate, pay rate, spread)
- Period (start/end dates)
- Named resource (the specific candidate/employee placed)
- Invoicing contact (bill-to address)

Linkage: Demand → Candidate → Employee → WorkOrder → Project → Revenue
"""
import logging
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.work_order import WorkOrder
from app.models.demand import Demand
from app.models.client import Client
from app.models.employee import Employee
from app.models.project import Project

logger = logging.getLogger(__name__)

class WorkOrderValidationError(Exception):
    """Raised when work order creation/update violates business rules."""

def create_work_order(
    db: Session,
    *,
    tenant_id: int,
    po_number: str,
    demand_id: str,
    client_id: str,
    billing_rate_usd_cents: int,
    start_date: date,
    sow_reference: Optional[str] = None,
    employee_id: Optional[str] = None,
    project_id: Optional[str] = None,
    pay_rate_usd_cents: Optional[int] = None,
    end_date: Optional[date] = None,
    invoicing_contact_email: Optional[str] = None,
    invoicing_contact_name: Optional[str] = None,
    status: str = "ACTIVE",
) -> WorkOrder:
    """
    Create a new Work Order.

    Args:
        tenant_id: Tenant ID (scoped access)
        po_number: Client-assigned PO number (one PO may cover several placements, so it is not unique)
        demand_id: Link to Demand (DIRECT or Opportunity-sourced)
        client_id: Bill-to Client
        billing_rate_usd_cents: Billing rate to client (USD cents)
        start_date: Work start date
        sow_reference: Optional SOW/statement of work URL or ID
        employee_id: Named resource on PO (nullable until hire)
        project_id: Auto-linked when project created
        pay_rate_usd_cents: Pay rate to employee (USD cents, optional until hire)
        end_date: Work end date (nullable = open-ended)
        invoicing_contact_email: Invoice recipient email
        invoicing_contact_name: Invoice recipient name
        status: ACTIVE, ENDED, PAUSED (default: ACTIVE)

    Returns:
        WorkOrder: The created work order

    Raises:
        WorkOrderValidationError: If business rules violated
    """
    po_number = (po_number or "").strip()
    if not po_number:
        raise WorkOrderValidationError("The client's PO number is required.")

    # Validate demand exists
    demand = db.query(Demand).filter(Demand.id == demand_id, Demand.tenant_id == tenant_id).first()
    if not demand:
        raise WorkOrderValidationError(f"Demand {demand_id} not found in tenant {tenant_id}")

    # Validate client exists
    client = db.query(Client).filter(Client.id == client_id, Client.tenant_id == tenant_id).first()
    if not client:
        raise WorkOrderValidationError(f"Client {client_id} not found in tenant {tenant_id}")
    # the PO authorises billing this client for this client's job, never another client's
    if demand.client_id and demand.client_id != client_id:
        raise WorkOrderValidationError(f"Job {demand_id} belongs to a different client than {client.company_name}.")

    # Validate employee if provided
    if employee_id:
        employee = db.query(Employee).filter(Employee.id == employee_id, Employee.tenant_id == tenant_id).first()
        if not employee:
            raise WorkOrderValidationError(f"Employee {employee_id} not found in tenant {tenant_id}")

    # Validate project if provided
    if project_id:
        project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == tenant_id).first()
        if not project:
            raise WorkOrderValidationError(f"Project {project_id} not found in tenant {tenant_id}")
        if project.client_id != client_id:
            raise WorkOrderValidationError(f"Project {project.name} belongs to a different client.")

    # Validate dates
    if end_date and end_date < start_date:
        raise WorkOrderValidationError(f"End date {end_date} cannot be before start date {start_date}")

    # Validate billing rate
    if billing_rate_usd_cents < 0:
        raise WorkOrderValidationError(f"Billing rate cannot be negative: {billing_rate_usd_cents}")

    # Validate pay rate if provided
    if pay_rate_usd_cents is not None and pay_rate_usd_cents < 0:
        raise WorkOrderValidationError(f"Pay rate cannot be negative: {pay_rate_usd_cents}")

    work_order = WorkOrder(
        tenant_id=tenant_id,
        po_number=po_number,
        demand_id=demand_id,
        client_id=client_id,
        billing_rate_usd_cents=billing_rate_usd_cents,
        start_date=start_date,
        sow_reference=sow_reference,
        employee_id=employee_id,
        project_id=project_id,
        pay_rate_usd_cents=pay_rate_usd_cents,
        end_date=end_date,
        invoicing_contact_email=invoicing_contact_email,
        invoicing_contact_name=invoicing_contact_name,
        status=status,
    )
    db.add(work_order)
    return work_order

def update_work_order(
    db: Session,
    work_order: WorkOrder,
    *,
    pay_rate_usd_cents: Optional[int] = None,
    end_date: Optional[date] = None,
    employee_id: Optional[str] = None,
    project_id: Optional[str] = None,
    invoicing_contact_email: Optional[str] = None,
    invoicing_contact_name: Optional[str] = None,
    status: Optional[str] = None,
) -> WorkOrder:
    """
    Update an existing Work Order.

    Only certain fields can be updated after creation:
    - pay_rate_usd_cents (set when employee hired)
    - end_date (if work ends early)
    - employee_id (link employee after hire)
    - project_id (link project when created)
    - invoicing contact details
    - status (ACTIVE, ENDED, PAUSED)

    PO number and billing rate CANNOT be changed (immutable after signature).
    """
    if pay_rate_usd_cents is not None:
        if pay_rate_usd_cents < 0:
            raise WorkOrderValidationError(f"Pay rate cannot be negative: {pay_rate_usd_cents}")
        work_order.pay_rate_usd_cents = pay_rate_usd_cents

    if end_date is not None:
        if end_date < work_order.start_date:
            raise WorkOrderValidationError(f"End date {end_date} cannot be before start date {work_order.start_date}")
        work_order.end_date = end_date

    if employee_id is not None:
        employee = db.query(Employee).filter(
            Employee.id == employee_id,
            Employee.tenant_id == work_order.tenant_id
        ).first()
        if not employee:
            raise WorkOrderValidationError(f"Employee {employee_id} not found in tenant {work_order.tenant_id}")
        work_order.employee_id = employee_id

    if project_id is not None:
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.tenant_id == work_order.tenant_id
        ).first()
        if not project:
            raise WorkOrderValidationError(f"Project {project_id} not found in tenant {work_order.tenant_id}")
        if project.client_id != work_order.client_id:
            raise WorkOrderValidationError(f"Project {project.name} belongs to a different client than this PO.")
        work_order.project_id = project_id

    if invoicing_contact_email is not None:
        work_order.invoicing_contact_email = invoicing_contact_email

    if invoicing_contact_name is not None:
        work_order.invoicing_contact_name = invoicing_contact_name

    if status is not None:
        if status not in ("ACTIVE", "ENDED", "PAUSED"):
            raise WorkOrderValidationError(f"Invalid status: {status}. Must be ACTIVE, ENDED, or PAUSED.")
        work_order.status = status

    work_order.updated_at = datetime.utcnow()
    db.add(work_order)
    return work_order

def get_work_order_by_id(db: Session, work_order_id: str, tenant_id: int) -> Optional[WorkOrder]:
    """Get a work order by ID (tenant-scoped)."""
    return db.query(WorkOrder).filter(
        WorkOrder.id == work_order_id,
        WorkOrder.tenant_id == tenant_id
    ).first()

def get_work_orders_by_demand(db: Session, demand_id: str, tenant_id: int) -> List[WorkOrder]:
    """Get all work orders for a specific demand."""
    return db.query(WorkOrder).filter(
        WorkOrder.demand_id == demand_id,
        WorkOrder.tenant_id == tenant_id
    ).all()

def get_work_orders_by_project(db: Session, project_id: str, tenant_id: int) -> List[WorkOrder]:
    """Get all work orders linked to a specific project."""
    return db.query(WorkOrder).filter(
        WorkOrder.project_id == project_id,
        WorkOrder.tenant_id == tenant_id
    ).all()

def get_work_orders_by_employee(db: Session, employee_id: str, tenant_id: int) -> List[WorkOrder]:
    """Get all work orders for a specific employee."""
    return db.query(WorkOrder).filter(
        WorkOrder.employee_id == employee_id,
        WorkOrder.tenant_id == tenant_id
    ).all()

def get_work_orders_by_client(db: Session, client_id: str, tenant_id: int) -> List[WorkOrder]:
    """Get all work orders for a specific client."""
    return db.query(WorkOrder).filter(
        WorkOrder.client_id == client_id,
        WorkOrder.tenant_id == tenant_id
    ).all()

def get_all_work_orders(db: Session, tenant_id: int, status: Optional[str] = None) -> List[WorkOrder]:
    """Get all work orders for a tenant, optionally filtered by status."""
    query = db.query(WorkOrder).filter(WorkOrder.tenant_id == tenant_id)
    if status:
        query = query.filter(WorkOrder.status == status)
    return query.all()


def run_po_expiry_alerts(db: Session, today: Optional[date] = None) -> dict:
    """Daily (scheduled job po_expiry_alerts, internal only): every ACTIVE client PO ending within
    PO_EXPIRY_ALERT_DAYS (or already past its end and still ACTIVE) gets one open Finance task, so
    it is renewed before hours stop being invoiceable (invoice_service refuses hours after a PO's
    end). Idempotent: one open task per work order."""
    from datetime import timedelta

    from app.core.config import settings
    from app.models.employee_allocation import EmployeeAllocation
    from app.models.task import Task
    from app.services.invoice_service import invoice_approvers
    from app.services.task_service import create_task

    today = today or date.today()
    horizon = today + timedelta(days=settings.PO_EXPIRY_ALERT_DAYS)
    expiring = db.query(WorkOrder).filter(WorkOrder.status == "ACTIVE", WorkOrder.end_date.isnot(None),
                                          WorkOrder.end_date <= horizon).order_by(WorkOrder.end_date).all()
    raised, failed = 0, []
    for work_order in expiring:
        title = f"PO expiring: {work_order.po_number} ends {work_order.end_date} ({work_order.id[:8]})"
        if db.query(Task.id).filter(Task.title == title, Task.status.notin_(("COMPLETED", "CANCELLED"))).first():
            continue
        try:
            client = db.get(Client, work_order.client_id)
            placements = db.query(EmployeeAllocation).filter(EmployeeAllocation.work_order_id == work_order.id,
                                                             EmployeeAllocation.status == "ACTIVE").count()
            days = (work_order.end_date - today).days
            when = f"ends in {days} day(s)" if days >= 0 else f"ended {-days} day(s) ago"
            approvers = invoice_approvers(db, work_order.tenant_id)
            assignee = approvers[0].UserID if approvers else None
            create_task(
                db, title=title, priority="HIGH" if days <= 7 else "MEDIUM", tenant_id=work_order.tenant_id,
                category="FINANCE", assigned_to_user_id=assignee,
                visibility_scope="ASSIGNEE_MANAGER_DEPARTMENT" if assignee else "ORG_WIDE",
                description=(f"{client.company_name if client else 'The client'}'s PO {work_order.po_number} "
                             f"{when} ({work_order.end_date}); {placements} active placement(s) bill against it. "
                             "Hours dated after its end date cannot be invoiced: get the extension or the new PO "
                             "from the client and update the work order (Clients > Work Orders)."),
                link="/clients")
            db.commit()
            raised += 1
        except Exception as exc:
            db.rollback()
            logger.error(f"[POExpiry] work order {work_order.id} failed: {exc}", exc_info=True)
            failed.append(work_order.id)
    logger.info(f"[POExpiry] {len(expiring)} expiring, {raised} task(s) raised, {len(failed)} failed")
    return {"expiring": len(expiring), "raised": raised, "failed": len(failed), "failed_ids": failed[:50]}

def end_work_order(db: Session, work_order: WorkOrder, end_date: Optional[date] = None) -> WorkOrder:
    """End a work order (set status to ENDED and optional end date)."""
    work_order.status = "ENDED"
    if end_date:
        if end_date < work_order.start_date:
            raise WorkOrderValidationError(f"End date {end_date} cannot be before start date {work_order.start_date}")
        work_order.end_date = end_date
    work_order.updated_at = datetime.utcnow()
    db.add(work_order)
    return work_order

def pause_work_order(db: Session, work_order: WorkOrder) -> WorkOrder:
    """Pause a work order."""
    if work_order.status == "ENDED":
        raise WorkOrderValidationError("Cannot pause an ended work order")
    work_order.status = "PAUSED"
    work_order.updated_at = datetime.utcnow()
    db.add(work_order)
    return work_order

def resume_work_order(db: Session, work_order: WorkOrder) -> WorkOrder:
    """Resume a paused work order."""
    if work_order.status != "PAUSED":
        raise WorkOrderValidationError(f"Can only resume paused work orders, this is {work_order.status}")
    work_order.status = "ACTIVE"
    work_order.updated_at = datetime.utcnow()
    db.add(work_order)
    return work_order


_UNSET = object()


def set_placement_billing(db: Session, allocation, *, approver_email=_UNSET, work_order_id=_UNSET):
    """A placement's client billing set-up: its client timesheet approver (validated against the
    client's TIMESHEET_APPROVER contacts when it has any) and the client PO it bills against (same
    tenant and client; a PO naming another employee, or an ENDED PO, is refused). Pass only what
    changes; an empty value clears it. The caller commits."""
    from app.services.client_timesheet_approval_service import ClientApprovalError, validate_approver_email

    client = db.get(Client, allocation.client_id)
    if client is None:
        raise WorkOrderValidationError(f"Allocation {allocation.id} has no client.")
    if approver_email is not _UNSET:
        try:
            allocation.timesheet_approver_email = validate_approver_email(db, client, approver_email)
        except ClientApprovalError as exc:
            raise WorkOrderValidationError(str(exc)) from exc
    if work_order_id is not _UNSET:
        if not work_order_id:
            allocation.work_order_id = None
        else:
            work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id,
                                                    WorkOrder.tenant_id == allocation.tenant_id).first()
            if work_order is None:
                raise WorkOrderValidationError(f"Work order {work_order_id} not found.")
            if work_order.client_id != allocation.client_id:
                raise WorkOrderValidationError(f"PO {work_order.po_number} belongs to a different client than this placement.")
            if work_order.employee_id and work_order.employee_id != allocation.employee_id:
                raise WorkOrderValidationError(f"PO {work_order.po_number} names a different employee.")
            if work_order.status == "ENDED":
                raise WorkOrderValidationError(f"PO {work_order.po_number} has ended; link the placement to its current PO.")
            allocation.work_order_id = work_order.id
    db.add(allocation)
    return allocation
