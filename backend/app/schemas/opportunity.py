from datetime import date, datetime
import logging
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

logger = logging.getLogger(__name__)

class OpportunityCreateRequest(BaseModel):
    # probability_pct is deliberately NOT client-supplied -- 2026-08-12,
    # Avinash: win probability must be system-generated (stage-based
    # default, see opportunity_service.STAGE_PROBABILITY), never manual
    # entry. Server derives and stores it from `stage` on create/transition.
    client_id: str
    revenue_value_usd_cents: int
    currency: str = "USD"
    revenue_value_native: Optional[int] = None
    owner_employee_id: Optional[str] = None
    client_owner_id: Optional[str] = None  # a user (users.UserID); defaults to the caller
    expected_close_date: Optional[date] = None
    stage: str = "QUALIFICATION"
    # What is being sold (stored in opportunity_profiles)
    service: Optional[str] = None
    guidewire_module: Optional[str] = None
    client_type: Optional[str] = None
    pricing_model: Optional[str] = None

    # an unknown field is a screen/API mismatch: reject it instead of silently dropping data
    model_config = ConfigDict(extra="forbid")

class OpportunityItem(BaseModel):
    id: str
    client_id: str
    client_name: Optional[str] = None
    owner_employee_id: Optional[str] = None
    owner_name: Optional[str] = None
    client_owner_id: Optional[str] = None
    client_owner_name: Optional[str] = None
    service: Optional[str] = None
    guidewire_module: Optional[str] = None
    client_type: Optional[str] = None
    pricing_model: Optional[str] = None
    stage: str
    revenue_value_usd_cents: int
    revenue_value_native: Optional[int]
    currency: str
    probability_pct: int
    weighted_forecast_usd_cents: int
    expected_close_date: Optional[date]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class OpportunityListResponse(BaseModel):
    opportunities: list[OpportunityItem]

class OpportunityStageTransitionRequest(BaseModel):
    new_stage: str
    project_name: Optional[str] = None
    billing_type: str = "TIME_AND_MATERIALS"
    continent: Optional[str] = None

class OpportunityStageTransitionResponse(BaseModel):
    opportunity: OpportunityItem
    project_id: Optional[str] = None

class PipelineColumn(BaseModel):
    stage: str
    total_revenue_usd_cents: int
    total_weighted_forecast_usd_cents: int
    opportunities: list[OpportunityItem]

class PipelineResponse(BaseModel):
    columns: list[PipelineColumn]

class RoleDemandFromOpportunityRequest(BaseModel):
    job_title: str
    required_skills: str
    min_experience_years: float
    work_location: str
    quantity: int
    duration_hours: int
    billing_rate_usd_cents: int

    @field_validator("work_location")
    @classmethod
    def _work_location(cls, value: str) -> str:
        """Remote / onsite / hybrid (the jobs table only stores these); refused here with a
        clear message instead of failing in the database."""
        from app.models.user import JOB_WORK_LOCATIONS

        normalised = (value or "").strip().upper()
        if normalised not in JOB_WORK_LOCATIONS:
            raise ValueError(f"work_location must be one of {', '.join(JOB_WORK_LOCATIONS)}")
        return normalised

class RoleDemandFromOpportunityResponse(BaseModel):
    id: str
    client_id: str
    job_title: str
    status: str
    headcount: int
    billing_rate_usd_cents: Optional[int]
    revenue_potential_usd_cents: Optional[int]
    opportunity_id: Optional[str]

    class Config:
        from_attributes = True


class UpcomingRoleCreateRequest(BaseModel):
    """A role the client is about to need (raised before the contract): opens a potential job now."""
    title: str
    description: str
    skills: list[str]
    # how candidates hear the client described, e.g. "a mid-size P&C carrier"; never its name
    client_description: str
    positions: int = 1
    location: str = ""
    work_location: str = "REMOTE"
    employment_type: str = "FULLTIME"
    min_experience_years: Optional[float] = None
    target_start: Optional[date] = None
    likelihood_pct: Optional[int] = None
    auto_outreach: bool = True
    client_update_id: Optional[int] = None


class RoleOutreachItem(BaseModel):
    candidate_id: str
    candidate_name: str
    status: str
    match_score: Optional[int] = None
    subject: Optional[str] = None
    why_fit: Optional[str] = None
    composed_by: Optional[str] = None
    note: Optional[str] = None
    sent_at: Optional[datetime] = None


class UpcomingRoleItem(BaseModel):
    job_id: str
    title: str
    positions: int
    skills: list[str]
    work_location: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    client_description: str
    target_start: Optional[date] = None
    likelihood_pct: Optional[int] = None
    auto_outreach: bool
    job_status: Optional[str] = None
    confirmation_status: Optional[str] = None
    created_at: datetime
    outreach: list[RoleOutreachItem] = []


class UpcomingRoleListResponse(BaseModel):
    opportunity_id: str
    roles: list[UpcomingRoleItem]
