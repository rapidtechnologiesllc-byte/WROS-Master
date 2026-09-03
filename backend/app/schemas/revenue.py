"""Pydantic schemas -- HRMS-0906 (Revenue Leakage Detection) +
HRMS-0903 (Timesheet-to-Revenue Reconciliation) + HRMS-0909 (Client
Revenue Realization Dashboard) API.
import logging
"""

import logging
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel
from app.core.logging import logger

logger = logging.getLogger(__name__)

class ScanLeakageRequest(BaseModel):
    project_id: str
    period_start: date
    period_end: date


class LogPartialBillingReasonRequest(BaseModel):
    reason: str


class LeakageFlagItem(BaseModel):
    id: str
    project_id: str
    period_start: date
    period_end: date
    approved_hours: float
    invoiced_hours: float
    unbilled_hours: float
    partial_billing_reason: Optional[str] = None
    detected_at: Optional[datetime] = None


class LeakageFlagsResponse(BaseModel):
    flags: List[LeakageFlagItem]


class ReconciliationAlertItem(BaseModel):
    id: str
    timesheet_id: str
    employee_id: str
    billable_hours: float
    status: str
    gap_detected_at: Optional[datetime] = None


class ReconciliationScanResponse(BaseModel):
    alerts: List[ReconciliationAlertItem]


class ReconciliationAlertsResponse(BaseModel):
    alerts: List[ReconciliationAlertItem]


class ClientRevenueDashboardResponse(BaseModel):
    earned_usd_cents: Optional[int] = None
    planned_usd_cents: Optional[int] = None
    billable_ratio_pct: Optional[float] = None
    burn_rate_pct: Optional[float] = None
    note: str
