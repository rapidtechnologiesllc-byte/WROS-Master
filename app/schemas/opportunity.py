from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class OpportunityCreateRequest(BaseModel):
    client_id: str
    revenue_value_usd_cents: int
    probability_pct: int
    currency: str = "USD"
    revenue_value_native: Optional[int] = None
    owner_employee_id: Optional[str] = None
    expected_close_date: Optional[date] = None
    stage: str = "QUALIFICATION"


class OpportunityItem(BaseModel):
    id: str
    client_id: str
    client_name: Optional[str] = None
    owner_employee_id: Optional[str] = None
    owner_name: Optional[str] = None
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
