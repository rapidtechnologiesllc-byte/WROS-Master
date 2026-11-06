"""Corporate earns no income, so its cost is shared across every other business unit by employee headcount,
billable or not (CEO 2026-11-05): 15 employees carry 15 shares, 4 carry 4, none carries nothing."""
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnit
from app.models.employee import Employee
from app.models.expense import EXPENSE_CATEGORIES, EXPENSE_PURPOSES, ExpenseRecord
from app.services.financial_outlook_service import outlook
from app.services.revenue_chain_service import CostBook, headcount_weights, pnl, prorated_shares
from tests.scope_fixtures import ApiClient, two_bu_world, uid

MONTH_START, MONTH_END = date(2026, 9, 1), date(2026, 9, 30)


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _unit(db, *, corporate=False):
    name = uid()
    unit = BusinessUnit(tenant_id=1, name=f"U-{name}", display_name=name, bu_code=name[:12], is_corporate=corporate)
    db.add(unit)
    db.flush()
    return unit


def _people(db, unit, count, *, billable=False, status="ACTIVE"):
    out = []
    for _ in range(count):
        person = Employee(tenant_id=1, first_name="P", last_name=uid(), email=f"{uid()}@bx.test", joining_date=date(2025, 1, 1),
                          status=status, bu_id=unit.id, is_billable=billable, base_salary_usd_cents=300_000,
                          buddy_program_status="GRADUATED")
        db.add(person)
        out.append(person)
    db.flush()
    return out


@pytest.fixture
def org(db, monkeypatch):
    """Corporate of 1 and BUs of 15, 4 and 0, with a fixed cost per person for the month."""
    monkeypatch.setattr(CostBook, "monthly", lambda self, employee, on=None: 300_000 if employee else None)
    two_bu_world(db)  # the tenant
    corp, big, small, empty = _unit(db, corporate=True), _unit(db), _unit(db), _unit(db)
    _people(db, corp, 1)
    _people(db, big, 10, billable=True, status="BENCH")
    _people(db, big, 5)
    _people(db, small, 4)  # none billable: still four heads
    db.commit()
    return corp, big, small, empty


def _rows(report):
    return {row["key"]: row for row in report["by_business_unit"]}


def test_shares_follow_every_employee_not_only_the_billable(db, org):
    corp, big, small, empty = org
    report = pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1)
    rows = _rows(report)
    assert rows[big.id]["shared_cost_usd_cents"] * 4 == pytest.approx(rows[small.id]["shared_cost_usd_cents"] * 15, abs=20)
    assert empty.id not in rows or rows[empty.id]["shared_cost_usd_cents"] == 0
    assert rows.get(corp.id, {}).get("overhead_cost_usd_cents", 0) == 0  # nothing is left on Corporate
    assert {"name": "Corporate", "cost_usd_cents": 300_000} in report["org_staff_by_function"]


def test_the_org_total_does_not_change_and_nothing_is_lost(db, org):
    corp, *_ = org
    report = pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1)
    assert sum(row["shared_cost_usd_cents"] for row in report["by_business_unit"]) == report["shared_cost_usd_cents"]
    corp.is_corporate = False
    db.commit()
    plain = pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1)
    assert plain["total_cost_usd_cents"] == report["total_cost_usd_cents"]


def test_a_partners_view_shows_the_same_share_as_the_ceos(db, org):
    _, big, *_ = org
    whole = _rows(pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1))[big.id]["shared_cost_usd_cents"]
    scoped = _rows(pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1, business_unit_ids={big.id}))[big.id]
    assert whole > 0 and scoped["shared_cost_usd_cents"] == whole


def test_someone_who_joined_mid_month_counts_for_their_days(db, org):
    _, big, small, _ = org
    late = _people(db, small, 1)[0]
    late.joining_date = date(2026, 9, 16)
    db.commit()
    weights = headcount_weights(db, start=MONTH_START, end=MONTH_END, tenant_id=1, costs=CostBook(db), corporate=set())
    assert weights[big.id] == 15 * 30 and weights[small.id] == 4 * 30 + 15


def test_people_not_yet_joined_or_gone_do_not_count(db, org):
    _, _, small, _ = org
    before = headcount_weights(db, start=MONTH_START, end=MONTH_END, tenant_id=1, costs=CostBook(db), corporate=set())[small.id]
    _people(db, small, 1, status="PRE_JOINING")
    _people(db, small, 1, status="EXITED")
    db.commit()
    after = headcount_weights(db, start=MONTH_START, end=MONTH_END, tenant_id=1, costs=CostBook(db), corporate=set())[small.id]
    assert after == before


def test_a_corporate_expense_is_shared_the_same_way(db, org):
    corp, big, small, _ = org
    w = two_bu_world(db)
    db.add(ExpenseRecord(tenant_id=1, business_unit_id=corp.id, logged_by_user_id=w.org_user.UserID, expense_date=date(2026, 9, 10),
                         amount_usd_cents=190_000, purpose=EXPENSE_PURPOSES[0], expense_category=EXPENSE_CATEGORIES[0], receipt_ref="r",
                         description="Office", manager_approval_status="APPROVED"))
    db.commit()
    rows = _rows(pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1))
    assert rows[big.id]["expense_cost_usd_cents"] > rows[small.id]["expense_cost_usd_cents"] > 0
    assert corp.id not in rows or rows[corp.id]["expense_cost_usd_cents"] == 0


def test_the_forecast_shares_corporate_the_same_way(db, org):
    corp, big, small, _ = org
    report = outlook(db, start=MONTH_START, end=MONTH_END, tenant_id=1, today=date(2026, 9, 15))
    rows = {row["key"]: row for row in report["by_business_unit"]}
    assert corp.id not in rows
    extra = rows[small.id]["anticipated_expense"] - 4 * 300_000
    assert extra == pytest.approx(300_000 * 4 / sum_heads(db, corp), rel=0.01)


def sum_heads(db, corp):
    weights = headcount_weights(db, start=MONTH_START, end=MONTH_END, tenant_id=1, costs=CostBook(db), corporate={corp.id})
    return sum(weights.values()) / 30


def test_prorated_shares_add_up_exactly():
    shares = prorated_shares(100, {1: 1, 2: 1, 3: 1})
    assert sum(shares.values()) == 100 and sorted(shares.values()) == [33, 33, 34]
    assert prorated_shares(0, {1: 15, 2: 4}) == {1: 0, 2: 0}


def test_the_form_sets_and_shows_corporate(db, api):
    w = two_bu_world(db)
    db.commit()
    created = api.post(w.org_user, "/api/v1/rbac/business-units", json={"name": f"Corp-{uid()}", "is_corporate": True})
    assert created.status_code == 200, created.text
    bu_id = created.json()["id"]
    assert api.get(w.org_user, f"/api/v1/rbac/business-units/{bu_id}").json()["is_corporate"] is True
    assert api.put(w.org_user, f"/api/v1/rbac/business-units/{bu_id}", json={"is_corporate": False, "name": ""}).status_code == 200
    assert api.get(w.org_user, f"/api/v1/rbac/business-units/{bu_id}").json()["is_corporate"] is False
