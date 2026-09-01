"""
HRMS-0XXX -- Work Order / PO / Engagement Records (FEATURE-2026-08-12T5)

A Work Order (aka PO, SOW, or Engagement Record) is the signed authority
to bill for a placed candidate/employee against a specific client demand.

Unlike Opportunity (revenue *estimate*), WorkOrder is revenue *authority*:
- PO number (signed by client)
- Rate terms (bill rate, pay rate, spread)
- Period (start/end dates)
- Named resource (the specific candidate/employee placed)
- Invoicing contact (bill-to address)

Linkage: Demand → Candidate → Employee → WorkOrder → Project → Revenue
- DIRECT-sourced demands (no Opportunity) must have a WorkOrder before billing
- Opportunity-sourced demands already have one (auto-created from Opportunity)
- WorkOrder drives Project creation when candidate converts to Employee
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Column, Date, DateTime, ForeignKey, Integer, String, func,
)

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # PO/SOW identification
    po_number = Column(String(512), nullable=False, index=True)  # Client-assigned PO
    sow_reference = Column(String(512), nullable=True)  # Optional SOW/statement of work URL or ID

    # Linkages
    demand_id = Column(String(512), ForeignKey("demands.id"), nullable=False, index=True)  # DIRECT or Opportunity-sourced
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=False, index=True)  # Bill-to client
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=True, index=True)  # Named resource on PO (nullable until hire)
    project_id = Column(String(512), ForeignKey("projects.id"), nullable=True, index=True)  # Auto-created when employee hired

    # Rate terms (USD cents, per WROS rules)
    billing_rate_usd_cents = Column(Integer, nullable=False)
    pay_rate_usd_cents = Column(Integer, nullable=True)  # Optiona: may be set after hire

    # Timeline
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # Open-ended if null

    # Invoicing contact
    invoicing_contact_email = Column(String(300), nullable=True)
    invoicing_contact_name = Column(String(512), nullable=True)

    # Status
    status = Column(String(512), nullable=False, default="ACTIVE")  # ACTIVE, ENDED, PAUSED, etc.

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
