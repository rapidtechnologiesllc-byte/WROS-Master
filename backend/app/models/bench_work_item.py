"""Bench work items (CEO 2026-11-11): what an employee who is not on client work logs their time
against -- an accelerator, a certification, or another piece of work the BU head approved. Time
on the bench is never free-floating: every hour names the item it went to.

A work item belongs to a business unit (None = every business unit) and exists only once a BU
leader has approved it: creating one is that approval (approved_by_user_id), so there is no
pending state to chase. Closing it stops new time; the time already logged stays.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base

# What kind of bench work it is: the grouping shown on timesheets and in bench reports
WORK_ITEM_CATEGORIES = {
    "ACCELERATOR": "Accelerator",
    "CERTIFICATION": "Certification",
    "APPROVED_WORK": "BU head approved work",
}
WORK_ITEM_STATUSES = ("ACTIVE", "CLOSED")


def _new_uuid() -> str:
    return str(uuid.uuid4())


class BenchWorkItem(Base):
    __tablename__ = "bench_work_items"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    # the business unit whose bench works on it; None = open to every business unit
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)
    name = Column(String(300), nullable=False)
    category = Column(String(30), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(10), nullable=False, default="ACTIVE", server_default="ACTIVE")
    # the BU leader who approved it (creating the item is the approval)
    approved_by_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
