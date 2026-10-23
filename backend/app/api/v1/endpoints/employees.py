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
    RecordUtilizationRequest,
    UtilizationHistoryItem,
    UtilizationSummaryItem,
    UtilizationSummaryResponse,
)
from app.services.resource_management_service import (
    LOW_UTILIZATION_THRESHOLD_PCT,
    get_bench_duration_days,
    get_current_bench_pool,
    get_latest_utilization_by_employee,
    mark_employee_on_bench,
    record_weekly_utilization_metric,
    remove_employee_from_bench,
)

router = APIRouter(prefix="/employees", tags=["employees"])

def _skills_list(raw, employee_id: str = None):
    """Employee.current_skills is a JSON array; rows written before that rule hold plain text
    ("Java, Guidewire"), which is parsed as a comma/semicolon list -- a real parse, logged so
    the legacy rows can be found -- never a failed list and never a silent []."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"[Employees] employee {employee_id}: current_skills is not JSON, read as a list: {raw!r}")
        return [s.strip() for s in str(raw).replace(";", ",").split(",") if s.strip()]
    if isinstance(parsed, list):
        return [str(s) for s in parsed]
    logger.warning(f"[Employees] employee {employee_id}: current_skills JSON is not a list: {raw!r}")
    return [str(parsed)]


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
        })
    return out


def _to_item(db: Session, employee: Employee, *, bench_entry=..., allocations=None) -> EmployeeItem:
    if bench_entry is ...:
        bench_entry = db.query(BenchPoolEntry).filter(BenchPoolEntry.employee_id == employee.id).first()
    if allocations is None:
        allocations = _allocation_summaries(db, [employee.id]).get(employee.id, [])
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
        base_salary_usd_cents=employee.base_salary_usd_cents,
        billing_rate_usd_cents=employee.billing_rate_usd_cents,
        is_on_bench=bench_entry is not None,
        bench_days=get_bench_duration_days(bench_entry) if bench_entry else None,
        guidewire_certification_current=employee.guidewire_certification_current,
        guidewire_certification_expected=employee.guidewire_certification_expected,
        bu_id=employee.bu_id,
        company_id=employee.company_id,
        is_billable=bool(employee.is_billable),
        buddy_program_status=employee.buddy_program_status,
        has_login=employee.wros_user_id is not None,
        reporting_manager_user_id=employee.reporting_manager_user_id,
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
    return _to_item(db, db.get(Employee, result["employee_id"]))


@router.get(
    "/import/template",
    summary="Employee import: the CSV template and what each column means",
    dependencies=[Depends(require_resource_permission("employees", "create"))]
)
def import_template():
    from app.services import employment_type_policy
    from app.services.employee_import_service import EMPLOYMENT_TYPE_TO_MODEL, IMPORT_COLUMNS, template_csv

    countries = [{"code": c["code"], "name": c["name"],
                  "employment_types": [o for o in c["options"] if o["accepted"] and o["value"] in EMPLOYMENT_TYPE_TO_MODEL]}
                 for c in employment_type_policy.describe()["countries"]]
    return {"csv": template_csv(), "countries": countries,
            "columns": [{"name": n, "required": r, "description": d} for n, r, d in IMPORT_COLUMNS]}


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
    return EmployeeListResponse(employees=[
        _to_item(db, e, bench_entry=bench.get(e.id), allocations=allocations.get(e.id, [])) for e in employees])

class GuidewireCertificationUpdate(BaseModel):
    guidewire_certification_current: Optional[str] = None
    guidewire_certification_expected: Optional[str] = None


GUIDEWIRE_CERT_LEVELS = ("None", "ACE", "Associate", "Specialist")


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
    return _to_item(db, employee)


@router.put("/{employee_id}/certifications", dependencies=[Depends(require_resource_permission("employees", "edit"))])
def update_guidewire_certifications(
    employee_id: str,
    body: GuidewireCertificationUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Employees screen: Guidewire certification level now and target."""
    employee = _get_employee_or_404(db, employee_id, current_user)
    for field in ("guidewire_certification_current", "guidewire_certification_expected"):
        value = getattr(body, field)
        if value is None:
            continue
        if value not in GUIDEWIRE_CERT_LEVELS:
            raise HTTPException(status_code=400, detail=f"{field} must be one of {GUIDEWIRE_CERT_LEVELS}")
        setattr(employee, field, None if value == "None" else value)
    db.commit()
    return {
        "employee_id": employee.id,
        "guidewire_certification_current": employee.guidewire_certification_current,
        "guidewire_certification_expected": employee.guidewire_certification_expected,
    }



@router.get(
    "/utilization-summary", response_model=UtilizationSummaryResponse,
    dependencies=[Depends(require_resource_permission("utilization-dashboard", "view"))],
    summary="Employee Utilization Dashboard (S-254) -- latest utilization per employee + low-utilization alerts",
)
def utilization_summary(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    latest_by_employee = get_latest_utilization_by_employee(db, tenant_id=current_user.tenant_id)
    visible = {e.id: e for e in _visible_employees(db, current_user).filter(Employee.id.in_(list(latest_by_employee)))}
    items = []
    pct_values = []
    low_count = 0
    for employee_id, metric in latest_by_employee.items():
        employee = visible.get(employee_id)
        if employee is None:  # outside the caller's business units
            continue
        pct = float(metric.utilization_pct)
        pct_values.append(pct)
        is_low = pct < LOW_UTILIZATION_THRESHOLD_PCT
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
    entries = get_current_bench_pool(db, tenant_id=current_user.tenant_id)
    visible = {e.id: e for e in _visible_employees(db, current_user).filter(
        Employee.id.in_([entry.employee_id for entry in entries]))}
    items = []
    total_running = 0
    for entry in entries:
        employee = visible.get(entry.employee_id)
        if employee is None:  # outside the caller's business units
            continue
        days = get_bench_duration_days(entry)
        daily = entry.bench_cost_usd_cents
        running = (daily * days) if daily is not None else None
        if running is not None:
            total_running += running
        items.append(BenchCostSummaryItem(
            employee_id=entry.employee_id,
            employee_name=f"{employee.first_name} {employee.last_name}".strip(),
            days_on_bench=days,
            daily_cost_usd_cents=daily,
            monthly_cost_usd_cents=(daily * 30) if daily is not None else None,
            running_total_usd_cents=running,
        ))
    return BenchCostSummaryResponse(employees=items, total_running_cost_usd_cents=total_running)

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
    return _to_item(db, employee)


@router.post(
    "/{employee_id}/record-utilization", response_model=UtilizationHistoryItem,
    dependencies=[Depends(require_resource_permission("employees", "create"))],
    summary="Calculate + snapshot one employee's utilization for a week (S-223/HRMS-0904) -- billable hours vs available hours",
)
def record_utilization(
    employee_id: str,
    body: RecordUtilizationRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    employee = _get_employee_or_404(db, employee_id, current_user)
    metric = record_weekly_utilization_metric(db, employee, body.week_starting_date)
    db.commit()
    db.refresh(metric)
    return UtilizationHistoryItem(
        period_start=metric.period_start, utilization_pct=float(metric.utilization_pct),
        billable_hours=float(metric.billable_hours), bench_hours=float(metric.bench_hours),
    )


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
    employee = _get_employee_or_404(db, employee_id, current_user)
    mark_employee_on_bench(db, employee, reason=body.reason)
    db.commit()
    db.refresh(employee)
    return _to_item(db, employee)

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
    employee = _get_employee_or_404(db, employee_id, current_user)
    remove_employee_from_bench(db, employee)
    db.commit()
    db.refresh(employee)
    return _to_item(db, employee)



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
