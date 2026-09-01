"""
S-364/HRMS-0520 -- 30-Day Buddy Program: 35-KPI Framework & Tracking.

The 35 KPI definitions (name + category + number) are fixed, BU-Head-
approved platform config -- explicitly "Do NOT build KPI weighting
adjustable by recruiter" in the story's own Not-In-Scope section -- so
they're a Python constant (KPI_DEFINITIONS in the service module), not
an ORM-backed, app-editable table. Only the two tables that hold actual
per-hire, per-week data are modeled here.
"""
import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base

BUDDY_RECORD_STATUSES = ("IN_PROGRESS", "GRADUATED", "EXTENDED", "EXITED")
KPI_CATEGORIES = ("HR", "BUDDY", "RM")


def _new_uuid() -> str:
    return str(uuid.uuid4())


class BuddyProgramRecord(Base):
    __tablename__ = "buddy_program_records"

    id = Column(String(256), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    employee_id = Column(String(256), ForeignKey("employees.id"), nullable=False, index=True)
    buddy_engineer_user_id = Column(String(256), ForeignKey("users.UserID"), nullable=False)

    program_start_date = Column(Date, nullable=False)
    expected_end_date = Column(Date, nullable=False)
    actual_end_date = Column(Date, nullable=True)

    status = Column(String(20), nullable=False, default="IN_PROGRESS")
    extension_count = Column(Integer, nullable=False, default = False)
    extension_reason = Column(Text, nullable=True)
    bu_head_decision_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now())


class BuddyKPIScore(Base):
    """One row per (buddy_record_id, kpi_number, week_number) -- see
    app.services.buddy_program_service for the completeness/draft logic
    (all 35 required per week before a week counts toward anything)."""
    __tablename__ = "buddy_kpi_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    buddy_record_id = Column(String(256), ForeignKey("buddy_program_records.id"), nullable=False, index=True)

    kpi_number = Column(Integer, nullable=False)  # 1-35
    kpi_category = Column(String(10), nullable=False)  # one of KPI_CATEGORIES
    kpi_name = Column(String(256), nullable=False)
    score = Column(Integer, nullable=False)  # 1-5 per the doc's own field spec
    scored_by = Column(String(256), ForeignKey("users.UserID"), nullable=False)
    scored_date = Column(Date, nullable=False)
    week_number = Column(Integer, nullable=False)  # 1-4
    notes = Column(Text, nullable=True)
