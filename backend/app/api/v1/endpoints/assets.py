"""
Asset Ledger -- API
=========================================================================
Prefix: /assets
Tag:    assets

Every device the organisation holds or is responsible for (CEO 2026-11-10), owned by the IT Admin
function (app.services.asset_service). Business rules live in the service; a refused change is a 400
with the reason in plain words.

Auth: the "assets" resource (Admin & Settings) for the ledger. Three actions are also open to the
employee who holds the item, on their own items only: confirm it arrived, enter the courier details of a
return, report a defect. A person's Assets tab is open to them, to whoever may see the employee, and to
the ledger's users.

Routes:
  GET   /assets/options                         lists for the forms (categories, owners, companies, clients)
  GET   /assets                                 the ledger (filters) with its summary
  GET   /assets/alerts                          everything that needs someone, most serious first
  POST  /assets                                 register an item
  GET   /assets/employee/{employee_id}          one person's assets, returns due, kit gaps, settlement hold
  POST  /assets/employee/{employee_id}/clearance/sign-off
  GET   /assets/project/{project_id}/requirements
  PUT   /assets/project/{project_id}/requirements
  POST  /assets/issues/{issue_id}               start repair / fixed / no fault / retire
  GET   /assets/{asset_id}                      the item with its history, shipments and defects
  PATCH /assets/{asset_id}
  POST  /assets/{asset_id}/issue-to-employee
  POST  /assets/{asset_id}/confirm-receipt      (IT Admin or the holder)
  POST  /assets/{asset_id}/request-return
  POST  /assets/{asset_id}/return-shipment      (IT Admin or the holder)
  POST  /assets/{asset_id}/receive-return       IT Admin signs the return off
  POST  /assets/{asset_id}/return-to-owner
  POST  /assets/{asset_id}/owner-received
  POST  /assets/{asset_id}/issues               (IT Admin or the holder)
  POST  /assets/{asset_id}/lost
  POST  /assets/{asset_id}/retire
"""
import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import authority
from app.core.data_scope import bu_filter
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.asset import (
    ASSET_CATEGORIES, ASSET_CONDITIONS, ASSET_STATUSES, HANDOVER_METHODS, ISSUE_SEVERITIES, OWNER_TYPES,
    RETURN_REASONS, Asset, AssetIssue,
)
from app.models.client import Client
from app.models.employee import Employee
from app.models.location import Location
from app.models.project import Project
from app.models.user import Users
from app.services import asset_service as service
from app.services.asset_service import AssetRefused

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assets", tags=["assets"])

VIEW = [Depends(require_resource_permission("assets", "view"))]
CREATE = [Depends(require_resource_permission("assets", "create"))]
EDIT = [Depends(require_resource_permission("assets", "edit"))]
# Everyone with a login has My Tasks: the holder's own actions are checked against the item itself
SIGNED_IN = [Depends(require_resource_permission("my-tasks", "view"))]


# --------------------------------------------------------------------------- requests

class AssetCreate(BaseModel):
    category: str
    owner_type: str
    owner_company_id: Optional[str] = None
    owner_client_id: Optional[str] = None
    owner_name: Optional[str] = Field(None, max_length=300)
    make: Optional[str] = Field(None, max_length=200)
    model: Optional[str] = Field(None, max_length=200)
    serial_number: Optional[str] = Field(None, max_length=200)
    asset_tag: Optional[str] = Field(None, max_length=64)
    condition: str = "GOOD"
    purchase_date: Optional[date] = None
    purchase_cost_cents: Optional[int] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=3)
    warranty_until: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=4000)
    employee_id: Optional[str] = None  # an employee's own device: who it belongs to


class AssetUpdate(BaseModel):
    category: Optional[str] = None
    owner_type: Optional[str] = None
    owner_company_id: Optional[str] = None
    owner_client_id: Optional[str] = None
    owner_name: Optional[str] = Field(None, max_length=300)
    make: Optional[str] = Field(None, max_length=200)
    model: Optional[str] = Field(None, max_length=200)
    serial_number: Optional[str] = Field(None, max_length=200)
    condition: Optional[str] = None
    purchase_date: Optional[date] = None
    purchase_cost_cents: Optional[int] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=3)
    warranty_until: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=4000)


class IssueToEmployee(BaseModel):
    employee_id: str
    method: str  # COURIER | HAND
    carrier: Optional[str] = Field(None, max_length=200)
    tracking_number: Optional[str] = Field(None, max_length=200)
    shipped_on: Optional[date] = None
    expected_on: Optional[date] = None
    project_id: Optional[str] = None
    return_at_project_end: Optional[bool] = None


class ReceiptConfirm(BaseModel):
    received_on: Optional[date] = None
    note: Optional[str] = Field(None, max_length=2000)


class ReturnRequest(BaseModel):
    due_date: date
    reason: str = "RECALL"
    note: Optional[str] = Field(None, max_length=2000)


class ReturnShipment(BaseModel):
    carrier: str = Field(..., min_length=1, max_length=200)
    tracking_number: str = Field(..., min_length=1, max_length=200)
    shipped_on: Optional[date] = None
    expected_on: Optional[date] = None


class ReturnReceive(BaseModel):
    condition: str
    received_on: Optional[date] = None
    note: Optional[str] = Field(None, max_length=2000)


class ReturnToOwner(BaseModel):
    method: str
    carrier: Optional[str] = Field(None, max_length=200)
    tracking_number: Optional[str] = Field(None, max_length=200)
    shipped_on: Optional[date] = None
    note: Optional[str] = Field(None, max_length=2000)


class DefectReport(BaseModel):
    description: str = Field(..., min_length=1, max_length=4000)
    severity: str = "MEDIUM"


class DefectUpdate(BaseModel):
    action: str  # START_REPAIR | FIXED | NO_FAULT | RETIRE
    resolution: Optional[str] = Field(None, max_length=4000)
    repair_vendor: Optional[str] = Field(None, max_length=300)
    fix_cost_cents: Optional[int] = Field(None, ge=0)


class Reason(BaseModel):
    note: str = Field(..., min_length=1, max_length=2000)


class ClearanceSignOff(BaseModel):
    note: Optional[str] = Field(None, max_length=2000)


class KitItem(BaseModel):
    category: str
    provided_by: str = "COMPANY"
    quantity: int = Field(1, ge=1, le=20)
    note: Optional[str] = Field(None, max_length=500)


class KitUpdate(BaseModel):
    items: List[KitItem]


# --------------------------------------------------------------------------- helpers

def _asset_or_404(db: Session, asset_id: str, user: Users) -> Asset:
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.tenant_id == user.tenant_id).first()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return asset


def _my_employee_id(db: Session, user: Users) -> Optional[str]:
    return db.query(Employee.id).filter(Employee.wros_user_id == user.UserID,
                                        Employee.tenant_id == user.tenant_id).scalar()


def _manager_or_holder(db: Session, asset: Asset, user: Users) -> None:
    """IT Admin (assets.edit), or the employee who holds this item. Anyone else gets the same 404 as
    for an item that does not exist."""
    if authority.has_permission(db, user, "assets.edit"):
        return
    mine = _my_employee_id(db, user)
    if not mine or asset.holder_employee_id != mine:
        raise HTTPException(status_code=404, detail="Asset not found.")


def _employee_or_404(db: Session, employee_id: str, user: Users) -> Employee:
    """The ledger's users see anyone in the organisation; whoever may see employees sees those in
    their business-unit scope; everyone sees themselves."""
    query = db.query(Employee).filter(Employee.id == employee_id, Employee.tenant_id == user.tenant_id)
    if authority.has_permission(db, user, "assets.view"):
        employee = query.first()
    elif authority.has_permission(db, user, "employees.view"):
        employee = query.filter(bu_filter(db, user, Employee.bu_id)).first()
    else:
        employee = query.filter(Employee.wros_user_id == user.UserID).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    return employee


def _done(db: Session, asset: Asset) -> dict:
    """Save, announce (tasks and reminders), and answer with the item as it now stands."""
    db.commit()
    db.refresh(asset)
    service.send_notices(db)
    return service.asset_detail(db, asset)


def _refused(db: Session, exc: AssetRefused) -> HTTPException:
    """Nothing is committed: the request's session is discarded, and nothing it noted is announced."""
    db.info["asset_notices"] = []
    return HTTPException(status_code=400, detail=str(exc))


# --------------------------------------------------------------------------- the ledger

@router.get("/options", dependencies=VIEW)
def asset_options(db: Session = Depends(get_db), current_user: Users = Depends(get_current_internal_user)):
    """The lists the forms offer: nothing is typed into the screen."""
    companies = db.query(Location).filter(Location.tenant_id == current_user.tenant_id).order_by(Location.name).all()
    clients = db.query(Client).filter(Client.tenant_id == current_user.tenant_id).order_by(Client.company_name).all()
    employees = db.query(Employee).filter(Employee.tenant_id == current_user.tenant_id,
                                          Employee.status.notin_(service.LEAVING_STATUSES)) \
        .order_by(Employee.first_name, Employee.last_name).all()
    projects = db.query(Project).filter(Project.tenant_id == current_user.tenant_id).order_by(Project.name).all()
    return {
        "categories": list(ASSET_CATEGORIES), "owner_types": list(OWNER_TYPES), "statuses": list(ASSET_STATUSES),
        "conditions": list(ASSET_CONDITIONS), "handover_methods": list(HANDOVER_METHODS),
        "severities": list(ISSUE_SEVERITIES), "return_reasons": [r for r in RETURN_REASONS if r != "EXIT"],
        "kit_providers": ["COMPANY", "CLIENT"],
        "companies": [{"id": c.id, "name": c.name} for c in companies],
        "clients": [{"id": c.id, "name": c.company_name} for c in clients],
        "employees": [{"id": e.id, "name": service.employee_name(e)} for e in employees],
        "projects": [{"id": p.id, "name": p.name, "client_id": p.client_id} for p in projects],
        "owner_function": service.settings.ASSET_OWNER_FUNCTION,
        "can_create": authority.has_permission(db, current_user, "assets.create"),
        "can_edit": authority.has_permission(db, current_user, "assets.edit"),
    }


@router.get("", dependencies=VIEW)
def list_ledger(status: Optional[str] = None, owner_type: Optional[str] = None, category: Optional[str] = None,
                search: Optional[str] = None, employee_id: Optional[str] = None,
                db: Session = Depends(get_db), current_user: Users = Depends(get_current_internal_user)):
    for value, allowed, name in ((status, ASSET_STATUSES, "status"), (owner_type, OWNER_TYPES, "owner_type"),
                                 (category, ASSET_CATEGORIES, "category")):
        if value and value not in allowed:
            raise HTTPException(status_code=400, detail=f"Unknown {name} {value!r}.")
    return {"summary": service.ledger_summary(db, current_user.tenant_id),
            "assets": service.list_assets(db, current_user.tenant_id, status=status, owner_type=owner_type,
                                          category=category, search=search, employee_id=employee_id)}


@router.get("/alerts", dependencies=VIEW)
def ledger_alerts(db: Session = Depends(get_db), current_user: Users = Depends(get_current_internal_user)):
    return {"alerts": service.ledger_alerts(db, current_user.tenant_id)}


@router.post("", dependencies=CREATE)
def register_asset(body: AssetCreate, db: Session = Depends(get_db),
                   current_user: Users = Depends(get_current_internal_user)):
    try:
        asset = service.register_asset(db, current_user.tenant_id, current_user, **body.model_dump())
    except AssetRefused as exc:
        raise _refused(db, exc)
    logger.info(f"[Assets] {asset.asset_tag} registered by {current_user.UserID}")
    return _done(db, asset)


# --------------------------------------------------------------------------- one person

@router.get("/employee/{employee_id}", dependencies=SIGNED_IN)
def employee_assets(employee_id: str, db: Session = Depends(get_db),
                    current_user: Users = Depends(get_current_internal_user)):
    employee = _employee_or_404(db, employee_id, current_user)
    result = service.employee_assets(db, employee)
    result["is_self"] = bool(employee.wros_user_id) and employee.wros_user_id == current_user.UserID
    result["can_manage"] = authority.has_permission(db, current_user, "assets.edit")
    return result


@router.post("/employee/{employee_id}/clearance/sign-off", dependencies=EDIT)
def sign_off_clearance(employee_id: str, body: ClearanceSignOff, db: Session = Depends(get_db),
                       current_user: Users = Depends(get_current_internal_user)):
    """IT Admin confirms everything is back: releases full and final settlement."""
    employee = _employee_or_404(db, employee_id, current_user)
    try:
        service.sign_off_clearance(db, employee, current_user, note=body.note)
    except AssetRefused as exc:
        raise _refused(db, exc)
    db.commit()
    service.send_notices(db)
    logger.info(f"[Assets] clearance for {employee.id} signed off by {current_user.UserID}")
    return service.employee_assets(db, employee)


# --------------------------------------------------------------------------- a project's kit

def _project_or_404(db: Session, project_id: str, user: Users) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == user.tenant_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def _kit(db: Session, project: Project) -> dict:
    return {"project_id": project.id, "project_name": project.name,
            "items": [{"category": r.category, "provided_by": r.provided_by, "quantity": r.quantity, "note": r.note}
                      for r in service.project_requirements(db, project.id)]}


@router.get("/project/{project_id}/requirements", dependencies=VIEW)
def get_project_kit(project_id: str, db: Session = Depends(get_db),
                    current_user: Users = Depends(get_current_internal_user)):
    return _kit(db, _project_or_404(db, project_id, current_user))


@router.put("/project/{project_id}/requirements", dependencies=EDIT)
def set_project_kit(project_id: str, body: KitUpdate, db: Session = Depends(get_db),
                    current_user: Users = Depends(get_current_internal_user)):
    """The kit each person on the project must hold; everyone on it is checked again at once."""
    project = _project_or_404(db, project_id, current_user)
    try:
        service.set_project_requirements(db, project, current_user, [item.model_dump() for item in body.items])
    except AssetRefused as exc:
        raise _refused(db, exc)
    db.commit()
    service.send_notices(db)
    return _kit(db, project)


# --------------------------------------------------------------------------- defects

@router.post("/issues/{issue_id}", dependencies=EDIT)
def update_defect(issue_id: str, body: DefectUpdate, db: Session = Depends(get_db),
                  current_user: Users = Depends(get_current_internal_user)):
    issue = db.query(AssetIssue).filter(AssetIssue.id == issue_id, AssetIssue.tenant_id == current_user.tenant_id).first()
    if issue is None:
        raise HTTPException(status_code=404, detail="Defect not found.")
    asset = _asset_or_404(db, issue.asset_id, current_user)
    try:
        service.update_issue(db, issue, current_user, **body.model_dump())
    except AssetRefused as exc:
        raise _refused(db, exc)
    return _done(db, asset)


# --------------------------------------------------------------------------- one item

@router.get("/{asset_id}", dependencies=VIEW)
def get_asset(asset_id: str, db: Session = Depends(get_db), current_user: Users = Depends(get_current_internal_user)):
    return service.asset_detail(db, _asset_or_404(db, asset_id, current_user))


@router.patch("/{asset_id}", dependencies=EDIT)
def update_asset(asset_id: str, body: AssetUpdate, db: Session = Depends(get_db),
                 current_user: Users = Depends(get_current_internal_user)):
    asset = _asset_or_404(db, asset_id, current_user)
    try:
        service.update_asset(db, asset, current_user, body.model_dump(exclude_unset=True))
    except AssetRefused as exc:
        raise _refused(db, exc)
    return _done(db, asset)


@router.post("/{asset_id}/issue-to-employee", dependencies=EDIT)
def issue_to_employee(asset_id: str, body: IssueToEmployee, db: Session = Depends(get_db),
                      current_user: Users = Depends(get_current_internal_user)):
    asset = _asset_or_404(db, asset_id, current_user)
    employee = db.query(Employee).filter(Employee.id == body.employee_id,
                                         Employee.tenant_id == current_user.tenant_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    try:
        service.issue_asset(db, asset, employee, current_user, **body.model_dump(exclude={"employee_id"}))
    except AssetRefused as exc:
        raise _refused(db, exc)
    logger.info(f"[Assets] {asset.asset_tag} issued to {employee.id} by {current_user.UserID}")
    return _done(db, asset)


@router.post("/{asset_id}/confirm-receipt", dependencies=SIGNED_IN)
def confirm_receipt(asset_id: str, body: ReceiptConfirm, db: Session = Depends(get_db),
                    current_user: Users = Depends(get_current_internal_user)):
    asset = _asset_or_404(db, asset_id, current_user)
    _manager_or_holder(db, asset, current_user)
    try:
        service.confirm_receipt(db, asset, current_user, received_on=body.received_on, note=body.note)
    except AssetRefused as exc:
        raise _refused(db, exc)
    return _done(db, asset)


@router.post("/{asset_id}/request-return", dependencies=EDIT)
def request_return(asset_id: str, body: ReturnRequest, db: Session = Depends(get_db),
                   current_user: Users = Depends(get_current_internal_user)):
    asset = _asset_or_404(db, asset_id, current_user)
    try:
        service.request_return(db, asset, reason=body.reason, due_date=body.due_date, note=body.note,
                               actor=current_user.UserID)
    except AssetRefused as exc:
        raise _refused(db, exc)
    return _done(db, asset)


@router.post("/{asset_id}/return-shipment", dependencies=SIGNED_IN)
def return_shipment(asset_id: str, body: ReturnShipment, db: Session = Depends(get_db),
                    current_user: Users = Depends(get_current_internal_user)):
    """The courier and tracking number of an item on its way back."""
    asset = _asset_or_404(db, asset_id, current_user)
    _manager_or_holder(db, asset, current_user)
    try:
        service.record_return_shipment(db, asset, current_user, **body.model_dump())
    except AssetRefused as exc:
        raise _refused(db, exc)
    return _done(db, asset)


@router.post("/{asset_id}/receive-return", dependencies=EDIT)
def receive_return(asset_id: str, body: ReturnReceive, db: Session = Depends(get_db),
                   current_user: Users = Depends(get_current_internal_user)):
    """IT Admin has the item back, records its condition and signs the return off."""
    asset = _asset_or_404(db, asset_id, current_user)
    try:
        service.receive_return(db, asset, current_user, **body.model_dump())
    except AssetRefused as exc:
        raise _refused(db, exc)
    logger.info(f"[Assets] {asset.asset_tag} return signed off by {current_user.UserID}")
    return _done(db, asset)


@router.post("/{asset_id}/return-to-owner", dependencies=EDIT)
def return_to_owner(asset_id: str, body: ReturnToOwner, db: Session = Depends(get_db),
                    current_user: Users = Depends(get_current_internal_user)):
    asset = _asset_or_404(db, asset_id, current_user)
    try:
        service.return_to_owner(db, asset, current_user, **body.model_dump())
    except AssetRefused as exc:
        raise _refused(db, exc)
    return _done(db, asset)


@router.post("/{asset_id}/owner-received", dependencies=EDIT)
def owner_received(asset_id: str, body: ReceiptConfirm, db: Session = Depends(get_db),
                   current_user: Users = Depends(get_current_internal_user)):
    asset = _asset_or_404(db, asset_id, current_user)
    try:
        service.confirm_owner_received(db, asset, current_user, received_on=body.received_on)
    except AssetRefused as exc:
        raise _refused(db, exc)
    return _done(db, asset)


@router.post("/{asset_id}/issues", dependencies=SIGNED_IN)
def report_defect(asset_id: str, body: DefectReport, db: Session = Depends(get_db),
                  current_user: Users = Depends(get_current_internal_user)):
    asset = _asset_or_404(db, asset_id, current_user)
    _manager_or_holder(db, asset, current_user)
    try:
        service.report_issue(db, asset, current_user, description=body.description, severity=body.severity)
    except AssetRefused as exc:
        raise _refused(db, exc)
    return _done(db, asset)


@router.post("/{asset_id}/lost", dependencies=EDIT)
def mark_lost(asset_id: str, body: Reason, db: Session = Depends(get_db),
              current_user: Users = Depends(get_current_internal_user)):
    asset = _asset_or_404(db, asset_id, current_user)
    try:
        service.mark_lost(db, asset, current_user, note=body.note)
    except AssetRefused as exc:
        raise _refused(db, exc)
    logger.warning(f"[Assets] {asset.asset_tag} marked lost by {current_user.UserID}")
    return _done(db, asset)


@router.post("/{asset_id}/retire", dependencies=EDIT)
def retire_asset(asset_id: str, body: Reason, db: Session = Depends(get_db),
                 current_user: Users = Depends(get_current_internal_user)):
    asset = _asset_or_404(db, asset_id, current_user)
    try:
        service.retire_asset(db, asset, current_user, reason=body.note)
    except AssetRefused as exc:
        raise _refused(db, exc)
    return _done(db, asset)
