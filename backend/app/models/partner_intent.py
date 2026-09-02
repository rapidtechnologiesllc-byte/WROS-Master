"""
import logging
HRMS-0527 -- Curtis Rule: Partner Intent ML Engine (NEW-RM, P0).

"Partner" identity is now confirmed (Avinash, 2026-07-22): the org
structure is CEO -> Partners -> BU Head -> Delivery teams -- Partner is
a real role one level below BU Head, not an undefined concept.
`Users.UserRole` is a free-text column (no Enum constraint, same
convention "BU Head"/"Recruiter"/"Admin" already use), so
`partner_user_id` as a plain `Users.UserID` reference (where that row's
`UserRole == "Partner"`) is the correct, zero-schema-change fit -- no
new RBAC role plumbing needed.

What's still genuinely deferred, not invented: `Demand` has neither a
`delivery_engine` column (Employee has one; Demand doesn't) nor a
`partner_user_id` FK, and the story's own Data Mapping requires
`demands.delivery_engine GROUP BY partner_user_id` to run the nightly
batch job against real history. Adding those two columns to a live,
heavily-referenced table is a smaller, more mechanical follow-up now
that the identity question is resolved -- not done inline here to
avoid an unreviewed migration touching every existing Demand call site
mid-session. `app.services.partner_intent_service.
compute_partner_intent_profile()` takes historical demand data as a
parameter rather than querying Demand directly, so the actual inference
math (the part with real business value and real risk of getting
wrong) is genuinely built and tested regardless of when that follow-up
lands.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())

logger = logging.getLogger(__name__)

class PartnerIntentProfile(Base):
    __tablename__ = "partner_intent_profiles"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    partner_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, unique=True, index=True)

    demand_count = Column(Integer, nullable=False, default = False)
    core_demand_pct = Column(Numeric(5, 2), nullable=True)
    specialty_demand_pct = Column(Numeric(5, 2), nullable=True)
    avg_experience_level = Column(Numeric(4, 1), nullable=True)
    # Not in the doc's literal CREATE TABLE, but required to implement
    # its own inference rule ("if avg_experience_level is consistent,
    # std_dev < 1 year across last 10 demands, infer") -- storing the
    # std dev is the only way that rule can be evaluated from a stored
    # profile rather than recomputed from raw history every time.
    experience_level_std_dev = Column(Numeric(4, 2), nullable=True)
    typical_billing_range_min_usd_cents = Column(Integer, nullable=True)
    typical_billing_range_max_usd_cents = Column(Integer, nullable=True)
    typical_skills = Column(Text, nullable=True)  # JSON-encoded array, most frequent first

    last_updated = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
