import logging
from app.core.logging import logger
"""Pydantic schemas -- HRMS-0907 (Invoice Generation, Status Tracking) API."""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class GenerateInvoiceRequest(BaseModel):
    project_id: str
    period_start: date
    period_end: date


class InvoiceLineItemItem(BaseModel):
    id: str
    employee_id: str
    timesheet_id: str
    hours: float
    rate_usd_cents: int
    amount_usd_cents: int


class InvoiceItem(BaseModel):
    id: str
    project_id: str
    client_id: str
    billing_period_start: date
    billing_period_end: date
    status: str
    total_usd_cents: int
    currency: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    line_items: List[InvoiceLineItemItem] = []


class InvoiceListResponse(BaseModel):
    invoices: List[InvoiceItem]
