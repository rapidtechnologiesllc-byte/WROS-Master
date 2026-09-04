"""
Pydantic schemas — S-372 (HRMS-0528) Confirmed vs Potential Demand
Workflow API.
import logging
"""

import logging
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from app.core.logging import logger

logger = logging.getLogger(__name__)

class ConfirmSOWRequest(BaseModel):
    sow_reference: str = Field(..., min_length=1)
    sow_received_date: Optional[date] = None

class ConfirmSOWResponse(BaseModel):
    demand_id: str
    confirmation_status: str
    sow_reference: Optional[str] = None
    sow_received_date: Optional[date] = None

class ScheduleCallRequest(BaseModel):
    curtis_user_id: Optional[str] = None
    bu_head_user_id: Optional[str] = None

class AlignmentCallItem(BaseModel):
    id: str
    demand_id: str
    demand_job_title: str
    employee_id: str
    employee_name: str
    curtis_user_id: Optional[str] = None
    bu_head_user_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None

    employee_fit_confirmed: Optional[bool] = None
    employee_fit_confirmed_at: Optional[datetime] = None
    employee_fit_notes: Optional[str] = None

    bu_head_fit_confirmed: Optional[bool] = None
    bu_head_fit_confirmed_at: Optional[datetime] = None
    bu_head_fit_notes: Optional[str] = None

    specialty_client_release_triggered_at: Optional[datetime] = None

class AlignmentCallListResponse(BaseModel):
    calls: List[AlignmentCallItem]

class ConfirmFitRequest(BaseModel):
    participant: str = Field(..., pattern="^(EMPLOYEE|BU_HEAD)$")
    confirmed: bool
    notes: Optional[str] = None

class ConfirmFitResponse(BaseModel):
    message: str
    call: AlignmentCallItem

class TriggerReleaseResponse(BaseModel):
    message: str
    call: AlignmentCallItem
