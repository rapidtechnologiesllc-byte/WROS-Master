"""CEO 2026-11-06: Rapid Consulting Group -> its companies. The P&L reads group first, then each company,
and the companies add up to the group."""
from app.models.location import Location
from app.models.tenant import Tenant
from app.services.revenue_chain_service import pnl
from tests.test_billable import MONTH_END, MONTH_START, _person
from tests.test_core_certification import _uid, db  # noqa: F401 -- fixture
from tests.test_employee_import import world  # noqa: F401 -- fixture

MONEY = ("revenue_usd_cents", "delivery_cost_usd_cents", "bench_cost_usd_cents", "overhead_cost_usd_cents",
         "htd_cost_usd_cents", "expense_cost_usd_cents", "total_cost_usd_cents")


def _report(db):
    return pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1)


def test_the_report_names_the_parent_company(db, world):
    tenant = db.get(Tenant, 1)
    original = tenant.parent_company_name
    tenant.parent_company_name = f"Parent-{_uid()}"
    db.flush()
    try:
        assert _report(db)["group"] == {"name": tenant.parent_company_name, "company_code": "1"}
    finally:
        tenant.parent_company_name = original
        db.flush()


def test_without_a_legal_name_the_parent_is_the_tenant(db, world):
    tenant = db.get(Tenant, 1)
    original = tenant.parent_company_name
    tenant.parent_company_name = None
    db.flush()
    try:
        assert _report(db)["group"]["name"] == tenant.name
    finally:
        tenant.parent_company_name = original
        db.flush()


def test_a_report_for_no_single_tenant_has_no_group(db, world):
    assert pnl(db, start=MONTH_START, end=MONTH_END)["group"] is None


def test_the_companies_add_up_to_the_group(db, world):
    _person(db, world, billable=False, status="ACTIVE")
    _person(db, world, billable=True, status="BENCH")
    db.commit()
    report = _report(db)
    assert report["total_cost_usd_cents"] > 0
    for field in MONEY:
        assert sum(row[field] for row in report["by_company"]) == report[field], field


def test_a_company_with_nothing_this_period_still_shows(db, world):
    idle = Location(tenant_id=1, name=f"Idle-{_uid()}", country="India")
    db.add(idle)
    db.commit()
    row = next(r for r in _report(db)["by_company"] if r["key"] == idle.id)
    assert row["total_cost_usd_cents"] == 0 and row["revenue_usd_cents"] == 0


def test_companies_keep_their_order_whatever_they_earned(db, world):
    first = Location(tenant_id=1, name=f"First-{_uid()}", country="India", company_seq=8001)
    second = Location(tenant_id=1, name=f"Second-{_uid()}", country="India", company_seq=8002)
    db.add_all([second, first])
    db.commit()
    keys = [r["key"] for r in _report(db)["by_company"]]
    assert keys.index(first.id) < keys.index(second.id)
    assert None not in keys[:-1]  # untagged work, if any, comes last


def test_a_business_unit_with_nothing_yet_and_its_partner_still_show(db, world):
    from app.models.business_unit import BusinessUnit
    from app.models.user import Users

    partner = Users(UserID=f"P-{_uid()}", UserName=f"Partner {_uid()}", UserEmail=f"{_uid()}@x.test", UserPassword="x",
                    UserRole="x", tenant_id=1, role_template_id=db.query(Users.role_template_id).filter(
                        Users.role_template_id.isnot(None)).first()[0])
    db.add(partner)
    db.flush()
    unit = BusinessUnit(tenant_id=1, name=f"Empty-{_uid()}", display_name="Empty", partner_user_id=partner.UserID)
    db.add(unit)
    db.commit()
    report = _report(db)
    row = next(r for r in report["by_business_unit"] if r["key"] == unit.id)
    assert row["name"] == unit.name and row["total_cost_usd_cents"] == 0
    by_partner = next(r for r in report["by_partner"] if r["key"] == partner.UserID)
    assert by_partner["name"] == partner.UserName and by_partner["revenue_usd_cents"] == 0


def test_a_retired_business_unit_is_left_out_when_it_has_nothing(db, world):
    from app.models.business_unit import BusinessUnit

    unit = BusinessUnit(tenant_id=1, name=f"Retired-{_uid()}", display_name="Retired", active=False)
    db.add(unit)
    db.commit()
    assert unit.id not in {r["key"] for r in _report(db)["by_business_unit"]}


def test_a_business_unit_slice_lists_only_that_unit(db, world):
    report = pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1, business_unit_ids={world.unit.id})
    assert {r["key"] for r in report["by_business_unit"]} <= {world.unit.id, None}


def test_each_companys_sub_vendor_cost_adds_up_to_the_group(db, world):
    report = _report(db)
    assert all("vendor_cost_usd_cents" in row for row in report["by_company"])
    assert sum(row["vendor_cost_usd_cents"] for row in report["by_company"]) == report["vendor_cost_usd_cents"]
