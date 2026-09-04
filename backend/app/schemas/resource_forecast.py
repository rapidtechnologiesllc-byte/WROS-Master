"""
Pydantic schemas — S-256/HRMS-0506 (canonical) Resource Demand
Planning / Future Demand vs Bench Forecast API.
import logging
"""

import logging
from datetime import date
from typing import List

from pydantic import BaseModel
from app.core.logging import logger

logger = logging.getLogger(__name__)

class ExpiringAllocationItem(BaseModel):
    employee_id: str
    employee_name: str
    skills: List[str]
    allocation_id: str
    demand_id: str
    client_id: str
    end_date: date
    days_out: int

class ExpiringAllocationsResponse(BaseModel):
    under_30_days: List[ExpiringAllocationItem]
    thirty_to_60_days: List[ExpiringAllocationItem]
    sixty_to_90_days: List[ExpiringAllocationItem]

class SkillGapRow(BaseModel):
    skill: str
    current_bench_count: int
    expiring_allocations_count_30d: int
    total_projected_supply: int
    open_demand_count: int
    gap: int

class SkillGapAnalysisResponse(BaseModel):
    rows: List[SkillGapRow]
