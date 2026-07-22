"""
Pydantic schemas — S-245 (Create Employee Profile) + S-246 (Mark
Employee as Bench, extended with bench_periods history) + S-247/S-248
(bench pool view / aging alerts) API.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class EmployeeCreateRequest(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=1)
    joining_date: date
    current_title: Optional[str] = None
    current_skills: Optional[List[str]] = None
    employment_type: Optional[str] = None  # PERMANENT | CONTRACT | FIXED_TERM
    work_location: Optional[str] = None  # REMOTE | ONSITE | HYBRID
    base_salary_usd_cents: Optional[int] = None
    billing_rate_usd_cents: Optional[int] = None
    nationality: Optional[str] = None


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
    core_certified: bool
    joining_date: date
    base_salary_usd_cents: Optional[int] = None
    billing_rate_usd_cents: Optional[int] = None
    is_on_bench: bool = False
    bench_days: Optional[int] = None


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
