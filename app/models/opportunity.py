"""
HRMS-0207/0208/0209/0215 -- Opportunities, Phase 2 Domain 4.

The sales-side pipeline record, upstream of Demand. Per HRMS-0210's own
explicit business rule, a won opportunity's role demands land in the
*same* `demands` table as any other demand (`Demand.source_type` is a
tag, not a schema branch) -- see app.models.demand for the columns this
story added there.

Stage list is hardcoded here (QUALIFICATION/PROPOSAL/NEGOTIATION/WON/
LOST) as a reasonable default pipeline. HRMS-0208's own spec says this
should be configurable via HRMS-0115 system config so the Kanban
columns and this dropdown never drift apart -- HRMS-0115 doesn't exist
in this codebase, so this is a placeholder fixed list, not the real
config-driven mechanism the docs describe.

Same SQL-Server/SQLite-portable translation conventions as
app.models.client/demand: UUID as String(36),
Enum(native_enum=False, create_constraint=True).
"""
import uuid

from sqlalchemy import (
    Column, Date, DateTime, Enum, ForeignKey, Integer,
    String, func,
)

from app.models.base import Base
from app.models.client import BILLING_CURRENCIES


def _new_uuid() -> str:
    return str(uuid.uuid4())


OPPORTUNITY_STAGES = ("QUALIFICATION", "PROPOSAL", "NEGOTIATION", "WON", "LOST")
CLOSED_STAGES = ("WON", "LOST")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    client_id = Column(String(36), ForeignKey("clients.id"), nullable=False, index=True)
    owner_employee_id = Column(String(36), ForeignKey("employees.id"), nullable=True, index=True)

    stage = Column(
        Enum(*OPPORTUNITY_STAGES, name="opportunity_stage", native_enum=False, create_constraint=True),
        nullable=False, default="QUALIFICATION",
    )

    # HRMS-0207 BR-0207-01 / R-09: storage is always USD cents; the
    # native-currency figure is the entry/display convenience only.
    # Currency conversion itself (HRMS-0121) doesn't exist in this
    # codebase, so revenue_value_usd_cents is caller-supplied (already
    # converted), not computed here -- same posture as every other
    # HRMS-0121 stand-in this session.
    revenue_value_usd_cents = Column(Integer, nullable=False)
    revenue_value_native = Column(Integer, nullable=True)  # display only, in `currency` units
    currency = Column(
        Enum(*BILLING_CURRENCIES, name="opportunity_currency", native_enum=False, create_constraint=True),
        nullable=False, default="USD",
    )
    probability_pct = Column(Integer, nullable=False, default=0)

    expected_close_date = Column(Date, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
