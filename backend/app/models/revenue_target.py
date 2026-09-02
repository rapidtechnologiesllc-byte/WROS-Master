"""
import logging
S-267/HRMS-0301 (Set BU Revenue Target) + net-new PartnerGoal.

Avinash's explicit 2026-08-05 direction, overriding S-267's own written
BR for the Partner-level goal specifically: "Ceo sets the target that's
why the agent should think and work like avinash." BU-level targets
stay BU Head/Director/Admin-settable per S-267's own doc; PartnerGoal
is CEO-set only, enforced in the service layer, not the model.

Both append-only (S-267 BR: "Target Cannot Be Deleted -- Only
Superseded") -- no update/delete path, only new rows; the active
target for a period is the most recent by primary key, NOT created_at.

Deliberate deviation from this codebase's usual String(36) UUID
primary key convention: these two tables are genuinely an ordered
ledger (append-only, "most recent wins"), and a wall-clock `created_at`
tiebreak is not safe for that -- two targets set for the same period in
rapid succession (a real scenario: someone corrects a typo seconds
after submitting) can land in the same instant on some platforms/under
load, confirmed by reproducing it directly, not theoretical. A real
autoincrement integer primary key is the only thing that gives a
portable (SQLite + SQL Server), DB-guaranteed strict insertion order --
a UUID has none, and a secondary non-PK "sequence" column doesn't
reliably autoincrement outside the primary-key position in either
dialect. `id` is used only as a stable identifier here, same as it
would be as a UUID everywhere else in this codebase.
"""
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, func

from app.models.base import Base

TARGET_PERIODS = ("Q1", "Q2", "Q3", "Q4", "H1", "H2", "ANNUAL")

logger = logging.getLogger(__name__)

class BURevenueTarget(Base):
    __tablename__ = "bu_revenue_targets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=False, index=True)
    target_period = Column(Enum(*TARGET_PERIODS, name="bu_target_period", native_enum=False, create_constraint=True), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    target_amount_usd_cents = Column(Integer, nullable=False)
    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    notes = Column(Text, nullable=True)


class PartnerGoal(Base):
    __tablename__ = "partner_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    partner_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)
    target_period = Column(Enum(*TARGET_PERIODS, name="partner_target_period", native_enum=False, create_constraint=True), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    target_amount_usd_cents = Column(Integer, nullable=False)
    # CEO-only, enforced in revenue_target_service.set_partner_goal() --
    # not a DB constraint, since "is this user the CEO" is an RBAC
    # question, not a schema one.
    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    notes = Column(Text, nullable=True)
