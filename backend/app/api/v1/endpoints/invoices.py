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
  POST   /invoices/{id}/send        Email the APPROVED invoice to the client's ACCOUNTS contact;
                                    it becomes SENT once the email has actually gone out.
  POST   /invoices/{id}/record-external-delivery  APPROVED -> SENT when delivered another way.
  POST   /invoices/{id}/mark-paid   SENT -> PAID, and the revenue is recognised.
  POST   /invoices/{id}/record-payment  Record the bank payment: matched transaction + PAID + revenue.
  GET    /invoices                  List (optional project_id/client_id/status filter).
  GET    /invoices/{id}             One invoice with line items.
"""
import logging
from datetime import datetime
logger = logging.getLogger(__name__)
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.project import Project
from app.models.user import Users
from app.models.invoice_delivery import InvoiceDelivery
from app.schemas.invoice import (
    GenerateInvoiceRequest,
    MarkPaidRequest,
    RecordPaymentRequest,
    RecordExternalDeliveryRequest,
    InvoiceItem,
    InvoiceLineItemItem,
    InvoiceListResponse,
)
from app.services.invoice_service import (
    AlreadyInvoiced,
    MissingBillingContact,
    NothingToInvoice,
    MissingBillRate,
    InvalidInvoiceTransition,
    OpenDisputeBlocksInvoice,
    UnapprovedTimesheetBlocksInvoice,
    approve_invoice,
    generate_invoice,
    mark_invoice_paid,
    record_external_delivery,
    request_invoice_email,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])

def _to_item(db: Session, invoice: Invoice) -> InvoiceItem:
    line_items = db.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id == invoice.id).all()
    delivery = db.query(InvoiceDelivery).filter(InvoiceDelivery.invoice_id == invoice.id).first()
    return InvoiceItem(
        delivery_channel=delivery.channel if delivery else None,
        delivery_status=delivery.status if delivery else None,
        delivery_to=delivery.to_address if delivery else None,
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

def _get_invoice_or_404(db: Session, invoice_id: str, tenant_id: Optional[int]) -> Invoice:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id).first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return invoice

@router.post(
    "/generate",
    response_model=InvoiceItem,
    summary="Generate a DRAFT invoice for a project+billing period",
    dependencies=[Depends(require_resource_permission("invoices", "create"))]
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
    except (NothingToInvoice, MissingBillRate, AlreadyInvoiced) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(invoice)

    # Queue invoice creation for FLASH orchestrator
    try:
        from app.services.message_queue_service import MessageQueueService
        MessageQueueService.enqueue(
            task_name='invoice_created_flash',
            task_id=f"invoice_created:{invoice.id}",
            data={
                'invoice_id': str(invoice.id),
                'created_at': datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.warning(f"Failed to queue invoice creation: {e}")

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
    invoice = _get_invoice_or_404(db, invoice_id, current_user.tenant_id)
    try:
        invoice = approve_invoice(db, invoice, approved_by=current_user.UserID)
    except InvalidInvoiceTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(invoice)

    # Queue invoice approval for FLASH orchestrator
    try:
        from app.services.message_queue_service import MessageQueueService
        MessageQueueService.enqueue(
            task_name='invoice_updated_flash',
            task_id=f"invoice_approved:{invoice.id}",
            data={
                'invoice_id': str(invoice.id),
                'status': 'approved',
                'updated_at': datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.warning(f"Failed to queue invoice approval: {e}")

    return _to_item(db, invoice)

@router.post(
    "/{invoice_id}/send",
    response_model=InvoiceItem,
    summary="Email an APPROVED invoice to the client's accounts contact",
    dependencies=[Depends(require_resource_permission("invoices", "create"))]
)
def send_invoice_endpoint(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    invoice = _get_invoice_or_404(db, invoice_id, current_user.tenant_id)
    try:
        request_invoice_email(db, invoice, requested_by=current_user.UserID)
    except InvalidInvoiceTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except MissingBillingContact as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        db.rollback()
        logger.error(f"[Invoices] could not queue email for {invoice_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=503, detail="The invoice email could not be queued; try again shortly.")
    db.refresh(invoice)
    return _to_item(db, invoice)

@router.post(
    "/{invoice_id}/record-external-delivery",
    response_model=InvoiceItem,
    summary="Record that an APPROVED invoice was delivered outside email (e.g. client portal)",
    dependencies=[Depends(require_resource_permission("invoices", "create"))]
)
def record_external_delivery_endpoint(
    invoice_id: str,
    body: RecordExternalDeliveryRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    invoice = _get_invoice_or_404(db, invoice_id, current_user.tenant_id)
    try:
        record_external_delivery(db, invoice, recorded_by=current_user.UserID, note=body.note)
    except InvalidInvoiceTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(invoice)
    return _to_item(db, invoice)

@router.post(
    "/{invoice_id}/mark-paid",
    response_model=InvoiceItem,
    summary="Mark a SENT invoice as PAID and recognise its revenue",
    dependencies=[Depends(require_resource_permission("invoices", "create"))]
)
def mark_invoice_paid_endpoint(
    invoice_id: str,
    body: Optional[MarkPaidRequest] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    invoice = _get_invoice_or_404(db, invoice_id, current_user.tenant_id)
    paid_on = body.paid_on if body else None
    if paid_on and paid_on > datetime.utcnow().date():
        raise HTTPException(status_code=422, detail="paid_on cannot be in the future.")
    try:
        mark_invoice_paid(db, invoice, paid_at=datetime.combine(paid_on, datetime.min.time()) if paid_on else None)
    except InvalidInvoiceTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(invoice)
    return _to_item(db, invoice)

@router.post(
    "/{invoice_id}/record-payment",
    response_model=InvoiceItem,
    summary="Record the client's payment: bank transaction matched, invoice PAID, revenue recognised",
    dependencies=[Depends(require_resource_permission("invoices", "create"))]
)
def record_payment_endpoint(
    invoice_id: str,
    body: RecordPaymentRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.bank_reconciliation_service import BankReconciliationError, record_invoice_payment

    invoice = _get_invoice_or_404(db, invoice_id, current_user.tenant_id)
    if body.paid_on > datetime.utcnow().date():
        raise HTTPException(status_code=422, detail="paid_on cannot be in the future.")
    try:
        record_invoice_payment(db, invoice, paid_on=body.paid_on, amount_usd_cents=body.amount_usd_cents,
                               reference=body.reference, recorded_by=current_user.UserID)
    except BankReconciliationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
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
    invoice = _get_invoice_or_404(db, invoice_id, current_user.tenant_id)
    return _to_item(db, invoice)

