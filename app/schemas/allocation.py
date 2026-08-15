"""
S-314 — Project Allocation Engine
Pydantic schemas for allocation APIs:
  - S-251 (Allocate Employee to Project)
  - S-252 (Allocation Conflict Detection)
  - S-314 (Project Allocation Engine with capacity checking)
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CreateAllocationRequest(BaseModel):
    employee_id: str
    demand_id: str
    # HRMS-0803 -- no REST caller ever passed this through before S-358's
    # Project API existed; nullable, since not every allocation traces
    # to a tracked project.
    project_id: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    utilization_pct: Optional[float] = None
    role: Optional[str] = None
    allow_concurrent: bool = False


class AllocationItem(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    demand_id: str
    demand_job_title: str
    client_id: str
    client_name: Optional[str] = None
    project_id: Optional[str] = None
    si_partner: Optional[str] = None
    status: str
    utilization_pct: Optional[float] = None
    start_date: date
    end_date: Optional[date] = None
    role: Optional[str] = None
    billing_rate_usd_cents: Optional[int] = None
    work_location: Optional[str] = None
    assigned_recruiter_name: Optional[str] = None
    business_unit_name: Optional[str] = None
    created_at: datetime


class AllocationListResponse(BaseModel):
    allocations: List[AllocationItem]


class EndAllocationRequest(BaseModel):
    end_date: Optional[date] = None


class DropdownItem(BaseModel):
    id: str
    name: str


class AllocationDropdownsResponse(BaseModel):
    employees: List[DropdownItem]
    demands: List[DropdownItem]


# S-314: Project Allocation Engine Schemas


class ProjectItem(BaseModel):
    """Project details for allocation dropdown."""
    id: str
    name: str
    client_id: str
    client_name: Optional[str] = None
    status: str
    delivery_engine: str
    si_partner: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    billing_type: str
    currency: str


class AvailableProjectsResponse(BaseModel):
    """Response for get_available_projects endpoint."""
    projects: List[ProjectItem] = Field(description="List of available projects")
    total_count: int = Field(description="Total number of projects returned")
    filtered_count: int = Field(
        description="Number of projects after applying employee conflict filters, if applicable"
    )


class CapacityCheckRequest(BaseModel):
    """Request for checking employee allocation capacity."""
    employee_id: str = Field(description="Employee ID to check capacity for")
    additional_utilization_pct: float = Field(
        default=100.0,
        ge=0.0,
        le=100.0,
        description="Proposed utilization percentage (0-100%)"
    )
    proposed_start_date: Optional[date] = Field(
        default=None,
        description="Start date for proposed allocation (defaults to today)"
    )


class CapacityCheckResponse(BaseModel):
    """Response for capacity check endpoint."""
    employee_id: str
    has_capacity: bool = Field(
        description="True if employee can accept the proposed allocation"
    )
    current_utilization_pct: float = Field(
        description="Current utilization percentage across all active allocations"
    )
    available_capacity_pct: float = Field(
        description="Remaining capacity after proposed allocation"
    )
    total_with_proposed_pct: float = Field(
        description="Total utilization if proposed allocation is accepted"
    )
    active_allocation_count: int = Field(
        description="Number of active allocations for this employee"
    )


class AllocationCheckRequest(BaseModel):
    """Request for comprehensive allocation check before creating."""
    employee_id: str
    project_id: Optional[str] = None
    demand_id: str
    utilization_pct: Optional[float] = None
    proposed_start_date: Optional[date] = None
    allow_concurrent: bool = False


class AllocationCheckResponse(BaseModel):
    """Response for pre-allocation validation check."""
    is_valid: bool = Field(description="Whether allocation can proceed")
    employee_id: str
    employee_name: str
    has_capacity: bool = Field(description="Capacity check result")
    current_utilization_pct: float
    available_capacity_pct: float
    proposed_utilization_pct: float
    conflict_reasons: List[str] = Field(
        default_factory=list,
        description="List of reasons why allocation cannot proceed (if is_valid=False)"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-blocking warnings about the allocation"
    )
