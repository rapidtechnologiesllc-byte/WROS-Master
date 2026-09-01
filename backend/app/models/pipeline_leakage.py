"""
S-243 (EPIC-02 Revenue Leakage Detection) -- real and distinct from the
already-shipped S-225/HRMS-0906 timesheet-based leakage
(RevenueLeakageFlag / revenue_leakage_time_layer, in app.models.revenue_leakage).

A 4-pattern engine per the confirmed EPIC-02/03 scoping note: stalled
opportunities, unfilled demand past need-date, unbilled time, and
sub-vendor cost overruns. Unbilled time reuses the already-shipped
HRMS-0906 detection rather than reimplementing it (BR-0906-01: "one
shared detection source") -- app.services.pipeline_leakage_service
wraps each active RevenueLeakageFlag as a PipelineLeakageFlag here so
it surfaces in the same EPIC-02 leakage list as the other 3 patterns,
linked back via revenue_leakage_flag_id rather than duplicating data.

Sub-vendor cost overruns are NOT built in this pass: no cost/budget/
rate field exists anywhere in the Sub-Vendor Portal domain (checked
SubVendorRequest, SubVendorSubmission, SubVendorAccount directly) to
compare an actual placement cost against. Building this pattern for
real needs a product decision on what "budget" means here (a per-
request max bill rate agreed with the vendor? an actual negotiated
placement fee?) before a field gets added -- flagged, not invented.
See pipeline_leakage_service.scan_subvendor_cost_overruns()'s own
docstring.
"""
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, func

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


LEAKAGE_PATTERN_TYPES = (
    "STALLED_OPPORTUNITY", "UNFILLED_DEMAND", "UNBILLED_TIME", "SUBVENDOR_COST_OVERRUN",
)


class PipelineLeakageFlag(Base):
    """One row per detected leakage signal. Polymorphic-lite via
    nullable FK columns, one per pattern type's source entity -- same
    established pattern as Task.candidate_id/document_id/interview_id/
    expense_id, not a generic entity_type/entity_id pair."""

    __tablename__ = "pipeline_leakage_flags"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    pattern_type = Column(
        Enum(*LEAKAGE_PATTERN_TYPES, name="leakage_pattern_type", native_enum=False, create_constraint=True),
        nullable=False, index=True,
    )
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)

    opportunity_id = Column(String(512), ForeignKey("opportunities.id"), nullable=True, index=True)
    demand_id = Column(String(512), ForeignKey("demands.id"), nullable=True, index=True)
    revenue_leakage_flag_id = Column(String(512), ForeignKey("revenue_leakage_time_layer.id"), nullable=True, index=True)
    sub_vendor_request_id = Column(String(512), ForeignKey("sub_vendor_requests.id"), nullable=True, index=True)

    estimated_impact_usd_cents = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)

    detected_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)
