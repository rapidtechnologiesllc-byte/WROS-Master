"""
Pydantic schemas — S-220/HRMS-0901 (Create Weekly Timesheet) + S-221
(Timesheet Validation & Submission Lock) + S-222/HRMS-0902 (Manager
Approval) API.
import logging
"""

import logging
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from app.core.logging import logger

logger = logging.getLogger(__name__)

class CreateWeeklyDraftRequest(BaseModel):
    allocation_id: str
    week_starting_date: date


class TimesheetEntryInput(BaseModel):
    entry_date: date
    hours: float = Field(..., ge=0, le=24)
    entry_type: str = "BILLABLE"  # BILLABLE | NON_BILLABLE | LEAVE | HOLIDAY
    notes: Optional[str] = None


class UpsertEntriesRequest(BaseModel):
    entries: List[TimesheetEntryInput]


class TimesheetEntryItem(BaseModel):
    id: str
    entry_date: date
    hours: float
    entry_type: str
    notes: Optional[str] = None


class TimesheetItem(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    allocation_id: str
    week_starting_date: date
    total_hours: float
    billable_hours: float
    non_billable_hours: float
    status: str
    submitted_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    entries: List[TimesheetEntryItem] = []


class TimesheetListResponse(BaseModel):
    timesheets: List[TimesheetItem]


class RejectTimesheetRequest(BaseModel):
    reason: str = Field(..., min_length=20)


class BulkApproveRequest(BaseModel):
    timesheet_ids: List[str]


class BulkApproveFailure(BaseModel):
    id: str
    reason: str


class BulkApproveResponse(BaseModel):
    approved: int
    failed: List[BulkApproveFailure]


# ---------------------------------------------------------------------------
# S-229/HRMS-0910 -- AI Time Entry Anomaly Detection
# ---------------------------------------------------------------------------

class AnomalyFlagItem(BaseModel):
    id: str
    timesheet_entry_id: str
    anomaly_type: str  # WEEKEND | OVER_12H | COMPLETED_PROJECT | DUPLICATE
    detected_at: Optional[datetime] = None


class AnomalyFlagsResponse(BaseModel):
    flags: List[AnomalyFlagItem]


# ---------------------------------------------------------------------------
# Timesheet Dispute Resolution
# ---------------------------------------------------------------------------

class RaiseDisputeRequest(BaseModel):
    raised_by: str  # RM | EMPLOYEE | CLIENT -- matches DISPUTE_RAISED_BY
    reason: str = Field(..., min_length=50)
    disputed_date: Optional[date] = None
    disputed_hours: Optional[float] = None


class ResolveDisputeRequest(BaseModel):
    resolution: str  # ADJUSTED | CONFIRMED
    resolution_notes: str
    adjusted_hours: Optional[float] = None


class DisputeItem(BaseModel):
    id: str
    timesheet_id: str
    raised_by: str
    raised_by_user_id: Optional[str] = None
    disputed_date: Optional[date] = None
    disputed_hours: Optional[float] = None
    original_hours: float
    reason: str
    status: str
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    adjusted_hours: Optional[float] = None


class DisputeListResponse(BaseModel):
    disputes: List[DisputeItem]
