"""
Pydantic schemas — S-251 (Allocate Employee to Project) + S-252
(Allocation Conflict Detection) API.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

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
    # Defaults to the job's client bill rate
    billing_rate_usd_cents: Optional[int] = None
    # None = the project's (client projects billable, internal projects not)
    billable: Optional[bool] = None
    # the client's timesheet approver for this placement (one of the client's TIMESHEET_APPROVER
    # contacts when it has any) and the client PO / work order it bills against
    timesheet_approver_email: Optional[str] = None
    work_order_id: Optional[str] = None


class PlacementBillingRequest(BaseModel):
    """PUT /allocations/{id}/client-billing: only the fields sent change; "" or null clears."""
    timesheet_approver_email: Optional[str] = None
    work_order_id: Optional[str] = None

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
    days_left: Optional[int] = None  # to end_date, from today
    ending_soon: bool = False  # active and inside the renewal-alert window, or rolling off
    role: Optional[str] = None
    billing_rate_usd_cents: Optional[int] = None
    work_location: Optional[str] = None
    assigned_recruiter_name: Optional[str] = None
    business_unit_name: Optional[str] = None
    created_at: datetime
    billable: bool = True
    project_name: Optional[str] = None
    renewal_status: Optional[str] = None
    renewal_owner_user_id: Optional[str] = None
    renewal_note: Optional[str] = None
    margin_pct: Optional[float] = None
    margin_check: Optional[str] = None
    # a change (or this placement) waiting for margin approval
    pending_change: Optional["AllocationChangeItem"] = None
    # the margin guard's verdict on create (flags NO_MARGIN_FLOOR_CONFIGURED etc.)
    margin: Optional["MarginCheck"] = None
    timesheet_approver_email: Optional[str] = None
    work_order_id: Optional[str] = None
    po_number: Optional[str] = None
    po_end_date: Optional[date] = None

class AllocationListResponse(BaseModel):
    allocations: List[AllocationItem]

class EndAllocationRequest(BaseModel):
    end_date: Optional[date] = None

class DropdownItem(BaseModel):
    id: str
    name: str

class JobDropdownItem(BaseModel):
    """A client job an employee can be allocated to (a job is the demand)."""
    id: str
    name: str
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    billing_rate_usd_cents: Optional[int] = None
    status: Optional[str] = None

class AllocationDropdownsResponse(BaseModel):
    employees: List[DropdownItem]
    demands: List[JobDropdownItem]


class MarginCheck(BaseModel):
    """The margin guard's verdict on a placement or proposed terms (margin_guard_service)."""
    margin_check: str
    margin_pct: Optional[float] = None
    loaded_hourly_cost_usd_cents: Optional[int] = None
    min_margin_pct: Optional[float] = None
    hard_floor_pct: Optional[float] = None
    margin_policy_id: Optional[int] = None
    delivery_engine: Optional[str] = None
    country: Optional[str] = None
    approval_level: Optional[str] = None
    message: str
    flags: List[str] = []


class MarginPreviewRequest(BaseModel):
    """Live margin in the allocation form: a new placement (employee + job) or an edit (allocation_id)."""
    employee_id: Optional[str] = None
    demand_id: Optional[str] = None
    project_id: Optional[str] = None
    allocation_id: Optional[str] = None
    billing_rate_usd_cents: Optional[int] = None
    billable: Optional[bool] = None
    start_date: Optional[date] = None
    role: Optional[str] = None


class AllocationChangeItem(BaseModel):
    id: str
    allocation_id: str
    change_type: str
    status: str
    old_values: Optional[Dict[str, Any]] = None
    new_values: Dict[str, Any]
    effective_from: Optional[date] = None
    reason: str
    changed_by_user_id: Optional[str] = None
    changed_by_name: Optional[str] = None
    changed_at: Optional[datetime] = None
    margin_pct: Optional[float] = None
    margin_check: Optional[str] = None
    min_margin_pct: Optional[float] = None
    hard_floor_pct: Optional[float] = None
    approval_level: Optional[str] = None
    approver_user_id: Optional[str] = None
    approver_name: Optional[str] = None
    task_id: Optional[int] = None
    decided_by_user_id: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_reason: Optional[str] = None


class AllocationHistoryResponse(BaseModel):
    changes: List[AllocationChangeItem]


class UpdateAllocationRequest(BaseModel):
    """PATCH /allocations/{id}: only the fields sent change (end_date: null = open-ended).
    effective_from: the Monday a new bill rate applies from (default: the first unbilled week)."""
    end_date: Optional[date] = None
    billing_rate_usd_cents: Optional[int] = None
    utilization_pct: Optional[float] = None
    billable: Optional[bool] = None
    effective_from: Optional[date] = None
    reason: str


class AllocationEditResponse(BaseModel):
    allocation: "AllocationItem"
    change: AllocationChangeItem


class MarginDecisionRequest(BaseModel):
    reason: str


class RenewalUpdateRequest(BaseModel):
    """Renewal status / owner / note. owner_user_id "" clears the owner (back to the default)."""
    renewal_status: Optional[str] = None
    owner_user_id: Optional[str] = None
    note: Optional[str] = None
    reason: Optional[str] = None


class RenewalItem(BaseModel):
    allocation_id: str
    employee_id: str
    employee_name: Optional[str] = None
    client_id: str
    client_name: Optional[str] = None
    job_title: Optional[str] = None
    role: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    days_left: Optional[int] = None
    billing_rate_usd_cents: Optional[int] = None
    utilization_pct: Optional[float] = None
    renewal_status: str
    renewal_note: Optional[str] = None
    renewal_owner_user_id: Optional[str] = None
    renewal_owner_name: Optional[str] = None
    renewal_owner_source: Optional[str] = None
    renewal_updated_at: Optional[datetime] = None
    margin_pct: Optional[float] = None
    margin_check: Optional[str] = None
    change_pending_approval: bool = False


class RenewalListResponse(BaseModel):
    days: int
    alert_days: List[int]
    renewals: List[RenewalItem]


class MarginApprovalListResponse(BaseModel):
    approvals: List[AllocationChangeItem]


AllocationItem.model_rebuild()
AllocationEditResponse.model_rebuild()
