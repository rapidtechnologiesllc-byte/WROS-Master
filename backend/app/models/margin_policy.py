"""Rate card / margin floor at placement (CEO 2026-10-23, gap 4).

One row per delivery engine (SPECIALITY = Staff Aug, CORE = direct client) and, optionally, per
delivery country (the employee's cost-object country, ISO 3166-1 alpha-2) and per role (matched
case-insensitively against the allocation's role). The most specific active row wins
(app.services.margin_guard_service.policy_for).

- min_margin_pct: below it, the placement waits for a BU Head (settings.BU_LEADER_MIN_LEVEL)
- hard_floor_pct: below it, a Partner (settings.PARTNER_MIN_LEVEL) must approve

Margin % = (bill rate - loaded hourly cost) / bill rate, the loaded cost from the CostBook
(revenue_chain_service). No row for a placement = no floor configured: allowed and flagged.
The numbers are Finance's to set on the P&L > Rate Card tab; nothing is seeded.
"""
from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, func,
)

from app.models.base import Base
from app.models.employee import DELIVERY_ENGINES


class MarginPolicy(Base):
    __tablename__ = "margin_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    delivery_engine = Column(Enum(*DELIVERY_ENGINES, name="margin_policy_engine", native_enum=False,
                                  create_constraint=True), nullable=False)
    # None = every country / every role
    country = Column(String(2), nullable=True)
    role = Column(String(200), nullable=True)
    min_margin_pct = Column(Numeric(6, 2), nullable=False)
    hard_floor_pct = Column(Numeric(6, 2), nullable=False)
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    updated_by = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("hard_floor_pct <= min_margin_pct", name="ck_margin_policy_hard_below_min"),
        CheckConstraint("min_margin_pct < 100 AND hard_floor_pct > -1000", name="ck_margin_policy_range"),
        # one row per engine x country x role (NULL = any): the lookup is never ambiguous
        Index("uq_margin_policy_scope", "tenant_id", "delivery_engine", func.coalesce(country, ""),
              func.lower(func.coalesce(role, "")), unique=True),
    )
