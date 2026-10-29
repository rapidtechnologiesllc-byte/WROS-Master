"""What an employee is paid, and the monthly USD cost it means (CEO 2026-10-24).

Pay is kept as given: an amount in the employee's pay currency (by default their country's,
employment_type_policy.currency_of) per hour, month or year. Every cost calculation (CostBook, P&L,
bench cost) reads one number, Employee.base_salary_usd_cents = the monthly pay in USD, which is
always derived here: annual / 12, hourly x STANDARD_MONTHLY_HOURS, converted at the configured rate
(FX_INR_PER_USD, FX_RATES_PER_USD_JSON). A currency with no rate leaves the USD cost unknown, which
the P&L reports as missing cost, never as zero.
"""
import json
from typing import Optional

from app.core.config import settings
from app.models.client import BILLING_CURRENCIES

PAY_BASES = ("ANNUAL", "MONTHLY", "HOURLY")


class PayError(ValueError):
    pass


def units_per_usd(currency: str) -> Optional[float]:
    """How many of this currency make 1 USD; None when no rate is configured."""
    if currency == "USD":
        return 1.0
    if currency == "INR":
        return settings.FX_INR_PER_USD or None
    try:
        rates = json.loads(settings.FX_RATES_PER_USD_JSON or "{}")
    except ValueError as exc:
        raise PayError(f"FX_RATES_PER_USD_JSON is not valid JSON: {exc}") from exc
    rate = rates.get(currency)
    return float(rate) if rate else None


def validate(amount_cents: Optional[int], currency: Optional[str], basis: Optional[str]) -> None:
    if amount_cents is None or amount_cents < 0:
        raise PayError("Pay must be zero or more")
    if currency not in BILLING_CURRENCIES:
        raise PayError(f"Pay currency must be one of {list(BILLING_CURRENCIES)}")
    if basis not in PAY_BASES:
        raise PayError(f"Pay basis must be one of {list(PAY_BASES)}")


def monthly_usd_cents(amount_cents: int, currency: str, basis: str) -> Optional[int]:
    """The monthly USD cost of this pay; None when the currency has no rate."""
    validate(amount_cents, currency, basis)
    rate = units_per_usd(currency)
    if rate is None:
        return None
    monthly = {"ANNUAL": amount_cents / 12, "MONTHLY": amount_cents,
               "HOURLY": amount_cents * settings.STANDARD_MONTHLY_HOURS}[basis]
    return round(monthly / rate)


def set_pay(employee, amount_cents: int, currency: str, basis: str) -> None:
    """Record what the employee is paid and the monthly USD cost behind every P&L figure."""
    validate(amount_cents, currency, basis)
    employee.pay_amount_cents, employee.pay_currency, employee.pay_basis = amount_cents, currency, basis
    employee.base_salary_usd_cents = monthly_usd_cents(amount_cents, currency, basis)
