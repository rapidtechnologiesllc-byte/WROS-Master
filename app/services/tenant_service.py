"""
S-219/HRMS-0121 -- Multi-Continent Locale & Currency Config.

Per-tenant timezone, date-display-format, and default display currency.
This is display configuration only -- every monetary column in this
codebase already stores USD cents as its base unit (R-09), and this
module does not implement USD-to-local currency conversion since no
exchange-rate table/source exists anywhere in this codebase. Inventing
a hardcoded FX rate would be guessing at real-world numbers that go
stale immediately; better to leave it unconverted and flagged than
silently wrong.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.tenant import TENANT_DATE_FORMATS, Tenant
from app.models.client import BILLING_CURRENCIES


class InvalidTenantLocaleField(Exception):
    pass


def update_tenant_locale(
    db: Session, tenant: Tenant, *,
    default_timezone: Optional[str] = None,
    default_date_format: Optional[str] = None,
    default_currency: Optional[str] = None,
) -> Tenant:
    if default_date_format is not None and default_date_format not in TENANT_DATE_FORMATS:
        raise InvalidTenantLocaleField(
            f"default_date_format must be one of {TENANT_DATE_FORMATS}, got '{default_date_format}'."
        )
    if default_currency is not None and default_currency not in BILLING_CURRENCIES:
        raise InvalidTenantLocaleField(
            f"default_currency must be one of {BILLING_CURRENCIES}, got '{default_currency}'."
        )

    if default_timezone is not None:
        tenant.default_timezone = default_timezone
    if default_date_format is not None:
        tenant.default_date_format = default_date_format
    if default_currency is not None:
        tenant.default_currency = default_currency

    db.add(tenant)
    return tenant
