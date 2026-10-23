"""
Pydantic schemas — S-245 (Create Employee Profile) + S-246 (Mark
Employee as Bench, extended with bench_periods history) + S-247/S-248
(bench pool view / aging alerts) API.
"""

import logging
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.models.employee_escalation import ESCALATION_SEVERITIES

logger = logging.getLogger(__name__)

class EmployeeCreateRequest(BaseModel):
    """Add employee (one import row, app.services.employee_import_service): the same columns as
    the CSV, with ids where the form has pickers."""
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=1)
    joining_date: date
    business_unit_id: int = Field(..., description="Maps to Employee.bu_id")
    base_salary_usd_cents: int = Field(..., ge=0, description="Monthly base salary: the P&L and bench cost source")
    billable: bool = Field(..., description="Client-facing (bench when not on a project) or internal (overhead)")
    company_id: Optional[str] = Field(None, description="Delivery center / employer company (locations.id)")
    country: Optional[str] = Field(None, description="ISO code; blank = the delivery center's country")
    current_title: Optional[str] = None
    current_skills: Optional[List[str]] = None
    employment_type: Optional[str] = None  # FULLTIME | CONTRACT (PERMANENT/FIXED_TERM read as FULLTIME)
    work_location: Optional[str] = None  # REMOTE | ONSITE | HYBRID
    billing_rate_usd_cents: Optional[int] = None
    employee_code: Optional[str] = None
    reporting_manager_id: Optional[str] = Field(None, description="Users.UserID this employee reports to")
    role_template_id: Optional[int] = Field(None, description="Function add-on; blank = the tenant's Employee role")
    existing_staff: bool = True
    core_certified: bool = False
    bench_since: Optional[date] = None

class ConvertCandidateRequest(BaseModel):
    joining_date: date
    current_title: Optional[str] = None
    current_skills: Optional[List[str]] = None
    employment_type: Optional[str] = None
    work_location: Optional[str] = None
    base_salary_usd_cents: Optional[int] = None
    billing_rate_usd_cents: Optional[int] = None
    nationality: Optional[str] = None
    # Added 2026-07-23: Avinash's instruction -- full street-level address
    # is collected at conversion time, not during candidate intake (which
    # only ever captures city/state/country). Employee.current_address/
    # permanent_address already existed on the model, unexposed here.
    current_address: Optional[str] = None
    permanent_address: Optional[str] = None

class EmployeeItem(BaseModel):
    id: str
    employee_number: Optional[str] = None
    first_name: str
    last_name: str
    email: str
    status: str
    employment_type: str
    current_title: Optional[str] = None
    current_skills: List[str] = []
    work_location: str
    delivery_engine: str
    engine_entry_date: date
    core_certified: bool
    core_certified_date: Optional[date] = None
    joining_date: date
    base_salary_usd_cents: Optional[int] = None
    billing_rate_usd_cents: Optional[int] = None
    is_on_bench: bool = False
    bench_days: Optional[int] = None
    guidewire_certification_current: Optional[str] = None
    guidewire_certification_expected: Optional[str] = None
    bu_id: Optional[int] = None
    company_id: Optional[str] = None
    is_billable: bool = True
    buddy_program_status: Optional[str] = None
    has_login: bool = False
    reporting_manager_user_id: Optional[str] = None
    # the employee's ACTIVE allocations (client, job, %): what "allocated" means everywhere
    active_allocations: List[dict] = []
    allocated_pct: float = 0

class EmployeeListResponse(BaseModel):
    employees: List[EmployeeItem]

class MarkBenchRequest(BaseModel):
    reason: str = Field(..., pattern="^(PROJECT_ENDED|PROJECT_DELAYED|NEWLY_JOINED|BETWEEN_PROJECTS|OTHER)$")

class BenchPeriodItem(BaseModel):
    id: str
    bench_start_date: date
    bench_end_date: Optional[date] = None
    reason_for_bench: str
    bench_cost_usd_cents: Optional[int] = None

class BenchPeriodHistoryResponse(BaseModel):
    periods: List[BenchPeriodItem]

class BenchAgingAlertItem(BaseModel):
    employee_id: str
    employee_name: str
    days_on_bench: int
    bench_cost_usd_cents: Optional[int] = None

class BenchAgingAlertsResponse(BaseModel):
    alerts: List[BenchAgingAlertItem]

class StaffingEligibilityResponse(BaseModel):
    employee_id: str
    delivery_engine: str
    eligible: bool
    reason: Optional[str] = None

# ---------------------------------------------------------------------------
# S-351/HRMS-0512 -- Delivery Engine Assignment: Speciality vs Core.
# Read-only per the source doc's "Not In Scope: do NOT build any UI bypass
# for delivery engine assignment" -- CORE can only ever be set via
# set_core_delivery_engine() (the future HRMS-0513 Core Eligibility Gate's
# real mutation point), never through this history endpoint.
# ---------------------------------------------------------------------------

class EngineHistoryItem(BaseModel):
    id: int
    from_engine: Optional[str] = None
    to_engine: str
    changed_at: Optional[datetime] = None
    changed_by: Optional[str] = None
    approval_reference: Optional[str] = None
    reason: Optional[str] = None

class EngineHistoryResponse(BaseModel):
    employee_id: str
    history: List[EngineHistoryItem]

class RecomputeUtilizationResponse(BaseModel):
    employees: int
    snapshots: int

class UtilizationHistoryItem(BaseModel):
    period_start: date
    utilization_pct: float
    billable_hours: float
    bench_hours: float

class UtilizationHistoryResponse(BaseModel):
    employee_id: str
    history: List[UtilizationHistoryItem]

class UtilizationSummaryItem(BaseModel):
    employee_id: str
    employee_name: str
    bu_id: Optional[int] = None
    latest_utilization_pct: Optional[float] = None
    latest_period_start: Optional[date] = None
    is_low_utilization: bool = False

class UtilizationSummaryResponse(BaseModel):
    employees: List[UtilizationSummaryItem]
    average_utilization_pct: Optional[float] = None
    low_utilization_count: int = 0
    # settings.UTILIZATION_TARGET_PCT: below it an employee's latest week is flagged
    utilization_target_pct: float

class BenchCostSummaryItem(BaseModel):
    employee_id: str
    employee_name: str
    days_on_bench: int
    daily_cost_usd_cents: Optional[int] = None
    monthly_cost_usd_cents: Optional[int] = None
    running_total_usd_cents: Optional[int] = None

class BenchCostSummaryResponse(BaseModel):
    employees: List[BenchCostSummaryItem]
    total_running_cost_usd_cents: int

class EscalationCreateRequest(BaseModel):
    reason: str = Field(..., min_length=3)
    severity: Literal[ESCALATION_SEVERITIES] = "MEDIUM"

class EscalationResolveRequest(BaseModel):
    resolution_note: str = Field(..., min_length=3)

class EscalationItem(BaseModel):
    id: str
    employee_id: str
    reason: str
    severity: str
    status: str
    raised_by_user_id: Optional[str] = None
    raised_at: Optional[datetime] = None
    resolved_by_user_id: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None

class EscalationListResponse(BaseModel):
    escalations: List[EscalationItem]
