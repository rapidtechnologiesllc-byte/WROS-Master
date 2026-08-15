"""
Pydantic schemas — S-353 (HRMS-0514) Core-Pull Engine + S-373 (HRMS-0529)
Specialty Pool Minimum 40 Guard API.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SpecialtyPoolStatusResponse(BaseModel):
    pool_size: int
    below_minimum: bool
    at_edge: bool
    gap: int


class CorePullEventItem(BaseModel):
    id: str
    status: str
    detected_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    override_justification: Optional[str] = None
    overridden_by: Optional[str] = None
    overridden_at: Optional[datetime] = None

    employee_id: str
    employee_name: str

    core_demand_id: str
    core_demand_job_title: str


class CorePullEventQueueResponse(BaseModel):
    events: List[CorePullEventItem]


class ExecuteCorePullResponse(BaseModel):
    message: str
    event: CorePullEventItem
    specialty_pool_size_after: int


class OverrideCorePullRequest(BaseModel):
    justification: str = Field(..., min_length=1)


class OverrideCorePullResponse(BaseModel):
    message: str
    event: CorePullEventItem


class ReplacementPlanRequest(BaseModel):
    employee_id: str
    replacement_strategy: str = Field(..., min_length=1)
    expected_replacement_date: date


class ReplacementPlanResponse(BaseModel):
    id: str
    employee_id_moving: str
    replacement_strategy: str
    expected_replacement_date: date
    logged_by: Optional[str] = None
    logged_at: Optional[datetime] = None


# ============================================================================
# S-318: Core-Pull Conflict Resolution Schemas (User's Main Requirement)
# ============================================================================


class EvaluateCorePullRequest(BaseModel):
    """Request to evaluate if employee should be allocated to Core vs Specialty."""
    employee_id: str
    job_id: str


class EvaluateCorePullResponse(BaseModel):
    """Response with evaluation result and confidence."""
    status: str  # "error", "conflict_detected", "not_eligible", "eligible"
    employee_id: str
    job_id: str
    recommendation: Optional[str] = None  # "CORE", "SPECIALITY", or None
    confidence: int  # 0-100
    reasoning: str


class ApplyCorePullRuleRequest(BaseModel):
    """Request to apply Core-Pull rule to employee + demand pair."""
    employee_id: str
    core_demand_id: str


class ApplyCorePullRuleResponse(BaseModel):
    """Response with Core-Pull rule decision."""
    status: str  # "error", "no_conflict", "conflict_applies_core_wins"
    employee_id: str
    allocation_decision: Optional[str] = None  # "ELIGIBLE" or "CORE_WINS"
    reasoning: str


class ResolveConflictRequest(BaseModel):
    """Request to resolve a Core-Pull conflict."""
    resolution: str = Field(..., description="'EXECUTE', 'OVERRIDE', or 'MONITOR'")
    justification: Optional[str] = Field(None, description="Required for OVERRIDE")


class ResolveConflictResponse(BaseModel):
    """Response from conflict resolution."""
    status: str  # "success", "error"
    conflict_id: str
    resolution: str
    resolved_at: datetime
    message: str
    event_status: Optional[str] = None
