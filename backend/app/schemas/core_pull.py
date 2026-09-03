"""
Pydantic schemas — S-353 (HRMS-0514) Core-Pull Engine + S-373 (HRMS-0529)
Specialty Pool Minimum 40 Guard API.
import logging
"""

import logging
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from app.core.logging import logger

logger = logging.getLogger(__name__)

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
