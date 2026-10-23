"""Cost object = business unit x location (CEO 2026-10-22): rates per BU and country with a
fallback order, each day charged to where the employee sat that day, so moving someone never
rewrites a past month; the P&L has location and cost-object views that reconcile with the bench
screen."""
from datetime import date, timedelta

from app.models.business_unit import BusinessUnit
from app.models.cost_rate_config import CostRateConfig
from app.models.employee import Employee
from app.models.employee_org_history import EmployeeOrgHistory
from app.models.location import Location
from app.services.bench_service import bench_report, reconcile_bench_pool
from app.services.cost_rate_service import get_active_cost_rate_config
from app.services.revenue_chain_service import CostBook, month_bounds, pnl
from tests.test_core_certification import _h, _uid, db  # noqa: F401 -- fixtures
from tests.test_employee_import import api, mail, world  # noqa: F401 -- fixtures

TODAY = date.today()
LAST_MONTH = month_bounds((TODAY.replace(day=1) - timedelta(days=1)).year,
                          (TODAY.replace(day=1) - timedelta(days=1)).month)


def _rate(db, world, statutory, *, bu=None, country=None, effective=date(2024, 1, 1)):
    db.add(CostRateConfig(business_unit_id=bu, country=country, statutory_pct=statutory, overhead_pct=0,
                          effective_date=effective, created_by=world.hr.UserID))
    db.flush()


def test_rate_lookup_order_and_effective_dates(db, world):
    other = BusinessUnit(tenant_id=1, name=f"o-{_uid()}", display_name="Other")
    db.add(other)
    db.flush()
    _rate(db, world, 30, bu=world.unit.id, country="IN")
    _rate(db, world, 20, country="IN")
    _rate(db, world, 15, bu=other.id)
    assert float(get_active_cost_rate_config(db, business_unit_id=world.unit.id, country="IN").statutory_pct) == 30
    assert float(get_active_cost_rate_config(db, business_unit_id=other.id, country="IN").statutory_pct) == 20
    assert float(get_active_cost_rate_config(db, business_unit_id=other.id, country="US").statutory_pct) == 15
    _rate(db, world, 40, bu=world.unit.id, country="IN", effective=TODAY)
    assert float(get_active_cost_rate_config(db, business_unit_id=world.unit.id, country="IN",
                                             on=TODAY - timedelta(days=1)).statutory_pct) == 30
    assert float(get_active_cost_rate_config(db, business_unit_id=world.unit.id, country="IN",
                                             on=TODAY).statutory_pct) == 40


def _employee(db, world, **extra):
    e = Employee(tenant_id=1, first_name="Mo", last_name=_uid(), email=f"{_uid()}@bx.test",
                 joining_date=date(2025, 1, 1), status="BENCH", bu_id=world.unit.id, company_id=world.company.id,
                 base_salary_usd_cents=300_000, buddy_program_status="GRADUATED", **extra)
    db.add(e)
    db.commit()
    return e


def test_history_is_written_on_create_and_on_every_move(db, world):
    e = _employee(db, world)
    rows = db.query(EmployeeOrgHistory).filter_by(employee_id=e.id).all()
    assert [(r.bu_id, r.country, r.effective_from) for r in rows] == [(world.unit.id, "IN", date(2025, 1, 1))]
    us = Location(tenant_id=1, name=f"BX-US-{_uid()}", country="United States")
    db.add(us)
    db.flush()
    e.company_id = us.id
    db.commit()
    rows = db.query(EmployeeOrgHistory).filter_by(employee_id=e.id).order_by(EmployeeOrgHistory.id).all()
    assert [(r.country, r.effective_from) for r in rows][-1] == ("US", TODAY)


def test_a_first_move_without_history_keeps_the_past(db, world):
    e = _employee(db, world)
    db.query(EmployeeOrgHistory).filter_by(employee_id=e.id).delete()  # an employee from before history
    db.commit()
    other = BusinessUnit(tenant_id=1, name=f"o-{_uid()}", display_name="Other")
    db.add(other)
    db.flush()
    e.bu_id = other.id
    db.commit()
    rows = db.query(EmployeeOrgHistory).filter_by(employee_id=e.id).order_by(EmployeeOrgHistory.effective_from).all()
    assert [(r.bu_id, r.effective_from) for r in rows] == [(world.unit.id, date(2025, 1, 1)), (other.id, TODAY)]


def test_moving_an_employee_never_rewrites_last_month(api, db, world):
    e = _employee(db, world)
    other = BusinessUnit(tenant_id=1, name=f"o-{_uid()}", display_name="Other")
    db.add(other)
    _rate(db, world, 10)  # the company-wide default the new BU falls back to
    db.commit()
    before = pnl(db, start=LAST_MONTH[0], end=LAST_MONTH[1], tenant_id=1)
    res = api.put(f"/api/v1/employees/{e.id}/organization", headers=_h(world.hr), json={"business_unit_id": other.id})
    assert res.status_code == 200, res.text
    after = pnl(db, start=LAST_MONTH[0], end=LAST_MONTH[1], tenant_id=1)
    unit = lambda report, bu: next((r for r in report["by_business_unit"] if r["key"] == bu), {})  # noqa: E731
    assert unit(after, world.unit.id)["bench_cost_usd_cents"] == unit(before, world.unit.id)["bench_cost_usd_cents"]
    assert not unit(after, other.id) or unit(after, other.id)["bench_cost_usd_cents"] == 0
    this_month = pnl(db, start=TODAY, end=TODAY, tenant_id=1)
    assert unit(this_month, other.id)["bench_cost_usd_cents"] > 0  # from the move on, the new BU pays


def test_each_country_is_charged_at_its_own_rate(db, world):
    _rate(db, world, 50, bu=world.unit.id, country="IN")
    e = _employee(db, world)
    cost = CostBook(db).monthly(e)
    assert cost == 300_000 + 150_000  # BU + India: 50% statutory, no overhead (not the BU default's 10% + 10%)


def test_bench_screen_reconciles_with_the_pnl_per_bu_and_location(db, world, mail):
    since = TODAY - timedelta(days=20)
    people = [_employee(db, world) for _ in range(2)]
    reconcile_bench_pool(db)
    for p in people:
        from app.models.resource_management import BenchPoolEntry
        db.query(BenchPoolEntry).filter_by(employee_id=p.id).update({"available_from": since})
    db.commit()
    report = bench_report(db, world.hr, business_unit_id=world.unit.id)
    by_object = {}
    for r in report["employees"]:
        by_object[(r["business_unit_id"], r["country"])] = by_object.get((r["business_unit_id"], r["country"]), 0) \
            + r["bench_loss_usd_cents"]
    period = pnl(db, start=since, end=TODAY, tenant_id=1)
    pnl_objects = {(row["business_unit_id"], row["country"]): row["bench_cost_usd_cents"] for row in period["by_cost_object"]}
    assert by_object == {(world.unit.id, "IN"): pnl_objects[(world.unit.id, "IN")]}
    india = pnl(db, start=since, end=TODAY, tenant_id=1, country="IN")
    assert india["bench_cost_usd_cents"] >= by_object[(world.unit.id, "IN")]
    assert pnl(db, start=since, end=TODAY, tenant_id=1, country="US")["bench_cost_usd_cents"] == 0
