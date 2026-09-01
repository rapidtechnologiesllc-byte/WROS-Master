from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, func

from app.models.base import Base
from app.models.client import BILLING_CURRENCIES

# S-219/HRMS-0121: display format only -- storage is always ISO (Date/
# DateTime columns), this just controls how a date renders for this
# tenant's users.
TENANT_DATE_FORMATS = ("MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD")


class Tenant(Base):
    """
    Top-level data-isolation boundary (HRMS-0109). Every business-entity
    table scopes to a tenant, resolved server-side from the authenticated
    session -- never from client input. See app/core/tenant_context.py.
    """
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    is_active = Column(Boolean, nullable=False, default=True)

    # S-219/HRMS-0121 -- Multi-Continent Locale & Currency Config.
    # default_currency reuses BILLING_CURRENCIES (Client/Project/Invoice
    # already use it) -- it's a *display* preference only; every monetary
    # column in this codebase still stores USD cents as its base unit
    # (R-09), no FX conversion happens here. This codebase has no
    # exchange-rate table/source, so no actual USD-to-local conversion is
    # implemented -- inventing one would mean guessing real-world FX
    # rates, which is worse than not converting at all. Flagged, not
    # silently faked.
    # server_default (not just Python-side default=) so raw SQL inserts
    # that don't mention these columns -- e.g. the Alembic backfill this
    # migration ships alongside, or any other future raw INSERT -- still
    # satisfy the NOT NULL constraint, matching what the migration itself
    # already sets at the DB level.
    default_timezone = Column(String(256), nullable=False, default="UTC", server_default="UTC")
    default_date_format = Column(
        Enum(*TENANT_DATE_FORMATS, name="tenant_date_format", native_enum=False, create_constraint=True),
        nullable=False, default="MM/DD/YYYY", server_default="MM/DD/YYYY",
    )
    default_currency = Column(
        Enum(*BILLING_CURRENCIES, name="tenant_default_currency", native_enum=False, create_constraint=True),
        nullable=False, default="USD", server_default="USD",
    )
