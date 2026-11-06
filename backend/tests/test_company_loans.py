"""A company whose costs a sister company pays as a loan (CEO 2026-11-05): each company keeps its own
P&L and all roll up to the parent. The borrower carries the costs, the lender shows money lent and
no expense, and the parent's total counts them once."""
import pytest

from app.models.employee import Employee
from app.models.employee_org_history import EmployeeOrgHistory
from app.models.location import Location
from app.models.tenant import Tenant
from app.services.revenue_chain_service import CostBook, pnl
from tests.scope_fixtures import ApiClient, two_bu_world
from tests.test_billable import MONTH_END, MONTH_START, _person
from tests.test_core_certification import _uid, db  # noqa: F401 -- fixture
from tests.test_employee_import import world  # noqa: F401 -- fixture

COMPANIES = "/api/v1/api/admin/users-access-control/delivery-centers"


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _borrower(db, lender):
    company = Location(tenant_id=1, name=f"Borrower-{_uid()}", country="India", funded_by_company_id=lender.id)
    db.add(company)
    db.flush()
    return company


def _move_from_day_one(db, person, company):
    db.query(EmployeeOrgHistory).filter_by(employee_id=person.id).update({"company_id": company.id})
    db.query(Employee).filter_by(id=person.id).update({"company_id": company.id})
    db.commit()


def test_borrower_carries_the_cost_and_the_lender_shows_a_loan(db, world):
    person = _person(db, world, billable=False, status="ACTIVE")
    db.commit()
    before = pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1)
    lender_before = next(r for r in before["by_company"] if r["key"] == world.company.id)

    borrower = _borrower(db, world.company)
    _move_from_day_one(db, person, borrower)
    after = pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1)
    rows = {r["key"]: r for r in after["by_company"]}
    payroll = CostBook(db).period(person, MONTH_START, MONTH_END)

    assert payroll > 0
    assert after["total_cost_usd_cents"] == before["total_cost_usd_cents"]  # counted once at the parent
    assert rows[borrower.id]["total_cost_usd_cents"] == payroll
    assert rows[borrower.id]["funded_by"] == world.company.name
    assert rows[world.company.id]["overhead_cost_usd_cents"] == lender_before["overhead_cost_usd_cents"] - payroll
    assert rows[world.company.id]["loaned_out_usd_cents"] == payroll

    loan = next(row for row in after["company_loans"] if row["company_id"] == borrower.id)
    assert (loan["lender_id"], loan["period_usd_cents"]) == (world.company.id, payroll)
    since_joining = CostBook(db).period(person, person.joining_date, MONTH_END)
    assert loan["to_date_usd_cents"] == since_joining and loan["cost_data_complete"]


def test_a_slice_of_the_org_shows_no_loan_figure(db, world):
    _move_from_day_one(db, _person(db, world, billable=False, status="ACTIVE"), _borrower(db, world.company))
    report = pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1, business_unit_ids={world.unit.id})
    assert report["company_loans"] == []


def test_the_lender_must_be_a_self_funded_sister(db, api):
    w = two_bu_world(db)
    lender = Location(tenant_id=1, name=f"Lender-{_uid()}")
    db.add(lender)
    db.flush()
    borrower = _borrower(db, lender)
    db.commit()
    base = {"name": f"New-{_uid()}", "funded_by_company_id": lender.id}

    created = api.post(w.org_user, COMPANIES, json=base)
    assert created.status_code == 200, created.text
    assert db.get(Location, created.json()["id"]).funded_by_company_id == lender.id
    # no chains: a borrower cannot lend, a lender cannot borrow, nobody funds itself
    assert api.post(w.org_user, COMPANIES, json={**base, "funded_by_company_id": borrower.id}).status_code == 400
    other = Location(tenant_id=1, name=f"Other-{_uid()}")
    db.add(other)
    db.commit()
    assert api.put(w.org_user, f"{COMPANIES}/{lender.id}", json={"name": lender.name, "funded_by_company_id": other.id}).status_code == 409
    assert api.put(w.org_user, f"{COMPANIES}/{other.id}", json={"name": other.name, "funded_by_company_id": other.id}).status_code == 400
    # "" clears it
    cleared = api.put(w.org_user, f"{COMPANIES}/{borrower.id}", json={"name": borrower.name, "funded_by_company_id": ""})
    assert cleared.status_code == 200
    db.expire_all()
    assert db.get(Location, borrower.id).funded_by_company_id is None


def test_the_companies_list_names_the_legal_parent_and_the_lender(db, api):
    w = two_bu_world(db)
    lender = Location(tenant_id=1, name=f"Lender-{_uid()}")
    db.add(lender)
    db.flush()
    borrower = _borrower(db, lender)
    tenant = db.get(Tenant, 1)
    tenant.parent_company_name = "Parent Group Test"
    db.commit()
    body = api.get(w.org_user, f"{COMPANIES}?limit=500").json()
    assert body["parent_company"]["name"] == "Parent Group Test"
    row = next(c for c in body["delivery_centers"] if c["id"] == borrower.id)
    assert row["funded_by_company_name"] == lender.name
