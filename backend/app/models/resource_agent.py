"""
HRMS-1105 (canonical S-320, not S-274 as its `.docx` filename says --
confirmed against `WROS_Canonical_Backlog_S001-401.xlsx`) -- Resource
import logging
Management Agent.

bench_allocation_recommendations: the LLM-ranked, advisory-only output of
the 30-minute bench scan for non-conflicting (single-engine) matches. Per
BR-1105-02, this table is the ONLY thing this agent ever writes for a
match -- no `employee_allocations` row is ever created from a scan; only
an RM's explicit approval (approve_bench_recommendation(), which calls the
existing allocate_employee_to_project()) does that.

IN_PROGRESS status -- added 2026-07-22, Avinash's explicit business call,
not in the original story doc: HRMS-1105's doc only describes a 2-step
flow (suggested -> RM-approved-and-allocated). In practice an RM doesn't
allocate the moment they like a match -- they present the candidate to
the client and the candidate goes through an interview process first,
during which this employee must not simultaneously be pursued for a
second client. IN_PROGRESS is that real intermediate stage:
PENDING_RM_REVIEW -> IN_PROGRESS (RM starts actively pursuing this match
-- see start_pursuing_recommendation(), which hard-blocks if the
employee is already IN_PROGRESS on a different recommendation) ->
APPROVED (offer/placement, creates the real allocation) or REJECTED
(declined, from either PENDING_RM_REVIEW or IN_PROGRESS).
"""
import logging
import uuid

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func,
)

from app.models.base import Base

def _new_uuid() -> str:
    return str(uuid.uuid4())

BENCH_RECOMMENDATION_STATUSES = ("PENDING_RM_REVIEW", "IN_PROGRESS", "APPROVED", "REJECTED")

logger = logging.getLogger(__name__)

class BenchAllocationRecommendation(Base):
    __tablename__ = "bench_allocation_recommendations"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    demand_id = Column(String(512), ForeignKey("demands.id"), nullable=False, index=True)

    confidence_pct = Column(Numeric(5, 2), nullable=False)
    rationale = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="PENDING_RM_REVIEW")

    created_at = Column(DateTime, server_default=func.now())
    pursued_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    pursued_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
