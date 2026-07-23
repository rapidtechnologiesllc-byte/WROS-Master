"""
Pydantic schemas — S-220/HRMS-0901 (Create Weekly Timesheet) + S-221
(Timesheet Validation & Submission Lock) + S-222/HRMS-0902 (Manager
Approval) API.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


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
