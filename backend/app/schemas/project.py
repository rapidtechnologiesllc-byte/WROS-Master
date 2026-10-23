"""
Pydantic schemas -- HRMS-0801 (Project Lifecycle) + HRMS-0804
(Milestones) + HRMS-0805 (Unfilled Roles) + HRMS-0806 (Revenue
Estimate & Margin) + S-358/HRMS-0519 (SI Partner Tagging) API.
"""

import logging
from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class CreateProjectRequest(BaseModel):
    client_id: str
    name: str = Field(..., min_length=1)
    billing_type: str = "TIME_AND_MATERIALS"
    currency: str = "USD"
    continent: Optional[str] = None
    delivery_engine: str = "SPECIALITY"
    si_partner: Optional[str] = None
    # Backlog item, 2026-08-05: end_client is a Speciality/Staff-Aug
    # concept but never mandatory (Avinash's own words). client_partner
    # is the Core equivalent. business_type (T_AND_M/MANAGED_SERVICES/
    # PROJECT/POD/PILOT) is required for CORE, meaningless for
    # Speciality (which is implicitly Staff Aug, nothing to store) --
    # enforced at the API layer, see create_project_endpoint().
    end_client: Optional[str] = None
    client_partner: Optional[str] = None
    business_type: Optional[str] = None
    allow_weekend_billing: bool = False
    # False for an internal project: its allocations default to non-billable
    is_billable: bool = True
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    # The project manager (an internal user) who owns delivery
    manager_user_id: Optional[str] = None

class UpdateProjectRequest(BaseModel):
    """PATCH /projects/{id}: only the fields sent change. start_date, end_date and manager_user_id
    may be sent as null to clear them; name and billing_type cannot be cleared."""
    name: Optional[str] = Field(None, min_length=1)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    billing_type: Optional[str] = None
    manager_user_id: Optional[str] = None

class ProjectManagerOption(BaseModel):
    user_id: str
    name: Optional[str] = None
    email: str

class ProjectOptionsResponse(BaseModel):
    """The choices the Projects screen offers, from the backend's own lists (never hardcoded in JS)."""
    billing_types: List[str]
    business_types: List[str]
    statuses: List[str]
    status_transitions: Dict[str, List[str]]
    currencies_by_engine: Dict[str, List[str]]
    managers: List[ProjectManagerOption]

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
    end_client: Optional[str] = None
    client_partner: Optional[str] = None
    business_type: Optional[str] = None
    allow_weekend_billing: bool
    is_billable: bool = True
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    manager_user_id: Optional[str] = None
    manager_name: Optional[str] = None

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
