"""
S-245 (Create Employee Profile) + S-246 (Mark Employee as Bench) +
S-247 (View Bench Pool) + S-248 (Bench Duration & Aging Report) — API
Endpoints
=========================================================================
Prefix: /employees
import logging
Tag:    employees

No employee REST API of any kind previously existed in this codebase
despite the Employee model, bench_pool lifecycle, and bench_periods
history all being real, tested backend (this and earlier Phase 4
rounds). This closes that gap for the foundational pieces four stories
in the EPIC-05/Resource & Bench Management cluster need.

Auth: same posture as every Phase 4 endpoint this program
(get_current_internal_user -- any internal user). No employee-specific
RBAC permission exists yet.

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
"""
import io
import os
import json
from datetime import date, datetime

from typing import Optional

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.candidate import Candidate
from app.models.employee import Employee, EmployeeEngineHistory
from app.models.resource_management import BenchPoolEntry
from app.models.user import Users
from app.schemas.performance import PerformanceEventItem, PerformanceStoreResponse
from app.core.logging import logger
from app.schemas.employee import (
    BenchAgingAlertItem,
    BenchAgingAlertsResponse,
    BenchCostSummaryItem,
    BenchCostSummaryResponse,
    BenchPeriodHistoryResponse,
    BenchPeriodItem,
    BulkImportResponse,
    BulkImportRowError,
    ConvertCandidateRequest,
    EmployeeCreateRequest,
    EmployeeItem,
    EmployeeListResponse,
    EngineHistoryItem,
    EngineHistoryResponse,
    MarkBenchRequest,
    RecordUtilizationRequest,
    StaffingEligibilityResponse,
    UtilizationHistoryItem,
    UtilizationHistoryResponse,
    UtilizationSummaryItem,
    UtilizationSummaryResponse,
)
from app.services.employee_service import (
    DuplicateEmployeeEmail,
    convert_candidate_to_employee,
    create_employee_profile,
    generate_employee_number,
)
from app.services.performance_store_service import (
    get_performance_events,
    get_score_averages_by_event_type,
)
from app.services.resource_management_service import (
    LOW_UTILIZATION_THRESHOLD_PCT,
    check_bench_aging_alerts,
    get_bench_duration_days,
    get_bench_period_history,
    get_current_bench_pool,
    get_latest_utilization_by_employee,
    get_utilization_history,
    is_staffing_eligible,
    mark_employee_on_bench,
    record_weekly_utilization_metric,
    remove_employee_from_bench,
)

router = APIRouter(prefix="/employees", tags=["employees"])

def _skills_list(raw):
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        raise ValueError("Operation failed")
    return parsed if isinstance(parsed, list) else []

def _to_item(db: Session, employee: Employee) -> EmployeeItem:
    bench_entry = db.query(BenchPoolEntry).filter(BenchPoolEntry.employee_id == employee.id).first()
    return EmployeeItem(
        id=employee.id,
        employee_number=employee.employee_number,
        first_name=employee.first_name,
        last_name=employee.last_name,
        email=employee.email,
        status=employee.status,
        employment_type=employee.employment_type,
        current_title=employee.current_title,
        current_skills=_skills_list(employee.current_skills),
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
    )

def _get_employee_or_404(db: Session, employee_id: str) -> Employee:
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    return employee

@router.post(
    "",
    response_model=EmployeeItem,
    summary="Create an employee profile",
    dependencies=[Depends(require_resource_permission("employees", "create"))]
)
def create_employee(
    body: EmployeeCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    fields = {}
    if body.current_title is not None:
        fields["current_title"] = body.current_title
    if body.current_skills is not None:
        fields["current_skills"] = json.dumps(body.current_skills)
    if body.employment_type is not None:
        fields["employment_type"] = body.employment_type
    if body.work_location is not None:
        fields["work_location"] = body.work_location
    if body.base_salary_usd_cents is not None:
        fields["base_salary_usd_cents"] = body.base_salary_usd_cents
    if body.billing_rate_usd_cents is not None:
        fields["billing_rate_usd_cents"] = body.billing_rate_usd_cents
    if body.nationality is not None:
        fields["nationality"] = body.nationality
    if body.org_node_id is not None:
        fields["org_node_id"] = body.org_node_id
    if body.business_unit_id is not None:
        fields["bu_id"] = body.business_unit_id
    if body.company_id:
        fields["company_id"] = _company_or_400(db, body.company_id, current_user.tenant_id)
    if body.reporting_manager_id is not None:
        fields["reporting_manager_user_id"] = body.reporting_manager_id

    # Optionally create a login account for this employee with the given
    # role template - do this before creating the Employee row so a bad
    # role_template_id fails the whole request instead of leaving an
    # Employee with no linked account.
    new_user = None
    if body.role_template_id is not None:
        from app.models.role_template import RoleTemplate
        role_template = db.query(RoleTemplate).filter(RoleTemplate.id == body.role_template_id).first()
        if not role_template:
            raise HTTPException(status_code=400, detail="Role template not found")
        if db.query(Users).filter(Users.UserEmail == body.email).first():
            raise HTTPException(status_code=409, detail=f"A user account already exists for {body.email}")

        from app.core.security import get_password_hash
        from app.utils.uniq_id_generator import user_id_generator
        import secrets as _secrets
        import string as _string

        temp_password = "".join(_secrets.choice(_string.ascii_letters + _string.digits) for _ in range(16))
        new_user = Users(
            UserID=user_id_generator(),
            UserEmail=body.email,
            UserName=f"{body.first_name} {body.last_name}".strip(),
            UserPassword=get_password_hash(temp_password),
            UserRole="User",
            role_template_id=body.role_template_id,
            business_unit_id=body.business_unit_id,
            tenant_id=current_user.tenant_id,
            password_reset_required=True,
        )
        db.add(new_user)
        db.flush()
        fields["wros_user_id"] = new_user.UserID

    try:
        employee = create_employee_profile(
            db, tenant_id=current_user.tenant_id,
            first_name=body.first_name, last_name=body.last_name, email=body.email,
            joining_date=body.joining_date, changed_by=current_user.UserID,
            **fields,
        )
    except DuplicateEmployeeEmail as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(employee)

    # Queue employee operation for FLASH orchestrator
    try:
        from app.services.message_queue_service import MessageQueueService
        MessageQueueService.enqueue(
            task_name='employee_created_flash',
            task_id=str(employee.id),
            data={
                'employee_id': str(employee.id),
                'employee_email': employee.email,
                'employee_name': f"{employee.first_name} {employee.last_name}".strip(),
                'created_at': datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.warning(f"Failed to queue employee creation: {e}")

    return _to_item(db, employee)

@router.post(
    "/convert-candidate/{candidate_id}", response_model=EmployeeItem,
    dependencies=[Depends(require_resource_permission("employees", "create"))],
    summary="Convert a candidate to an employee (HRMS-0708 minimal slice)",
)
def convert_candidate(
    candidate_id: str,
    body: ConvertCandidateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if db.query(Employee).filter(Employee.candidate_id == candidate_id).first():
        raise HTTPException(status_code=409, detail=f"Candidate {candidate_id} has already been converted to an employee.")

    fields = {"employee_number": generate_employee_number(db, current_user.tenant_id, "BLX")}
    if body.current_title is not None:
        fields["current_title"] = body.current_title
    if body.current_skills is not None:
        fields["current_skills"] = json.dumps(body.current_skills)
    if body.employment_type is not None:
        fields["employment_type"] = body.employment_type
    if body.work_location is not None:
        fields["work_location"] = body.work_location
    if body.base_salary_usd_cents is not None:
        fields["base_salary_usd_cents"] = body.base_salary_usd_cents
    if body.billing_rate_usd_cents is not None:
        fields["billing_rate_usd_cents"] = body.billing_rate_usd_cents
    if body.nationality is not None:
        fields["nationality"] = body.nationality
    if body.current_address is not None:
        fields["current_address"] = body.current_address
    if body.permanent_address is not None:
        fields["permanent_address"] = body.permanent_address

    employee = convert_candidate_to_employee(
        db, candidate, joining_date=body.joining_date, tenant_id=current_user.tenant_id,
        changed_by=current_user.UserID, **fields,
    )
    db.commit()
    db.refresh(employee)

    # Queue employee conversion for FLASH orchestrator
    try:
        from app.services.message_queue_service import MessageQueueService
        MessageQueueService.enqueue(
            task_name='employee_created_flash',
            task_id=str(employee.id),
            data={
                'employee_id': str(employee.id),
                'employee_email': employee.email,
                'employee_name': f"{employee.first_name} {employee.last_name}".strip(),
                'converted_from_candidate': str(candidate.candidateID),
                'created_at': datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.warning(f"Failed to queue employee creation: {e}")

    # Send welcome email to new employee
    try:
        from app.services.email_service import EmailService
        from app.services.template_service import TemplateService

        # Get portal URL and login credentials
        # PORTAL_URL env overrides; default is the live HRMS address
        portal_url = os.getenv("PORTAL_URL", "https://hrms.blitzenx.com")
        employee_name = f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip()

        # Render email template with dynamic fields
        email_body = TemplateService.render_template(
            db=db,
            tenant_id=current_user.tenant_id,
            template_key="EMPLOYEE_WELCOME_EMAIL",
            channel="EMAIL",
            context={
                "employee_name": employee_name,
                "department": getattr(employee, 'department', 'Not Set'),
                "business_unit": getattr(employee, 'business_unit', 'Not Set'),
                "portal_url": portal_url,
                "login_email": candidate.candidateEmail,
                "joining_date": body.joining_date.isoformat() if body.joining_date else "Not Set",
            }
        )

        # Send email if template exists
        if email_body:
            EmailService.send_event_notification(
                to_email=candidate.candidateEmail,
                recipient_name=employee_name,
                event_type="action_required",
                heading="Welcome to BlitzenX!",
                message=email_body,
            )
    except Exception as e:
        logger.warning(f"Failed to send welcome email to {candidate.candidateEmail}: {str(e)}")

    return _to_item(db, employee)

_BULK_IMPORT_COLUMNS = (
    "first_name", "last_name", "email", "joining_date", "current_title",
    "current_skills", "employment_type", "work_location",
    "base_salary_usd_cents", "billing_rate_usd_cents", "nationality",
)

def _parse_bulk_import_date(raw) -> date:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    return datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()


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
    employees = (
        db.query(Employee)
        .filter(Employee.tenant_id == current_user.tenant_id)
        .order_by(Employee.created_at.desc())
        .all()
    )
    return EmployeeListResponse(employees=[_to_item(db, e) for e in employees])

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
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.tenant_id == current_user.tenant_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")
    updates = body.dict(exclude_unset=True)
    if "company_id" in updates:
        employee.company_id = _company_or_400(db, updates["company_id"], current_user.tenant_id) if updates["company_id"] else None
    if "business_unit_id" in updates:
        bu_id = updates["business_unit_id"]
        if bu_id is not None and not db.query(BusinessUnit).filter(
            BusinessUnit.id == bu_id, BusinessUnit.tenant_id == current_user.tenant_id
        ).first():
            raise HTTPException(status_code=400, detail="Unknown business unit")
        employee.bu_id = bu_id
    db.commit()
    return {"employee_id": employee.id, "company_id": employee.company_id, "business_unit_id": employee.bu_id}


@router.put("/{employee_id}/certifications", dependencies=[Depends(require_resource_permission("employees", "edit"))])
def update_guidewire_certifications(
    employee_id: str,
    body: GuidewireCertificationUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Employees screen: Guidewire certification level now and target."""
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.tenant_id == current_user.tenant_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")
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
    dependencies=[Depends(require_resource_permission("employees", "view"))],
    summary="Employee Utilization Dashboard (S-254) -- latest utilization per employee + low-utilization alerts",
)
def utilization_summary(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    latest_by_employee = get_latest_utilization_by_employee(db, tenant_id=current_user.tenant_id)
    items = []
    pct_values = []
    low_count = 0
    for employee_id, metric in latest_by_employee.items():
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        if employee is None:
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
    dependencies=[Depends(require_resource_permission("employees", "view"))],
    summary="Bench Cost Visibility (S-255) -- daily/monthly/running bench cost per employee + total",
)
def bench_cost_summary(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    entries = get_current_bench_pool(db, tenant_id=current_user.tenant_id)
    items = []
    total_running = 0
    for entry in entries:
        employee = db.query(Employee).filter(Employee.id == entry.employee_id).first()
        if employee is None:
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
    employee = _get_employee_or_404(db, employee_id)
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
    employee = _get_employee_or_404(db, employee_id)
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
    employee = _get_employee_or_404(db, employee_id)
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
    employee = _get_employee_or_404(db, employee_id)
    remove_employee_from_bench(db, employee)
    db.commit()
    db.refresh(employee)
    return _to_item(db, employee)

