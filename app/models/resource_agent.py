"""
HRMS-1105 (canonical S-320, not S-274 as its `.docx` filename says --
confirmed against `WROS_Canonical_Backlog_S001-401.xlsx`) -- Resource
Management Agent.

bench_allocation_recommendations: the LLM-ranked, advisory-only output of
the 30-minute bench scan for non-conflicting (single-engine) matches. Per
BR-1105-02, this table is the ONLY thing this agent ever writes for a
match -- no `employee_allocations` row is ever created from a scan; only
an RM's explicit approval (approve_bench_recommendation(), which calls the
existing allocate_employee_to_project()) does that.
"""
import uuid

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func,
)

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


BENCH_RECOMMENDATION_STATUSES = ("PENDING_RM_REVIEW", "APPROVED", "REJECTED")


class BenchAllocationRecommendation(Base):
    __tablename__ = "bench_allocation_recommendations"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    demand_id = Column(String(36), ForeignKey("demands.id"), nullable=False, index=True)

    confidence_pct = Column(Numeric(5, 2), nullable=False)
    rationale = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="PENDING_RM_REVIEW")

    created_at = Column(DateTime, server_default=func.now())
    reviewed_by = Column(String(50), ForeignKey("users.UserID"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
