"""
Pydantic schemas -- HRMS-0801 (Project Lifecycle) + HRMS-0804
(Milestones) + HRMS-0805 (Unfilled Roles) + HRMS-0806 (Revenue
Estimate & Margin) + S-358/HRMS-0519 (SI Partner Tagging) API.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    client_id: str
    name: str = Field(..., min_length=1)
    billing_type: str = "TIME_AND_MATERIALS"
    currency: str = "USD"
    continent: Optional[str] = None
    delivery_engine: str = "SPECIALITY"
    si_partner: Optional[str] = None
    allow_weekend_billing: bool = False


class ProjectItem(BaseModel):
    id: str
    client_id: str
    opportunity_id: Optional[str] = None
    name: str
    status: str
    billing_type: str
    currency: str
    continent: Optional[str] = None
    delivery_engine: str
    si_partner: Optional[str] = None
    allow_weekend_billing: bool
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ProjectListResponse(BaseModel):
    projects: List[ProjectItem]


class TransitionProjectStatusRequest(BaseModel):
    status: str


class CreateMilestoneRequest(BaseModel):
    title: str = Field(..., min_length=1)
    due_date: date
    description: Optional[str] = None
    owner_employee_id: Optional[str] = None


class MilestoneItem(BaseModel):
    id: str
    project_id: str
    title: str
    description: Optional[str] = None
    due_date: date
    owner_employee_id: Optional[str] = None
    is_complete: str
    completion_date: Optional[date] = None
    delay_days: Optional[int] = None


class MilestoneListResponse(BaseModel):
    milestones: List[MilestoneItem]


class CompleteMilestoneRequest(BaseModel):
    completion_date: Optional[date] = None


class UnfilledRoleItem(BaseModel):
    demand_id: str
    job_title: str
    open_positions: int
    days_until_start: Optional[int] = None
    gap_status: str


class UnfilledRolesResponse(BaseModel):
    roles: List[UnfilledRoleItem]


class ExpectedRevenueResponse(BaseModel):
    expected_revenue_usd_cents: Optional[int] = None
    margin_usd_cents: Optional[int] = None
    margin_indicator: str
    note: str
