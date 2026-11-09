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


# ---- companies carry their share too (CEO 2026-11-09: "any income and expense will show in company level") ----

COMPANY_MONEY = ("revenue_usd_cents", "delivery_cost_usd_cents", "bench_cost_usd_cents", "overhead_cost_usd_cents",
                 "htd_cost_usd_cents", "expense_cost_usd_cents", "shared_cost_usd_cents", "total_cost_usd_cents")


@pytest.fixture
def companies(db, org):
    """Corporate and the BU of 15 in one company, the BU of 4 in another (like Poliqs)."""
    from app.models.employee_org_history import EmployeeOrgHistory
    from app.models.location import Location

    corp, big, small, _ = org
    main, sister = Location(tenant_id=1, name=f"Main-{uid()}"), Location(tenant_id=1, name=f"Sister-{uid()}")
    db.add_all([main, sister])
    db.flush()
    for unit, company in ((corp, main), (big, main), (small, sister)):
        ids = [e.id for e in db.query(Employee).filter_by(bu_id=unit.id)]
        db.query(Employee).filter(Employee.id.in_(ids)).update({"company_id": company.id}, synchronize_session=False)
        db.query(EmployeeOrgHistory).filter(EmployeeOrgHistory.employee_id.in_(ids)).update(
            {"company_id": company.id}, synchronize_session=False)
    db.commit()
    return main, sister


def _by_company(report):
    return {row["key"]: row for row in report["by_company"]}


def test_each_company_carries_corporate_for_its_own_people(db, org, companies):
    main, sister = companies
    report = pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1)
    rows = _by_company(report)
    pool = 300_000  # the one Corporate person
    assert rows[sister.id]["shared_cost_usd_cents"] == pytest.approx(pool * 4 / 19, abs=2)
    assert rows[main.id]["shared_cost_usd_cents"] == pytest.approx(pool * 15 / 19, abs=2)
    # the company that paid no longer carries it as its own staff cost
    assert rows[main.id]["overhead_cost_usd_cents"] + rows[main.id]["shared_cost_usd_cents"] \
        + rows[sister.id]["shared_cost_usd_cents"] == pytest.approx(5 * 300_000 + pool, abs=2)


def test_every_company_column_adds_up_to_the_group(db, org, companies):
    corp, *_ = org
    w = two_bu_world(db)
    db.add(ExpenseRecord(tenant_id=1, business_unit_id=corp.id, logged_by_user_id=w.org_user.UserID, expense_date=date(2026, 9, 10),
                         amount_usd_cents=190_000, purpose=EXPENSE_PURPOSES[0], expense_category=EXPENSE_CATEGORIES[0], receipt_ref="r",
                         description="Office", manager_approval_status="APPROVED"))
    db.commit()
    report = pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1)
    for field in COMPANY_MONEY:
        assert sum(row[field] for row in report["by_company"]) == report[field], field


def test_a_loan_covers_the_borrowers_own_costs_not_its_corporate_share(db, org, companies):
    main, sister = companies
    sister.funded_by_company_id = main.id
    db.commit()
    report = pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1)
    rows = _by_company(report)
    own = rows[sister.id]["total_cost_usd_cents"] - rows[sister.id]["shared_cost_usd_cents"]
    assert rows[sister.id]["shared_cost_usd_cents"] > 0
    assert rows[main.id]["loaned_out_usd_cents"] == own
    loan = next(row for row in report["company_loans"] if row["company_id"] == sister.id)
    assert loan["period_usd_cents"] == own


def test_a_slice_of_the_org_leaves_companies_without_a_partial_split(db, org, companies):
    _, big, *_ = org
    report = pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1, business_unit_ids={big.id})
    assert all(row["shared_cost_usd_cents"] == 0 for row in report["by_company"])
