"""
Pydantic schemas — S-251 (Allocate Employee to Project) + S-252
(Allocation Conflict Detection) API.
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
    project_id: Optional[str] = None
    si_partner: Optional[str] = None
    status: str
    utilization_pct: Optional[float] = None
    start_date: date
    end_date: Optional[date] = None
    role: Optional[str] = None
    billing_rate_usd_cents: Optional[int] = None


class AllocationListResponse(BaseModel):
    allocations: List[AllocationItem]


class EndAllocationRequest(BaseModel):
    end_date: Optional[date] = None
