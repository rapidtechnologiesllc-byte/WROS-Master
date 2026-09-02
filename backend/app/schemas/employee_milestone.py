import logging
"""Pydantic schemas -- S-356/HRMS-0517 (Employee Milestone Tracker) API."""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class CreateEmployeeMilestoneRequest(BaseModel):
    milestone_type: str  # PERSONAL | PROJECT | ORG
    title: str = Field(..., min_length=1)
    target_date: date
    project_id: Optional[str] = None
    employee_id: Optional[str] = None
    description: Optional[str] = None


class EmployeeMilestoneItem(BaseModel):
    id: str
    project_id: Optional[str] = None
    employee_id: Optional[str] = None
    milestone_type: str
    title: str
    description: Optional[str] = None
    target_date: date
    completed_date: Optional[date] = None
    status: str
    completion_notes: Optional[str] = None
    set_by: Optional[str] = None


class EmployeeMilestoneListResponse(BaseModel):
    milestones: List[EmployeeMilestoneItem]


class CompleteEmployeeMilestoneRequest(BaseModel):
    completion_notes: Optional[str] = None


class ScanOverdueMilestonesResponse(BaseModel):
    overdue: List[EmployeeMilestoneItem]
