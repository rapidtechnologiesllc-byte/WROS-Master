"""
HRMS-0907 -- Invoice Generation, Status Tracking -- API Endpoints
=========================================================================
Prefix: /invoices
import logging
Tag:    invoices

Wires app.services.invoice_service (real, tested backend, pre-existing
this codebase) to real HTTP routes. No REST layer previously existed.
R-10 ("unapproved timesheet blocks invoice generation") and HRMS-0904's
BR-02 (an open dispute blocks the period) are enforced entirely inside
generate_invoice() itself -- this file only maps its exceptions to
HTTP status codes, it invents no new business rules.

"Sent" and "Paid" are always explicit human actions per invoice_
service.py's own docstring (no automatic sending/reconciliation exists
in this codebase) -- separate endpoints for each transition, not
folded into approve.

Auth: get_current_internal_user, same posture as every endpoint this
program. No dedicated "Finance" role exists in this codebase's RBAC
(app/services/rbac_service.py) despite HRMS-0907 BR-0907-02 saying
approval is "always a Finance-role action" -- flagged, not guessed at,
same posture as every other RM/Finance role gap this session.

Routes:
  POST   /invoices/generate         Generate a DRAFT invoice for a project+period.
  POST   /invoices/{id}/approve     DRAFT -> APPROVED.
  POST   /invoices/{id}/send        APPROVED -> SENT.
  POST   /invoices/{id}/mark-paid   SENT -> PAID.
  GET    /invoices                  List (optional project_id/client_id/status filter).
  GET    /invoices/{id}             One invoice with line items.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.project import Project
from app.models.user import Users
from app.schemas.invoice import (
    GenerateInvoiceRequest,
    InvoiceItem,
    InvoiceLineItemItem,
    InvoiceListResponse,
)
from app.services.invoice_service import (
    InvalidInvoiceTransition,
    OpenDisputeBlocksInvoice,
    UnapprovedTimesheetBlocksInvoice,
    approve_invoice,
    generate_invoice,
    mark_invoice_paid,
    send_invoice,
)
from app.services.ar_followup_service import scan_overdue_invoices, trigger_ar_follow_up

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _to_item(db: Session, invoice: Invoice) -> InvoiceItem:
    line_items = db.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id == invoice.id).all()
    return InvoiceItem(
        id=invoice.id, project_id=invoice.project_id, client_id=invoice.client_id,
        billing_period_start=invoice.billing_period_start, billing_period_end=invoice.billing_period_end,
        status=invoice.status, total_usd_cents=invoice.total_usd_cents, currency=invoice.currency,
        approved_by=invoice.approved_by, approved_at=invoice.approved_at,
        sent_at=invoice.sent_at, paid_at=invoice.paid_at,
        line_items=[
            InvoiceLineItemItem(
                id=li.id, employee_id=li.employee_id, timesheet_id=li.timesheet_id,
                hours=float(li.hours), rate_usd_cents=li.rate_usd_cents, amount_usd_cents=li.amount_usd_cents,
            )
            for li in line_items
        ],
    )


def _get_invoice_or_404(db: Session, invoice_id: str) -> Invoice:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return invoice


@router.post(
    "/generate",
    response_model=InvoiceItem,
    summary="Generate a DRAFT invoice for a project+billing period",
    dependencies=[Depends(require_resource_permission("generate", "create"))]
)
def generate_invoice_endpoint(
    body: GenerateInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    project = db.query(Project).filter(Project.id == body.project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        invoice = generate_invoice(
            db, project, period_start=body.period_start, period_end=body.period_end,
            tenant_id=current_user.tenant_id,
        )
    except UnapprovedTimesheetBlocksInvoice as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except OpenDisputeBlocksInvoice as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(invoice)
    return _to_item(db, invoice)


@router.post(
    "/{invoice_id}/approve",
    response_model=InvoiceItem,
    summary="Approve a DRAFT invoice",
    dependencies=[Depends(require_resource_permission("invoices", "create"))]
)
def approve_invoice_endpoint(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    invoice = _get_invoice_or_404(db, invoice_id)
    try:
        invoice = approve_invoice(db, invoice, approved_by=current_user.UserID)
    except InvalidInvoiceTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(invoice)
    return _to_item(db, invoice)


@router.post(
    "/{invoice_id}/send",
    response_model=InvoiceItem,
    summary="Mark an APPROVED invoice as SENT",
    dependencies=[Depends(require_resource_permission("invoices", "create"))]
)
def send_invoice_endpoint(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    invoice = _get_invoice_or_404(db, invoice_id)
    try:
        invoice = send_invoice(db, invoice)
    except InvalidInvoiceTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(invoice)
    return _to_item(db, invoice)


@router.post(
    "/{invoice_id}/mark-paid",
    response_model=InvoiceItem,
    summary="Mark a SENT invoice as PAID",
    dependencies=[Depends(require_resource_permission("invoices", "create"))]
)
def mark_invoice_paid_endpoint(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    invoice = _get_invoice_or_404(db, invoice_id)
    try:
        invoice = mark_invoice_paid(db, invoice)
    except InvalidInvoiceTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(invoice)
    return _to_item(db, invoice)


@router.get(
    "",
    response_model=InvoiceListResponse,
    summary="List invoices",
    dependencies=[Depends(require_resource_permission("invoices", "view"))]
)
def list_invoices(
    project_id: Optional[str] = None,
    client_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    query = db.query(Invoice).filter(Invoice.tenant_id == current_user.tenant_id)
    if project_id:
        query = query.filter(Invoice.project_id == project_id)
    if client_id:
        query = query.filter(Invoice.client_id == client_id)
    if status:
        query = query.filter(Invoice.status == status)
    invoices = query.order_by(Invoice.created_at.desc()).all()
    return InvoiceListResponse(invoices=[_to_item(db, i) for i in invoices])


@router.get(
    "/{invoice_id}",
    response_model=InvoiceItem,
    summary="Get one invoice with line items",
    dependencies=[Depends(require_resource_permission("invoices", "view"))]
)
def get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    invoice = _get_invoice_or_404(db, invoice_id)
    return _to_item(db, invoice)


@router.get(
    "/ar/aging",
    summary="EPIC-16 AR Follow-Up: overdue SENT invoices",
    dependencies=[Depends(require_resource_permission("ar", "view"))]
)
def ar_aging(
    grace_days: int = 30,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    return {"overdue": scan_overdue_invoices(db, grace_days=grace_days, tenant_id=current_user.tenant_id)}


@router.post(
    "/{invoice_id}/ar/follow-up",
    summary="EPIC-16 AR Follow-Up: create/return the follow-up Task for this invoice",
    dependencies=[Depends(require_resource_permission("invoices", "create"))]
)
def ar_follow_up(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    invoice = _get_invoice_or_404(db, invoice_id)
    task = trigger_ar_follow_up(db, invoice)
    return {"task_id": task.id, "title": task.title, "assigned_to_user_id": task.assigned_to_user_id}
