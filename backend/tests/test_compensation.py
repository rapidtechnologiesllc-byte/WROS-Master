"""Pay as agreed (CEO 2026-10-24): an amount in the employee's currency per hour, month or year,
and the monthly USD cost every P&L figure reads, always derived from it."""
import pytest

from app.core.config import settings
from app.services import compensation


@pytest.fixture(autouse=True)
def _rates(monkeypatch):
    monkeypatch.setattr(settings, "FX_INR_PER_USD", 85.0)
    monkeypatch.setattr(settings, "FX_RATES_PER_USD_JSON", '{"GBP": 0.8}')
    monkeypatch.setattr(settings, "STANDARD_MONTHLY_HOURS", 173.33)


@pytest.mark.parametrize("amount, currency, basis, monthly_usd", [
    (12_000_000, "USD", "ANNUAL", 1_000_000),          # $120,000 a year -> $10,000 a month
    (1_000_000, "USD", "MONTHLY", 1_000_000),
    (5_000, "USD", "HOURLY", round(5_000 * 173.33)),   # $50/hour x standard monthly hours
    (102_000_000, "INR", "ANNUAL", round(102_000_000 / 12 / 85)),  # 10.2 lakh a year
    (80_000, "GBP", "MONTHLY", 100_000),
])
def test_monthly_usd_cost(amount, currency, basis, monthly_usd):
    assert compensation.monthly_usd_cents(amount, currency, basis) == monthly_usd


def test_a_currency_without_a_rate_leaves_the_cost_unknown():
    assert compensation.monthly_usd_cents(100_000, "EUR", "MONTHLY") is None


@pytest.mark.parametrize("amount, currency, basis", [
    (-1, "USD", "ANNUAL"), (None, "USD", "ANNUAL"), (100, "XYZ", "ANNUAL"), (100, "USD", "WEEKLY")])
def test_invalid_pay_is_refused(amount, currency, basis):
    with pytest.raises(compensation.PayError):
        compensation.validate(amount, currency, basis)


def test_set_pay_records_the_pay_and_the_cost():
    class Row:
        pass

    row = Row()
    compensation.set_pay(row, 102_000_000, "INR", "ANNUAL")
    assert (row.pay_amount_cents, row.pay_currency, row.pay_basis) == (102_000_000, "INR", "ANNUAL")
    assert row.base_salary_usd_cents == 100_000


def test_country_currency_comes_from_the_country_policy():
    from app.services.employment_type_policy import currency_of

    assert currency_of("IN") == "INR" and currency_of("US") == "USD" and currency_of("XX") is None
