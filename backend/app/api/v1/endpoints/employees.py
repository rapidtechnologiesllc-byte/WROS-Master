"""
S-245 (Create Employee Profile) + S-246 (Mark Employee as Bench) +
S-247 (View Bench Pool) + S-248 (Bench Duration & Aging Report) — API
Endpoints
=========================================================================
Prefix: /employees
Tag:    employees

No employee REST API of any kind previously existed in this codebase
despite the Employee model, bench_pool lifecycle, and bench_periods
history all being real, tested backend (this and earlier Phase 4
rounds). This closes that gap for the foundational pieces four stories
in the EPIC-05/Resource & Bench Management cluster need.

Auth: the role template's employees permission decides the actions; the
business unit decides the records (CEO 2026-10-12, app.core.data_scope):
an employee belongs to Employee.bu_id. Out-of-scope ids are 404, moving an
employee into a BU outside the caller's scope is 403.

Routes (static paths registered before the /{employee_id} catch-all,
so "bench-pool"/"bench-aging-alerts" never get swallowed as an id):
  POST   /employees
  GET    /employees
  GET    /employees/bench-pool
  GET    /employees/bench-aging-alerts
  GET    /employees/{employee_id}
  POST   /employees/{employee_id}/mark-bench
  POST   /employees/{employee_id}/remove-from-bench
  GET    /employees/{employee_id}/bench-history
  GET    /employees/{employee_id}/escalations
  POST   /employees/{employee_id}/escalations
  POST   /employees/escalations/{escalation_id}/resolve   (Director and above)
"""
import json
from datetime import date, datetime

from typing import Optional

from pydantic import BaseModel
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from app.core.config import settings
from sqlalchemy.orm import Session

from app.core.data_scope import bu_filter, ensure_assignable
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.employee import Employee
from app.models.employee_escalation import EmployeeEscalation
from app.models.resource_management import BenchPoolEntry
from app.models.user import Users
from app.core.logging import logger
from app.schemas.employee import (
    BenchCostSummaryItem,
    BenchCostSummaryResponse,
    EmployeeCreateRequest,
    EmployeeItem,
    EmployeeListResponse,
    EscalationCreateRequest,
    EscalationItem,
    EscalationListResponse,
    EscalationResolveRequest,
    MarkBenchRequest,
    RecomputeUtilizationResponse,
    UtilizationSummaryItem,
    UtilizationSummaryResponse,
)
from app.services.resource_management_service import (
    get_bench_duration_days,
    get_current_bench_pool,
    get_latest_utilization_by_employee,
    mark_employee_on_bench,
    remove_employee_from_bench,
    snapshot_utilization,
    utilization_population,
)

from app.services.employee_profile_service import can_edit_compensation, can_see_compensation
from app.services.employee_standing import deployment_status, employment_actions, employment_status, in_htd

router = APIRouter(prefix="/employees", tags=["employees"])

def _skills_list(raw, employee_id: str = None):
    from app.services.employee_service import skills_list

    return skills_list(raw, employee_id)


def _allocation_summaries(db: Session, employee_ids) -> dict:
    """{employee_id: [ACTIVE allocation summaries]} in three queries for any number of people."""
    from app.models.client import Client
    from app.models.demand import Demand
    from app.models.employee_allocation import EmployeeAllocation

    ids = list(employee_ids)
    if not ids:
        return {}
    rows = db.query(EmployeeAllocation).filter(EmployeeAllocation.employee_id.in_(ids),
                                               EmployeeAllocation.status == "ACTIVE").all()
    clients = {c.id: c.company_name for c in db.query(Client).filter(Client.id.in_({r.client_id for r in rows}))} if rows else {}
    jobs = {j.jobID: j.jobTitle for j in db.query(Demand).filter(Demand.jobID.in_({r.demand_id for r in rows}))} if rows else {}
    out = {}
    for r in rows:
        out.setdefault(r.employee_id, []).append({
            "allocation_id": r.id, "client_name": clients.get(r.client_id), "job_title": jobs.get(r.demand_id),
            "utilization_pct": float(r.utilization_pct) if r.utilization_pct is not None else 100.0,
            "start_date": r.start_date.isoformat() if r.start_date else None,
            "end_date": r.end_date.isoformat() if r.end_date else None,
            "renewal_status": r.renewal_status,
        })
    return out


def _managers(db: Session, employees) -> dict:
    """{reporting_manager_user_id: (name, that manager's employee id)} for these employees, in two
    queries. The row mirrors the org chart (org_structure_service._sync_employee_reporting)."""
    ids = {e.reporting_manager_user_id for e in employees if e.reporting_manager_user_id}
    if not ids:
        return {}
    names = {u.UserID: u.UserName or u.UserEmail for u in db.query(Users).filter(Users.UserID.in_(ids))}
    rows = {e.wros_user_id: e.id for e in db.query(Employee.wros_user_id, Employee.id).filter(Employee.wros_user_id.in_(ids))}
    return {uid: (names.get(uid), rows.get(uid)) for uid in ids}


def _to_item(db: Session, employee: Employee, *, bench_entry=..., allocations=None,
             guidewire_level=..., viewer: Optional[Users] = None, sees_money: Optional[bool] = None,
             managers: Optional[dict] = None) -> EmployeeItem:
    """viewer decides what money shows: salary only with finance-operations.view (the
    fully-loaded-cost rule); without a viewer it is never sent."""
    from app.services.employee_certification_service import current_guidewire_levels

    if guidewire_level is ...:
        guidewire_level = current_guidewire_levels(db, [employee.id]).get(employee.id)
    if bench_entry is ...:
        bench_entry = db.query(BenchPoolEntry).filter(BenchPoolEntry.employee_id == employee.id).first()
    if allocations is None:
        allocations = _allocation_summaries(db, [employee.id]).get(employee.id, [])
    if sees_money is None:
        sees_money = viewer is not None and can_see_compensation(db, viewer)
    if managers is None:
        managers = _managers(db, [employee])
    manager_name, manager_employee_id = managers.get(employee.reporting_manager_user_id, (None, None))
    bench_days = get_bench_duration_days(bench_entry) if bench_entry else None
    deployment = deployment_status(employee.status, employee.buddy_program_status, allocations, bench_days,
                                   date.today(), htd_active=in_htd(employee.htd_track, employee.htd_phase))
    return EmployeeItem(
        id=employee.id,
        employee_number=employee.employee_number,
        first_name=employee.first_name,
        last_name=employee.last_name,
        email=employee.email,
        status=employee.status,
        employment_type=employee.employment_type,
        current_title=employee.current_title,
        current_skills=_skills_list(employee.current_skills, employee.id),
        work_location=employee.work_location,
        delivery_engine=employee.delivery_engine,
        engine_entry_date=employee.engine_entry_date,
        core_certified=employee.core_certified,
        core_certified_date=employee.core_certified_date,
        joining_date=employee.joining_date,
        exit_date=employee.exit_date,
        base_salary_usd_cents=employee.base_salary_usd_cents if sees_money else None,
        billing_rate_usd_cents=employee.billing_rate_usd_cents,
        is_on_bench=bench_entry is not None,
        bench_days=bench_days,
        employment_status=employment_status(employee.status),
        employment_actions=employment_actions(employee.status),
        deployment_status=deployment["status"],
        deployment_until=deployment["until"],
        deployment_days=deployment["days"],
        # derived from the certificates held (employee_certification_service), never typed
        guidewire_certification_current=guidewire_level,
        guidewire_certification_expected=employee.guidewire_certification_expected,
        bu_id=employee.bu_id,
        company_id=employee.company_id,
        is_billable=bool(employee.is_billable),
        buddy_program_status=employee.buddy_program_status,
        htd_track=bool(employee.htd_track),
        htd_phase=employee.htd_phase,
        htd_start_date=employee.htd_start_date,
        htd_end_date=employee.htd_end_date,
        has_login=employee.wros_user_id is not None,
        has_photo=bool(employee.photo_path),
        has_cover=bool(employee.cover_path),
        reporting_manager_user_id=employee.reporting_manager_user_id,
        reporting_manager_name=manager_name,
        reporting_manager_employee_id=manager_employee_id,
        active_allocations=allocations,
        allocated_pct=sum(a["utilization_pct"] for a in allocations),
    )

def _visible_employees(db: Session, user: Users):
    """This tenant's employees inside the caller's business-unit scope (app.core.data_scope)."""
    return db.query(Employee).filter(Employee.tenant_id == user.tenant_id, bu_filter(db, user, Employee.bu_id))


def _get_employee_or_404(db: Session, employee_id: str, user: Users) -> Employee:
    """One employee of the caller's tenant and business-unit scope; any other id is 404, the
    same answer as an id that does not exist."""
    employee = _visible_employees(db, user).filter(Employee.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    return employee

@router.post(
    "",
    response_model=EmployeeItem,
    summary="Add one employee (the import path with one row: login, scope, bench or allocation, activation email)",
    dependencies=[Depends(require_resource_permission("employees", "create"))]
)
def create_employee(
    body: EmployeeCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """One employee through employee_import_service, the only creation path: the same
    resolution, gates, login linking and activation email as a bulk import row."""
    from app.services.employee_import_service import ImportFileError, apply_rows, row_from_request

    ensure_assignable(db, current_user, body.business_unit_id, "employee")
    try:
        row = row_from_request(db, body)
    except ImportFileError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    outcome = apply_rows(db, current_user, [row], only_create=True)
    result = outcome["rows"][0]
    if result["status"] != "applied":
        errors = result["errors"]
        status = 409 if any("already exists" in e for e in errors) else 422
        raise HTTPException(status_code=status, detail="; ".join(errors))
    employee = db.get(Employee, result["employee_id"])
    if body.hired_for_htd:
        from app.services.htd_service import update_htd

        update_htd(db, employee, on_track=True, start=employee.joining_date, changed_by=current_user.UserID)
        db.commit()
    return _to_item(db, employee, viewer=current_user)


@router.get(
    "/import/template",
    summary="Employee import: the CSV template and what each column means",
    dependencies=[Depends(require_resource_permission("employees", "create"))]
)
def import_template(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.models.org_structure import OrgNode, OrgRole
    from app.services import employment_type_policy
    from app.services.employee_import_service import EMPLOYMENT_TYPE_TO_MODEL, IMPORT_COLUMNS, template_csv

    countries = [{"code": c["code"], "name": c["name"], "currency": c.get("currency"),
                  "employment_types": [o for o in c["options"] if o["accepted"] and o["value"] in EMPLOYMENT_TYPE_TO_MODEL]}
                 for c in employment_type_policy.describe()["countries"]]
    tid = current_user.tenant_id
    # Designations are org roles (they set the seat level); managers are people seated in the org
    # chart -- the new employee's seat goes under theirs (employee_import_service._seat_under_manager)
    roles = db.query(OrgRole).filter(OrgRole.tenant_id == tid, OrgRole.active.is_(True)) \
        .order_by(OrgRole.hierarchy_level.desc(), OrgRole.name).all()
    seated = db.query(Users, OrgNode).join(OrgNode, OrgNode.id == Users.org_node_id) \
        .filter(Users.tenant_id == tid, Users.terminated_at.is_(None), OrgNode.active.is_(True)) \
        .order_by(Users.UserName).all()
    from app.core.config import settings
    from app.models.client import BILLING_CURRENCIES
    from app.services.compensation import PAY_BASES

    return {"csv": template_csv(), "countries": countries,
            "pay_bases": list(PAY_BASES), "pay_basis_default": settings.PAY_BASIS_DEFAULT,
            "currencies": list(BILLING_CURRENCIES),
            "columns": [{"name": n, "required": r, "description": d} for n, r, d in IMPORT_COLUMNS],
            "org_roles": [{"name": r.name, "level": r.hierarchy_level} for r in roles],
            "managers": [{"user_id": u.UserID, "name": u.UserName or u.UserEmail, "email": u.UserEmail,
                          "title": u.job_title, "level": node.hierarchy_level} for u, node in seated]}


@router.post(
    "/import/dry-run",
    summary="Employee import, step 1: preview every row (nothing is written or emailed); returns the token",
    dependencies=[Depends(require_resource_permission("employees", "create"))]
)
async def import_dry_run(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.employee_import_service import ImportFileError, dry_run

    content = await file.read()
    try:
        return dry_run(db, current_user, content, file_name=file.filename)
    except ImportFileError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post(
    "/import/apply",
    summary="Employee import, step 2: apply a previewed file (same file + its token); each row all-or-nothing",
    dependencies=[Depends(require_resource_permission("employees", "create"))]
)
async def import_apply(
    token: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.employee_import_service import ImportFileError, ImportTokenError, apply

    content = await file.read()
    try:
        return apply(db, current_user, token, content)
    except ImportTokenError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except ImportFileError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(
    "",
    response_model=EmployeeListResponse,
    summary="List employees",
    dependencies=[Depends(require_resource_permission("employees", "view"))]
)
def list_employees(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    employees = _visible_employees(db, current_user).order_by(Employee.created_at.desc()).all()
    ids = [e.id for e in employees]
    bench = {b.employee_id: b for b in db.query(BenchPoolEntry).filter(BenchPoolEntry.employee_id.in_(ids))} if ids else {}
    allocations = _allocation_summaries(db, ids)
    from app.services.employee_certification_service import current_guidewire_levels

    levels = current_guidewire_levels(db, ids)
    sees_money = can_see_compensation(db, current_user)
    managers = _managers(db, employees)
    return EmployeeListResponse(employees=[
        _to_item(db, e, bench_entry=bench.get(e.id), allocations=allocations.get(e.id, []),
                 guidewire_level=levels.get(e.id), sees_money=sees_money, managers=managers) for e in employees])

class GuidewireCertificationUpdate(BaseModel):
    # derived from certificates held; accepted only when it matches (old clients send it back)
    guidewire_certification_current: Optional[str] = None
    guidewire_certification_expected: Optional[str] = None


class CertificateCreate(BaseModel):
    certification_id: str
    earned_date: date
    expires_date: Optional[date] = None  # None: the catalog's validity_months decides
    cert_number: Optional[str] = None
    issuer: Optional[str] = None
    status: str = "Active"


class CertificateUpdate(BaseModel):
    earned_date: Optional[date] = None
    expires_date: Optional[date] = None
    cert_number: Optional[str] = None
    issuer: Optional[str] = None
    status: Optional[str] = None


def _certificate_item(record) -> dict:
    cert = record.certification
    return {
        "id": record.id, "certification_id": record.certification_id,
        "cert_name": cert.cert_name if cert else None, "cert_code": cert.cert_code if cert else None,
        "guidewire_level": cert.guidewire_level if cert else None, "status": record.status,
        "earned_date": record.earned_date.date().isoformat() if record.earned_date else None,
        "expires_date": record.expires_date.date().isoformat() if record.expires_date else None,
        "cert_number": record.cert_number, "issuer": record.issuer,
    }


def _certificate_or_404(db: Session, employee: Employee, record_id: str):
    from app.models.certification import EmployeeCertification

    record = db.query(EmployeeCertification).filter(
        EmployeeCertification.id == record_id, EmployeeCertification.employee_id == employee.id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Certificate not found.")
    return record


def _company_or_400(db: Session, company_id: str, tenant_id: int) -> str:
    from app.models.location import Location
    if not db.query(Location).filter(Location.id == company_id, Location.tenant_id == tenant_id).first():
        raise HTTPException(status_code=400, detail="Unknown company")
    return company_id


class EmployeeOrgUpdate(BaseModel):
    # "" clears; omitted fields are left unchanged
    company_id: Optional[str] = None
    business_unit_id: Optional[int] = None


@router.put("/{employee_id}/organization", dependencies=[Depends(require_resource_permission("employees", "edit"))])
def update_employee_organization(
    employee_id: str,
    body: EmployeeOrgUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Employer company (BX-US / BX-IN) and business unit: headcount is counted by both."""
    from app.models.business_unit import BusinessUnit
    employee = _get_employee_or_404(db, employee_id, current_user)
    updates = body.dict(exclude_unset=True)
    if "company_id" in updates:
        employee.company_id = _company_or_400(db, updates["company_id"], current_user.tenant_id) if updates["company_id"] else None
    if "business_unit_id" in updates:
        bu_id = updates["business_unit_id"]
        if bu_id is not None and not db.query(BusinessUnit).filter(
            BusinessUnit.id == bu_id, BusinessUnit.tenant_id == current_user.tenant_id
        ).first():
            raise HTTPException(status_code=400, detail="Unknown business unit")
        ensure_assignable(db, current_user, bu_id, "employee")
        employee.bu_id = bu_id
    db.commit()
    return {"employee_id": employee.id, "company_id": employee.company_id, "business_unit_id": employee.bu_id}


def _is_self(employee: Employee, user: Users) -> bool:
    return bool(employee.wros_user_id) and employee.wros_user_id == user.UserID


def _profile_employee_or_404(db: Session, employee_id: str, user: Users) -> Employee:
    """The employee whose profile this viewer may open: anyone in scope with employees.view, and
    everyone their own (same 404 as an unknown id otherwise)."""
    from app.core import authority

    if authority.has_permission(db, user, "employees.view"):
        return _get_employee_or_404(db, employee_id, user)
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.tenant_id == user.tenant_id).first()
    if employee is None or not _is_self(employee, user):
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.get("/me", dependencies=[Depends(require_resource_permission("my-tasks", "view"))])
def my_employee_record(db: Session = Depends(get_db), current_user: Users = Depends(get_current_internal_user)):
    """The signed-in person's employee id (for "My profile"); 404 when the login has none."""
    employee = db.query(Employee).filter(Employee.wros_user_id == current_user.UserID,
                                         Employee.tenant_id == current_user.tenant_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Your login has no employee record")
    return {"employee_id": employee.id}


@router.get("/{employee_id}/profile", dependencies=[Depends(require_resource_permission("my-tasks", "view"))])
def get_employee_profile(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Everything about one employee for the profile page (app.services.employee_profile_service).
    Open to staff with employees.view (in their scope) and to each employee for their own."""
    from app.services.employee_profile_service import build_profile

    employee = _profile_employee_or_404(db, employee_id, current_user)
    profile = build_profile(db, employee, current_user, _to_item(db, employee, viewer=current_user).dict())
    profile["is_self"] = _is_self(employee, current_user)
    return profile


PHOTO_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
PHOTO_KINDS = {"photo": "photo_path", "cover": "cover_path"}


def _photo_kind(kind: str) -> str:
    if kind not in PHOTO_KINDS:
        raise HTTPException(status_code=404, detail="Unknown photo kind; photo or cover")
    return PHOTO_KINDS[kind]


@router.put("/{employee_id}/photo/{kind}", dependencies=[Depends(require_resource_permission("my-tasks", "view"))])
async def upload_employee_photo(
    employee_id: str,
    kind: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Profile photo or cover photo: the employee for their own, anyone with employees.edit for anyone
    in their scope. JPG, PNG or WEBP up to EMPLOYEE_PHOTO_MAX_BYTES; replaces the previous one."""
    import os

    from app.core import authority

    column = _photo_kind(kind)
    employee = _profile_employee_or_404(db, employee_id, current_user)
    if not (_is_self(employee, current_user) or authority.has_permission(db, current_user, "employees.edit")):
        raise HTTPException(status_code=403, detail="Only the employee or someone who edits employees can change this photo")
    extension = PHOTO_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(status_code=400, detail="Upload a JPG, PNG or WEBP image")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The image is empty")
    if len(data) > settings.EMPLOYEE_PHOTO_MAX_BYTES:
        raise HTTPException(status_code=400,
                            detail=f"The image is larger than {settings.EMPLOYEE_PHOTO_MAX_BYTES // (1024 * 1024)} MB")
    folder = os.path.join(settings.UPLOAD_DIR, "employee-photos", str(employee.tenant_id))
    os.makedirs(folder, exist_ok=True)
    old = getattr(employee, column)
    path = os.path.join(folder, f"{employee.id}-{kind}{extension}")
    with open(path, "wb") as handle:
        handle.write(data)
    if old and old != path and os.path.exists(old):
        os.remove(old)  # a different extension than before: the old file is no longer referenced
    setattr(employee, column, path)
    db.commit()
    logger.info(f"[Employees] {employee.id} {kind} changed by {current_user.UserID}")
    return {"employee_id": employee.id, "kind": kind}


@router.get("/{employee_id}/photo/{kind}", dependencies=[Depends(require_resource_permission("my-tasks", "view"))])
def get_employee_photo(
    employee_id: str,
    kind: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """A colleague's photo, like a staff directory: any internal user of the same tenant."""
    import os

    from fastapi.responses import FileResponse

    column = _photo_kind(kind)
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.tenant_id == current_user.tenant_id).first()
    path = getattr(employee, column) if employee else None
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No photo")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=300"})


class ManagerUpdate(BaseModel):
    manager_user_id: str


@router.put("/{employee_id}/manager", dependencies=[Depends(require_resource_permission("employees", "edit"))])
def update_employee_manager(
    employee_id: str,
    body: ManagerUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Who they report to. Someone with a WROS login is seated under the manager in the org chart
    (the one reporting line timesheet and expense approvals follow; the org rules decide); someone
    without a login has the manager recorded on their employee row."""
    from app.services.org_structure_service import place_under_manager

    employee = _get_employee_or_404(db, employee_id, current_user)
    manager = db.query(Users).filter(Users.UserID == body.manager_user_id, Users.tenant_id == current_user.tenant_id,
                                     Users.terminated_at.is_(None)).first()
    if manager is None:
        raise HTTPException(status_code=404, detail="Manager not found")
    if manager.UserID == employee.wros_user_id:
        raise HTTPException(status_code=400, detail="An employee cannot report to themselves")
    if employee.wros_user_id:
        login = db.query(Users).filter(Users.UserID == employee.wros_user_id).first()
        try:
            place_under_manager(db, login, manager)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
    else:
        employee.reporting_manager_user_id = manager.UserID
        manager_row = db.query(Employee).filter(Employee.wros_user_id == manager.UserID).first()
        employee.manager_id = manager_row.id if manager_row else None
    db.commit()
    db.refresh(employee)
    logger.info(f"[Employees] {employee.id} now reports to {manager.UserID} (set by {current_user.UserID})")
    return _to_item(db, employee, viewer=current_user)


class EmployeeDetailsUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    current_title: Optional[str] = None
    work_location: Optional[str] = None
    # personal
    legal_name: Optional[str] = None
    personal_email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    current_address: Optional[str] = None
    permanent_address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    # job
    employment_type: Optional[str] = None
    joining_date: Optional[date] = None  # only before they join
    confirmation_date: Optional[date] = None
    visa_status: Optional[str] = None
    total_experience_months: Optional[int] = None
    # money and ids (finance-operations.edit)
    base_salary_usd_cents: Optional[int] = None  # older clients: monthly USD pay
    pay_amount_cents: Optional[int] = None
    pay_currency: Optional[str] = None
    pay_basis: Optional[str] = None
    billing_rate_usd_cents: Optional[int] = None
    pan_number: Optional[str] = None
    tax_id: Optional[str] = None


# Free-text fields the PATCH takes as written (blank clears them)
_TEXT_FIELDS = ("legal_name", "phone", "gender", "nationality", "current_address", "permanent_address",
                "emergency_contact_name", "emergency_contact_phone", "visa_status")
_MONEY_FIELDS = ("base_salary_usd_cents", "pay_amount_cents", "pay_currency", "pay_basis", "billing_rate_usd_cents",
                 "pan_number", "tax_id")


@router.get("/edit-options", dependencies=[Depends(require_resource_permission("employees", "view"))])
def employee_edit_options():
    """Choices the employee edit form offers (the model's own lists)."""
    from app.models.employee import HTD_PHASES, WORK_LOCATIONS

    return {"work_locations": list(WORK_LOCATIONS), "htd_phases": list(HTD_PHASES)}


@router.patch("/{employee_id}", dependencies=[Depends(require_resource_permission("employees", "edit"))])
def update_employee_details(
    employee_id: str,
    body: EmployeeDetailsUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Any field of the profile page's Personal, Job and Finance sections. The work email is the
    person's identity once they have a WROS login (they sign in with it), so it changes in Users &
    Access, not here. Salary, bill rate and government ids need finance-operations.edit."""
    from app.models.employee import EMPLOYMENT_TYPES, WORK_LOCATIONS

    employee = _get_employee_or_404(db, employee_id, current_user)
    updates = body.dict(exclude_unset=True)
    if any(field in updates for field in _MONEY_FIELDS) and not can_edit_compensation(db, current_user):
        raise HTTPException(status_code=403, detail="Salary, bill rate and tax ids need Finance Operations edit access")
    for field in _TEXT_FIELDS:
        if field in updates:
            setattr(employee, field, (updates[field] or "").strip() or None)
    if "personal_email" in updates:
        personal = (updates["personal_email"] or "").strip().lower() or None
        if personal and "@" not in personal:
            raise HTTPException(status_code=400, detail="Personal email is not a valid email")
        employee.personal_email = personal
    if "date_of_birth" in updates:
        dob = updates["date_of_birth"]
        if dob is not None and dob >= date.today():
            raise HTTPException(status_code=400, detail="Date of birth must be in the past")
        employee.date_of_birth = dob
    if "employment_type" in updates:
        if updates["employment_type"] not in EMPLOYMENT_TYPES:
            raise HTTPException(status_code=400, detail=f"Employment type must be one of {list(EMPLOYMENT_TYPES)}")
        employee.employment_type = updates["employment_type"]
    if "joining_date" in updates and updates["joining_date"] != employee.joining_date:
        if employee.status != "PRE_JOINING" or updates["joining_date"] is None:
            raise HTTPException(status_code=409, detail="The joining date changes only before the employee joins")
        employee.joining_date = updates["joining_date"]
    if "confirmation_date" in updates:
        confirmed = updates["confirmation_date"]
        if confirmed is not None and confirmed < employee.joining_date:
            raise HTTPException(status_code=400, detail="Confirmation cannot be before the joining date")
        employee.confirmation_date = confirmed
    if "total_experience_months" in updates:
        months = updates["total_experience_months"]
        if months is not None and months < 0:
            raise HTTPException(status_code=400, detail="Experience cannot be negative")
        employee.total_experience_months = months
    if any(field in updates for field in ("pay_amount_cents", "pay_currency", "pay_basis", "base_salary_usd_cents")):
        from app.services import compensation
        from app.services.employment_type_policy import currency_of
        from app.core.config import settings
        from app.models.employee_org_history import country_of_company

        if "pay_amount_cents" in updates or "pay_currency" in updates or "pay_basis" in updates:
            amount = updates.get("pay_amount_cents", employee.pay_amount_cents)
            currency = updates.get("pay_currency") or employee.pay_currency \
                or currency_of(country_of_company(db, employee.company_id)) or "USD"
            basis = updates.get("pay_basis") or employee.pay_basis or settings.PAY_BASIS_DEFAULT
        else:  # older clients send the monthly USD salary
            amount, currency, basis = updates["base_salary_usd_cents"], "USD", "MONTHLY"
        try:
            compensation.set_pay(employee, amount, currency, basis)
        except compensation.PayError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    if "billing_rate_usd_cents" in updates:
        amount = updates["billing_rate_usd_cents"]
        if amount is not None and amount < 0:
            raise HTTPException(status_code=400, detail="Amounts cannot be negative")
        employee.billing_rate_usd_cents = amount
    for field in ("pan_number", "tax_id"):
        if field in updates:
            setattr(employee, field, (updates[field] or "").strip().upper() or None)
    for field in ("first_name", "last_name"):
        if field in updates:
            value = (updates[field] or "").strip()
            if not value:
                raise HTTPException(status_code=400, detail=f"{field.replace('_', ' ').capitalize()} is required")
            setattr(employee, field, value)
    if "current_title" in updates:
        employee.current_title = (updates["current_title"] or "").strip() or None
    if "work_location" in updates:
        if updates["work_location"] not in WORK_LOCATIONS:
            raise HTTPException(status_code=400, detail=f"Work location must be one of {list(WORK_LOCATIONS)}")
        employee.work_location = updates["work_location"]
    if "email" in updates and (updates["email"] or "").strip().lower() != (employee.email or "").lower():
        email = (updates["email"] or "").strip().lower()
        if employee.wros_user_id:
            raise HTTPException(status_code=409, detail="This employee signs in with this email: change it in "
                                                        "Users & Access so the login and the record stay one person.")
        if "@" not in email:
            raise HTTPException(status_code=400, detail="A valid email is required")
        clash = db.query(Employee.id).filter(Employee.tenant_id == employee.tenant_id, Employee.email == email,
                                             Employee.id != employee.id).first()
        if clash is not None:
            raise HTTPException(status_code=409, detail=f"Another employee already has {email}")
        employee.email = email
    db.commit()
    db.refresh(employee)
    return _to_item(db, employee, viewer=current_user)


class EmployeeHtdUpdate(BaseModel):
    htd_track: bool
    htd_phase: Optional[str] = None
    htd_start_date: Optional[date] = None


@router.put("/{employee_id}/htd", dependencies=[Depends(require_resource_permission("employees", "edit"))])
def update_employee_htd(
    employee_id: str,
    body: EmployeeHtdUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Hire-Train-Deploy: put the employee on the track (from a start date, first phase INDUCTION
    unless given), move their phase, or take them off it. Training is not bench and is a cost line
    of its own in the P&L (app.services.htd_service)."""
    from app.services.htd_service import HtdRefused, update_htd

    employee = _get_employee_or_404(db, employee_id, current_user)
    try:
        update_htd(db, employee, on_track=body.htd_track, phase=body.htd_phase, start=body.htd_start_date,
                   changed_by=current_user.UserID)
    except HtdRefused as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(employee)
    logger.info(f"[Employees] {employee.id} HTD track={employee.htd_track} phase={employee.htd_phase} "
                f"by {current_user.UserID}")
    return _to_item(db, employee, viewer=current_user)


class EmploymentChangeRequest(BaseModel):
    action: str  # START_NOTICE | RECORD_EXIT | START_LEAVE | END_LEAVE
    effective_date: Optional[date] = None  # last working day (notice) or exit date
    reason: str


@router.post("/{employee_id}/employment", dependencies=[Depends(require_resource_permission("employees", "edit"))])
def change_employee_employment(
    employee_id: str,
    body: EmploymentChangeRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Serving notice, exit (terminated) or leave, with their consequences (app.services.employment_change_service)."""
    from app.services.employee_service import InvalidStatusTransition
    from app.services.employment_change_service import EmploymentChangeRefused, change_employment

    employee = _get_employee_or_404(db, employee_id, current_user)
    try:
        change_employment(db, employee, body.action, effective_date=body.effective_date, reason=body.reason,
                          changed_by=current_user.UserID)
    except EmploymentChangeRefused as exc:  # nothing is committed: the request's session is discarded
        raise HTTPException(status_code=400, detail=str(exc))
    except InvalidStatusTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(employee)
    logger.info(f"[Employees] {employee.id} employment change {body.action} by {current_user.UserID}")
    return _to_item(db, employee, viewer=current_user)


class EmployeeBillableUpdate(BaseModel):
    billable: bool


@router.put("/{employee_id}/billable", dependencies=[Depends(require_resource_permission("employees", "edit"))])
def update_employee_billable(
    employee_id: str,
    body: EmployeeBillableUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Billable (client-facing: bench when not on a project) or non-billable (internal: overhead,
    never bench). Moves the person on or off the bench in the same transaction."""
    from app.services.bench_service import set_billable

    employee = _get_employee_or_404(db, employee_id, current_user)
    set_billable(db, employee, body.billable, changed_by=current_user.UserID)
    db.commit()
    db.refresh(employee)
    return _to_item(db, employee, viewer=current_user)


@router.put("/{employee_id}/certifications", dependencies=[Depends(require_resource_permission("employees", "edit"))])
def update_guidewire_certifications(
    employee_id: str,
    body: GuidewireCertificationUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Employees screen: the Guidewire TARGET level. The current level is derived from the
    certificates the employee holds (POST /employees/{id}/certificates); a different current level
    sent here is refused rather than silently ignored."""
    from app.models.certification import GUIDEWIRE_CERT_LEVELS
    from app.services.employee_certification_service import current_guidewire_levels

    employee = _get_employee_or_404(db, employee_id, current_user)
    current = current_guidewire_levels(db, [employee.id]).get(employee.id)
    allowed = ("None",) + GUIDEWIRE_CERT_LEVELS
    sent_current = body.guidewire_certification_current
    if sent_current is not None and (None if sent_current == "None" else sent_current) != current:
        raise HTTPException(status_code=400, detail=(
            "The current Guidewire level comes from the certificates the employee holds: add or remove "
            "a certificate instead of typing the level."))
    if body.guidewire_certification_expected is not None:
        if body.guidewire_certification_expected not in allowed:
            raise HTTPException(status_code=400,
                                detail=f"guidewire_certification_expected must be one of {list(allowed)}")
        employee.guidewire_certification_expected = (
            None if body.guidewire_certification_expected == "None" else body.guidewire_certification_expected)
    db.commit()
    return {
        "employee_id": employee.id,
        "guidewire_certification_current": current,
        "guidewire_certification_expected": employee.guidewire_certification_expected,
    }


@router.get("/certification-options", dependencies=[Depends(require_resource_permission("employees", "view"))])
def certification_options(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """The certificate catalog, record statuses and Guidewire levels for the certificates form."""
    from app.models.certification import CERT_STATUS, GUIDEWIRE_CERT_LEVELS
    from app.services.employee_certification_service import catalog

    return {
        "certifications": [
            {"id": c.id, "cert_name": c.cert_name, "cert_code": c.cert_code, "level": c.level,
             "guidewire_level": c.guidewire_level, "validity_months": c.validity_months}
            for c in catalog(db, current_user.tenant_id)
        ],
        "statuses": list(CERT_STATUS),
        "guidewire_levels": ["None", *GUIDEWIRE_CERT_LEVELS],
    }


@router.get("/{employee_id}/certificates", dependencies=[Depends(require_resource_permission("employees", "view"))])
def list_certificates(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Every certificate the employee holds, newest first, and the Guidewire level they give."""
    from app.services.employee_certification_service import current_guidewire_levels, list_records

    employee = _get_employee_or_404(db, employee_id, current_user)
    return {
        "certificates": [_certificate_item(r) for r in list_records(db, employee)],
        "guidewire_certification_current": current_guidewire_levels(db, [employee.id]).get(employee.id),
    }


@router.post("/{employee_id}/certificates", status_code=201,
             dependencies=[Depends(require_resource_permission("employees", "edit"))])
def add_certificate(
    employee_id: str,
    body: CertificateCreate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.employee_certification_service import EmployeeCertificationError, create_record

    employee = _get_employee_or_404(db, employee_id, current_user)
    try:
        record = create_record(db, employee, **body.model_dump())
    except EmployeeCertificationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(record)
    return _certificate_item(record)


@router.patch("/{employee_id}/certificates/{record_id}",
              dependencies=[Depends(require_resource_permission("employees", "edit"))])
def update_certificate(
    employee_id: str,
    record_id: str,
    body: CertificateUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.employee_certification_service import EmployeeCertificationError, update_record

    employee = _get_employee_or_404(db, employee_id, current_user)
    record = _certificate_or_404(db, employee, record_id)
    try:
        update_record(db, record, body.model_dump(exclude_unset=True))
    except EmployeeCertificationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(record)
    return _certificate_item(record)


@router.delete("/{employee_id}/certificates/{record_id}",
               dependencies=[Depends(require_resource_permission("employees", "delete"))])
def delete_certificate(
    employee_id: str,
    record_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.employee_certification_service import delete_record

    employee = _get_employee_or_404(db, employee_id, current_user)
    delete_record(db, _certificate_or_404(db, employee, record_id))
    db.commit()
    return {"deleted": record_id}



@router.get(
    "/utilization-summary", response_model=UtilizationSummaryResponse,
    dependencies=[Depends(require_resource_permission("utilization-dashboard", "view"))],
    summary="Employee Utilization Dashboard (S-254) -- latest utilization per employee + low-utilization alerts",
)
def utilization_summary(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.core.config import settings

    target = settings.UTILIZATION_TARGET_PCT
    latest_by_employee = get_latest_utilization_by_employee(db, tenant_id=current_user.tenant_id)
    # billable people only: internal staff are overhead, never under-utilized (CEO 2026-10-22)
    visible = {e.id: e for e in _visible_employees(db, current_user).filter(
        Employee.id.in_(list(latest_by_employee)), Employee.is_billable.is_(True))}
    items = []
    pct_values = []
    low_count = 0
    for employee_id, metric in latest_by_employee.items():
        employee = visible.get(employee_id)
        if employee is None:  # outside the caller's business units, or non-billable
            continue
        pct = float(metric.utilization_pct)
        pct_values.append(pct)
        is_low = pct < target
        if is_low:
            low_count += 1
        items.append(UtilizationSummaryItem(
            employee_id=employee_id,
            employee_name=f"{employee.first_name} {employee.last_name}".strip(),
            bu_id=employee.bu_id,
            latest_utilization_pct=pct,
            latest_period_start=metric.period_start,
            is_low_utilization=is_low,
        ))
    average = round(sum(pct_values) / len(pct_values), 2) if pct_values else None
    return UtilizationSummaryResponse(
        employees=items, average_utilization_pct=average, low_utilization_count=low_count,
        utilization_target_pct=target,
    )

@router.get(
    "/bench-cost-summary", response_model=BenchCostSummaryResponse,
    dependencies=[Depends(require_resource_permission("utilization-dashboard", "view"))],
    summary="Bench Cost Visibility (S-255) -- daily/monthly/running bench cost per employee + total",
)
def bench_cost_summary(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """The bench screen's own figures (bench_service.bench_report): loaded cost per bench day from
    the P&L's CostBook, so this, the bench screen and the P&L bench cost always agree. (It used to
    be raw monthly salary / 30, which disagreed with the P&L.)"""
    from app.services.bench_service import bench_report
    from app.services.revenue_chain_service import CostBook

    report = bench_report(db, current_user, financials=True)
    employees = {e.id: e for e in db.query(Employee).filter(Employee.id.in_([r["employee_id"] for r in report["employees"]]))}
    costs = CostBook(db)
    items = [BenchCostSummaryItem(
        employee_id=r["employee_id"], employee_name=r["name"], days_on_bench=r["bench_days"],
        daily_cost_usd_cents=r["daily_cost_usd_cents"], monthly_cost_usd_cents=costs.monthly(employees[r["employee_id"]]),
        running_total_usd_cents=r["bench_loss_usd_cents"],
    ) for r in report["employees"]]
    return BenchCostSummaryResponse(employees=items,
                                    total_running_cost_usd_cents=report["totals"]["bench_loss_usd_cents"])

@router.get(
    "/{employee_id}",
    response_model=EmployeeItem,
    summary="Get one employee",
    dependencies=[Depends(require_resource_permission("employees", "view"))]
)
def get_employee(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    employee = _get_employee_or_404(db, employee_id, current_user)
    return _to_item(db, employee, viewer=current_user)


@router.post(
    "/utilization/recompute", response_model=RecomputeUtilizationResponse,
    dependencies=[Depends(require_resource_permission("employees", "create"))],
    summary="Recompute weekly utilization now (S-223/HRMS-0904) for the billable employees the caller can see",
)
def recompute_utilization(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """What the weekly utilization_snapshot job does, now, for the caller's business units: the
    last completed weeks (settings.UTILIZATION_SNAPSHOT_WEEKS), billable working employees only."""
    employees = utilization_population(db).filter(
        Employee.tenant_id == current_user.tenant_id, bu_filter(db, current_user, Employee.bu_id)).all()
    written = snapshot_utilization(db, employees)
    db.commit()
    return RecomputeUtilizationResponse(employees=len(employees), snapshots=written)


@router.post(
    "/{employee_id}/mark-bench", response_model=EmployeeItem,
    dependencies=[Depends(require_resource_permission("employees", "create"))],
    summary="Mark an employee as on the bench (S-246)",
)
def mark_bench(
    employee_id: str,
    body: MarkBenchRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.bench_service import belongs_on_bench, sync_billing_classification
    from app.services.employee_service import transition_employee_status

    employee = _get_employee_or_404(db, employee_id, current_user)
    if employee.status == "ACTIVE" and employee.is_billable:
        transition_employee_status(db, employee, "BENCH", reason=f"Marked bench: {body.reason}",
                                   changed_by=current_user.UserID)
    if not belongs_on_bench(db, employee):
        db.rollback()
        raise HTTPException(status_code=409, detail=(
            "Only a billable, joined employee with no active allocation is on the bench: end their allocation "
            "first (or they are internal / not joined yet)."))
    mark_employee_on_bench(db, employee, reason=body.reason)
    sync_billing_classification(db, employee)
    db.commit()
    db.refresh(employee)
    return _to_item(db, employee, viewer=current_user)

@router.post(
    "/{employee_id}/remove-from-bench", response_model=EmployeeItem,
    dependencies=[Depends(require_resource_permission("employees", "create"))],
    summary="Remove an employee from the bench",
)
def remove_from_bench(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.bench_service import belongs_on_bench

    employee = _get_employee_or_404(db, employee_id, current_user)
    if belongs_on_bench(db, employee):
        raise HTTPException(status_code=409, detail=(
            "This employee is on the bench by rule (billable, no active allocation): allocate them to a job, "
            "or mark them non-billable."))
    remove_employee_from_bench(db, employee)  # clears a stale row
    db.commit()
    db.refresh(employee)
    return _to_item(db, employee, viewer=current_user)



# --------------------------------------------------------------------------- escalations
# An OPEN escalation keeps the employee away from every client (deployment_readiness_service);
# only a Director or above resolves one, with a note (CEO 2026-10-14).

def _escalation_item(row: EmployeeEscalation) -> EscalationItem:
    return EscalationItem(
        id=row.id, employee_id=row.employee_id, reason=row.reason, severity=row.severity, status=row.status,
        raised_by_user_id=row.raised_by_user_id, raised_at=row.raised_at, resolved_by_user_id=row.resolved_by_user_id,
        resolved_at=row.resolved_at, resolution_note=row.resolution_note,
    )


@router.get(
    "/{employee_id}/escalations", response_model=EscalationListResponse,
    dependencies=[Depends(require_resource_permission("employees", "view"))],
    summary="Escalations raised against an employee (open first)",
)
def list_escalations(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    employee = _get_employee_or_404(db, employee_id, current_user)
    rows = (
        db.query(EmployeeEscalation)
        .filter(EmployeeEscalation.employee_id == employee.id, EmployeeEscalation.tenant_id == current_user.tenant_id)
        .order_by(EmployeeEscalation.status, EmployeeEscalation.raised_at.desc())
        .all()
    )
    return EscalationListResponse(escalations=[_escalation_item(r) for r in rows])


@router.post(
    "/{employee_id}/escalations", response_model=EscalationItem, status_code=201,
    dependencies=[Depends(require_resource_permission("employees", "edit"))],
    summary="Raise an escalation (blocks client submission and deployment while open)",
)
def raise_escalation(
    employee_id: str,
    body: EscalationCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    employee = _get_employee_or_404(db, employee_id, current_user)
    row = EmployeeEscalation(tenant_id=current_user.tenant_id, employee_id=employee.id, reason=body.reason.strip(),
                             severity=body.severity, raised_by_user_id=current_user.UserID)
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(f"[Escalation] {row.id} raised on employee {employee.id} by {current_user.UserID}")
    return _escalation_item(row)


@router.post(
    "/escalations/{escalation_id}/resolve", response_model=EscalationItem,
    dependencies=[Depends(require_resource_permission("employees", "edit"))],
    summary="Resolve an escalation (Director and above)",
)
def resolve_escalation(
    escalation_id: str,
    body: EscalationResolveRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.core.authority import is_director

    row = db.query(EmployeeEscalation).filter(
        EmployeeEscalation.id == escalation_id, EmployeeEscalation.tenant_id == current_user.tenant_id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Escalation not found.")
    _get_employee_or_404(db, row.employee_id, current_user)  # another BU's escalation is not found
    if not is_director(db, current_user):
        raise HTTPException(status_code=403, detail="Only a Director or above can resolve an escalation.")
    if row.status != "OPEN":
        raise HTTPException(status_code=409, detail="This escalation is already resolved.")
    row.status, row.resolution_note = "RESOLVED", body.resolution_note.strip()
    row.resolved_by_user_id, row.resolved_at = current_user.UserID, datetime.utcnow()
    db.commit()
    db.refresh(row)
    logger.info(f"[Escalation] {row.id} resolved by {current_user.UserID}")
    return _escalation_item(row)
