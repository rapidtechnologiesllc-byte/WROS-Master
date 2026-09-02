"""
Pydantic schemas for Work Order API (DEFECT-1: Work Order / PO Model)
import logging
"""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class CreateWorkOrderRequest(BaseModel):
    """Create a new Work Order."""
    po_number: str = Field(..., min_length=1, description="Client-assigned PO number")
    demand_id: str = Field(..., description="Demand ID")
    client_id: str = Field(..., description="Client ID (bill-to)")
    billing_rate_usd_cents: int = Field(..., ge=0, description="Billing rate to client in USD cents")
    start_date: date = Field(..., description="Work start date")
    sow_reference: Optional[str] = None
    employee_id: Optional[str] = None
    project_id: Optional[str] = None
    pay_rate_usd_cents: Optional[int] = Field(None, ge=0, description="Pay rate to employee in USD cents")
    end_date: Optional[date] = None
    invoicing_contact_email: Optional[str] = None
    invoicing_contact_name: Optional[str] = None


class UpdateWorkOrderRequest(BaseModel):
    """Update an existing Work Order (only mutable fields)."""
    pay_rate_usd_cents: Optional[int] = Field(None, ge=0, description="Pay rate to employee in USD cents")
    end_date: Optional[date] = None
    employee_id: Optional[str] = None
    project_id: Optional[str] = None
    invoicing_contact_email: Optional[str] = None
    invoicing_contact_name: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(ACTIVE|ENDED|PAUSED)$")


class WorkOrderItem(BaseModel):
    """Work Order response item."""
    id: str
    tenant_id: int
    po_number: str
    sow_reference: Optional[str] = None
    demand_id: str
    client_id: str
    employee_id: Optional[str] = None
    project_id: Optional[str] = None
    billing_rate_usd_cents: int
    pay_rate_usd_cents: Optional[int] = None
    start_date: date
    end_date: Optional[date] = None
    invoicing_contact_email: Optional[str] = None
    invoicing_contact_name: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WorkOrderListResponse(BaseModel):
    """List of work orders."""
    work_orders: List[WorkOrderItem]


class EndWorkOrderRequest(BaseModel):
    """End a work order."""
    end_date: Optional[date] = None


class PauseWorkOrderRequest(BaseModel):
    """Pause a work order."""
    pass


class ResumeWorkOrderRequest(BaseModel):
    """Resume a paused work order."""
    pass
