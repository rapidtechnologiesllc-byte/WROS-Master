"""Sub-vendor invoices and pay-when-paid (CEO 2026-11-02): Finance records a vendor's invoice against
the contractors' approved timesheets, approves it, and pays it only once the client has paid for
that work. Rules live in app.services.vendor_invoice_service; this layer maps them to HTTP."""
import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.employee import Employee
from app.models.sub_vendor import SubVendorAccount
from app.models.user import Users
from app.models.vendor_invoice import VendorInvoice
from app.schemas.vendor_invoice import (
    ContractorItem, ContractorSet, ContractorsResponse, EligibleTimesheetsResponse, SubVendorCreate, SubVendorItem,
    VendorInvoiceApprove, VendorInvoiceCreate, VendorInvoiceItem, VendorInvoiceListResponse, VendorInvoicePay,
    VendorInvoiceReject,
)
from app.services import vendor_invoice_service as service
from app.services.vendor_invoice_service import VendorInvoiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vendor-invoices", tags=["vendor-invoices"])
VIEW = [Depends(require_resource_permission("invoices", "view"))]
CREATE = [Depends(require_resource_permission("invoices", "create"))]
EDIT = [Depends(require_resource_permission("invoices", "edit"))]


def _refuse(exc: VendorInvoiceError, db: Session) -> HTTPException:
    """A broken rule is a 409 with the rule's own message; nothing half-done is kept."""
    db.rollback()
    logger.info(f"[VendorInvoice] refused: {exc}")
    return HTTPException(status_code=409, detail=str(exc))


def _invoice_or_404(db: Session, invoice_id: str, user: Users) -> VendorInvoice:
    invoice = db.query(VendorInvoice).filter(VendorInvoice.id == invoice_id,
                                             VendorInvoice.tenant_id == user.tenant_id).first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Vendor invoice not found.")
    return invoice


def _vendor_names(db: Session, tenant_id: int) -> dict:
    return dict(db.query(SubVendorAccount.id, SubVendorAccount.company_name)
                .filter(SubVendorAccount.tenant_id == tenant_id))


@router.get("/sub-vendors", response_model=List[SubVendorItem], dependencies=VIEW,
            summary="Sub-vendors of the organisation with their contractor counts")
def list_sub_vendors(db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    counts = dict(db.query(Employee.sub_vendor_id, func.count(Employee.id))
                  .filter(Employee.sub_vendor_id.isnot(None), Employee.tenant_id == user.tenant_id)
                  .group_by(Employee.sub_vendor_id))
    vendors = (db.query(SubVendorAccount).filter(SubVendorAccount.tenant_id == user.tenant_id)
               .order_by(SubVendorAccount.company_name).all())
    return [SubVendorItem(id=v.id, company_name=v.company_name, contact_email=v.contact_email, status=v.status,
                          contractors=counts.get(v.id, 0)) for v in vendors]


@router.post("/sub-vendors", response_model=SubVendorItem, status_code=201, dependencies=CREATE,
             summary="Add a sub-vendor (approved at once: Finance has vetted it)")
def add_sub_vendor(body: SubVendorCreate, db: Session = Depends(get_db),
                   user: Users = Depends(get_current_internal_user)):
    try:
        vendor = service.create_sub_vendor(db, user, company_name=body.company_name, contact_email=body.contact_email,
                                           contact_phone=body.contact_phone, tax_id=body.tax_id)
    except VendorInvoiceError as exc:
        raise _refuse(exc, db)
    db.commit()
    return SubVendorItem(id=vendor.id, company_name=vendor.company_name, contact_email=vendor.contact_email,
                         status=vendor.status)


def _contractor_item(employee: Employee, vendors: dict) -> ContractorItem:
    return ContractorItem(employee_id=employee.id, name=f"{employee.first_name} {employee.last_name}".strip(),
                          employment_type=employee.employment_type, sub_vendor_id=employee.sub_vendor_id,
                          sub_vendor_name=vendors.get(employee.sub_vendor_id),
                          hourly_rate_usd_cents=employee.vendor_hourly_rate_usd_cents)


@router.get("/contractors", response_model=ContractorsResponse, dependencies=VIEW,
            summary="Contractors supplied by sub-vendors, and the employees who could be")
def list_contractors(db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    vendors = _vendor_names(db, user.tenant_id)
    people = (db.query(Employee).filter(Employee.tenant_id == user.tenant_id, Employee.status != "EXITED")
              .order_by(Employee.first_name, Employee.last_name).all())
    return ContractorsResponse(contractors=[_contractor_item(e, vendors) for e in people if e.sub_vendor_id],
                               employees=[_contractor_item(e, vendors) for e in people if not e.sub_vendor_id])


@router.post("/contractors", response_model=ContractorItem, dependencies=EDIT,
             summary="Make an employee a contractor of a sub-vendor at an hourly vendor rate (limited access)")
def set_contractor(body: ContractorSet, db: Session = Depends(get_db),
                   user: Users = Depends(get_current_internal_user)):
    employee = db.query(Employee).filter(Employee.id == body.employee_id, Employee.tenant_id == user.tenant_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    try:
        service.set_contractor(db, user, employee, sub_vendor_id=body.sub_vendor_id,
                               hourly_rate_usd_cents=body.hourly_rate_usd_cents)
    except VendorInvoiceError as exc:
        raise _refuse(exc, db)
    db.commit()
    return _contractor_item(employee, _vendor_names(db, user.tenant_id))


@router.get("/eligible-timesheets", response_model=EligibleTimesheetsResponse, dependencies=VIEW,
            summary="Approved, not yet vendor-invoiced timesheets of a sub-vendor's contractors in a period")
def eligible_timesheets(sub_vendor_id: str = Query(...), period_start: date = Query(...),
                        period_end: date = Query(...), db: Session = Depends(get_db),
                        user: Users = Depends(get_current_internal_user)):
    if sub_vendor_id not in _vendor_names(db, user.tenant_id):
        raise HTTPException(status_code=404, detail="Sub-vendor not found.")
    try:
        rows = service.billable_timesheets(db, sub_vendor_id, period_start, period_end)
    except VendorInvoiceError as exc:
        raise _refuse(exc, db)
    return EligibleTimesheetsResponse(timesheets=rows, expected_usd_cents=sum(r["amount_usd_cents"] for r in rows))


@router.get("", response_model=VendorInvoiceListResponse, dependencies=VIEW,
            summary="Vendor invoices, with what is owed and what is payable now (the client has paid)")
def list_vendor_invoices(status: Optional[str] = None, db: Session = Depends(get_db),
                         user: Users = Depends(get_current_internal_user)):
    query = db.query(VendorInvoice).filter(VendorInvoice.tenant_id == user.tenant_id)
    if status:
        query = query.filter(VendorInvoice.status == status)
    items = [service.to_item(db, i) for i in query.order_by(VendorInvoice.invoice_date.desc()).all()]
    approved = [i for i in items if i["status"] == "APPROVED"]
    return VendorInvoiceListResponse(
        vendor_invoices=items, owed_usd_cents=sum(i["amount_usd_cents"] for i in approved),
        payable_now_usd_cents=sum(i["amount_usd_cents"] for i in approved if i["client_paid"]))


@router.post("", response_model=VendorInvoiceItem, status_code=201, dependencies=CREATE,
             summary="Record a sub-vendor's invoice against their contractors' approved timesheets")
def add_vendor_invoice(body: VendorInvoiceCreate, db: Session = Depends(get_db),
                       user: Users = Depends(get_current_internal_user)):
    try:
        invoice = service.create_vendor_invoice(db, user, **body.model_dump())
    except VendorInvoiceError as exc:
        raise _refuse(exc, db)
    db.commit()
    return service.to_item(db, invoice)


@router.post("/{invoice_id}/approve", response_model=VendorInvoiceItem, dependencies=EDIT,
             summary="Approve a received vendor invoice (a difference from hours x rate needs a note)")
def approve(invoice_id: str, body: Optional[VendorInvoiceApprove] = None, db: Session = Depends(get_db),
            user: Users = Depends(get_current_internal_user)):
    invoice = _invoice_or_404(db, invoice_id, user)
    try:
        service.approve_vendor_invoice(db, user, invoice, note=body.note if body else None)
    except VendorInvoiceError as exc:
        raise _refuse(exc, db)
    db.commit()
    return service.to_item(db, invoice)


@router.post("/{invoice_id}/reject", response_model=VendorInvoiceItem, dependencies=EDIT,
             summary="Reject a vendor invoice; its timesheets can go on a corrected one")
def reject(invoice_id: str, body: VendorInvoiceReject, db: Session = Depends(get_db),
           user: Users = Depends(get_current_internal_user)):
    invoice = _invoice_or_404(db, invoice_id, user)
    try:
        service.reject_vendor_invoice(db, user, invoice, reason=body.reason)
    except VendorInvoiceError as exc:
        raise _refuse(exc, db)
    db.commit()
    return service.to_item(db, invoice)


@router.post("/{invoice_id}/pay", response_model=VendorInvoiceItem, dependencies=EDIT,
             summary="Record the vendor payment -- refused until the client has paid for the work")
def pay(invoice_id: str, body: VendorInvoicePay, db: Session = Depends(get_db),
        user: Users = Depends(get_current_internal_user)):
    invoice = _invoice_or_404(db, invoice_id, user)
    try:
        service.pay_vendor_invoice(db, user, invoice, paid_on=body.paid_on, reference=body.reference)
    except VendorInvoiceError as exc:
        raise _refuse(exc, db)
    db.commit()
    return service.to_item(db, invoice)
