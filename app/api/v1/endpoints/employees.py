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

Auth: same posture as every Phase 4 endpoint this program
(get_current_hr_or_admin -- any internal user). No employee-specific
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
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin
from app.models.employee import Employee
from app.models.resource_management import BenchPoolEntry
from app.models.user import Users
from app.schemas.employee import (
    BenchAgingAlertItem,
    BenchAgingAlertsResponse,
    BenchPeriodHistoryResponse,
    BenchPeriodItem,
    EmployeeCreateRequest,
    EmployeeItem,
    EmployeeListResponse,
    MarkBenchRequest,
    StaffingEligibilityResponse,
)
from app.services.employee_service import DuplicateEmployeeEmail, create_employee_profile
from app.services.resource_management_service import (
    check_bench_aging_alerts,
    get_bench_duration_days,
    get_bench_period_history,
    get_current_bench_pool,
    is_staffing_eligible,
    mark_employee_on_bench,
    remove_employee_from_bench,
)

router = APIRouter(prefix="/employees", tags=["employees"])


def _skills_list(raw):
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
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
        core_certified=employee.core_certified,
        joining_date=employee.joining_date,
        base_salary_usd_cents=employee.base_salary_usd_cents,
        billing_rate_usd_cents=employee.billing_rate_usd_cents,
        is_on_bench=bench_entry is not None,
        bench_days=get_bench_duration_days(bench_entry) if bench_entry else None,
    )


def _get_employee_or_404(db: Session, employee_id: str) -> Employee:
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    return employee


@router.post("", response_model=EmployeeItem, summary="Create an employee profile")
def create_employee(
    body: EmployeeCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
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

    try:
        employee = create_employee_profile(
            db, tenant_id=current_user.tenant_id,
            first_name=body.first_name, last_name=body.last_name, email=body.email,
            joining_date=body.joining_date, changed_by=current_user.UserID,
            **fields,
        )
    except DuplicateEmployeeEmail as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(employee)
    return _to_item(db, employee)


@router.get("", response_model=EmployeeListResponse, summary="List employees")
def list_employees(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    employees = (
        db.query(Employee)
        .filter(Employee.tenant_id == current_user.tenant_id)
        .order_by(Employee.created_at.desc())
        .all()
    )
    return EmployeeListResponse(employees=[_to_item(db, e) for e in employees])


@router.get(
    "/bench-pool", response_model=EmployeeListResponse,
    summary="View the current bench pool (S-247)",
)
def view_bench_pool(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    entries = get_current_bench_pool(db, tenant_id=current_user.tenant_id)
    employees = []
    for entry in entries:
        employee = db.query(Employee).filter(Employee.id == entry.employee_id).first()
        if employee is not None:
            employees.append(_to_item(db, employee))
    return EmployeeListResponse(employees=employees)


@router.get(
    "/bench-aging-alerts", response_model=BenchAgingAlertsResponse,
    summary="Employees who just crossed a 30/60/90-day bench milestone (S-248)",
)
def bench_aging_alerts(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    alerts = check_bench_aging_alerts(db, tenant_id=current_user.tenant_id)
    items = []
    for alert in alerts:
        employee = db.query(Employee).filter(Employee.id == alert["employee_id"]).first()
        employee_name = f"{employee.first_name} {employee.last_name}".strip() if employee else "(unknown)"
        items.append(BenchAgingAlertItem(employee_name=employee_name, **alert))
    return BenchAgingAlertsResponse(alerts=items)


@router.get("/{employee_id}", response_model=EmployeeItem, summary="Get one employee")
def get_employee(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    employee = _get_employee_or_404(db, employee_id)
    return _to_item(db, employee)


@router.get(
    "/{employee_id}/staffing-eligibility", response_model=StaffingEligibilityResponse,
    summary="Staffing Eligibility Engine (S-250) -- can this employee appear in ranking for a delivery engine?",
)
def staffing_eligibility(
    employee_id: str,
    delivery_engine: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    employee = _get_employee_or_404(db, employee_id)
    eligible, reason = is_staffing_eligible(employee, delivery_engine)
    return StaffingEligibilityResponse(
        employee_id=employee_id, delivery_engine=delivery_engine, eligible=eligible, reason=reason,
    )


@router.post(
    "/{employee_id}/mark-bench", response_model=EmployeeItem,
    summary="Mark an employee as on the bench (S-246)",
)
def mark_bench(
    employee_id: str,
    body: MarkBenchRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    employee = _get_employee_or_404(db, employee_id)
    mark_employee_on_bench(db, employee, reason=body.reason)
    db.commit()
    db.refresh(employee)
    return _to_item(db, employee)


@router.post(
    "/{employee_id}/remove-from-bench", response_model=EmployeeItem,
    summary="Remove an employee from the bench",
)
def remove_from_bench(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    employee = _get_employee_or_404(db, employee_id)
    remove_employee_from_bench(db, employee)
    db.commit()
    db.refresh(employee)
    return _to_item(db, employee)


@router.get(
    "/{employee_id}/bench-history", response_model=BenchPeriodHistoryResponse,
    summary="Full bench episode history for an employee",
)
def bench_history(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    _get_employee_or_404(db, employee_id)
    periods = get_bench_period_history(db, employee_id)
    return BenchPeriodHistoryResponse(
        periods=[
            BenchPeriodItem(
                id=p.id, bench_start_date=p.bench_start_date, bench_end_date=p.bench_end_date,
                reason_for_bench=p.reason_for_bench, bench_cost_usd_cents=p.bench_cost_usd_cents,
            )
            for p in periods
        ]
    )
