"""One bench, every surface (CEO 2026-10-22): imported employees show the same on Workforce
Overview, the bench screen, the BU head and CEO dashboards, Demand vs Bench, bench cost, Flash
(who is on the bench, what it costs, status of a person) -- and the bench screen's loss
reconciles with the P&L's bench cost."""
import re
from datetime import date, timedelta

from app.models.business_unit import BusinessUnit
from app.models.employee import Employee
from app.services import employee_import_service as importer
from app.services.bench_service import bench_report, headcount_snapshot
from app.services.bu_head_dashboard_service import BUHeadDashboardService
from app.services.flash_service import answer_internal_query, find_available_bench_employees
from app.services.resource_management_service import get_current_bench_pool
from app.services.revenue_chain_service import pnl
from tests.test_core_certification import _h, _uid, _user, db  # noqa: F401 -- fixtures
from tests.test_employee_import import COLUMNS, _row, api, mail, world  # noqa: F401 -- fixtures

BENCH_SINCE = date.today() - timedelta(days=40)


def _import(db, world, *rows):
    content = ("\n".join([COLUMNS, *rows]) + "\n").encode()
    preview = importer.dry_run(db, world.hr, content)
    assert preview["counts"]["error"] == 0, [r["errors"] for r in preview["rows"]]
    return importer.apply(db, world.hr, preview["token"], content)


def _staff(world):
    return [
        _row(world, f"b1{_uid()}@bx.test", bench_since=BENCH_SINCE.isoformat()),
        _row(world, f"b2{_uid()}@bx.test", bench_since=BENCH_SINCE.isoformat(), salary="4500"),
        _row(world, f"in{_uid()}@bx.test", billable="no"),
    ]


def test_every_surface_counts_the_same_bench(api, db, world, mail):
    _import(db, world, *_staff(world))
    alloc_unit = BusinessUnit(tenant_id=1, name=f"other-{_uid()}", display_name="Other")
    db.add(alloc_unit)
    db.commit()
    _import(db, world, _row(world, f"al{_uid()}@bx.test", job=world.job.jobID, pct="100",
                            start=(date.today() - timedelta(days=10)).isoformat()))

    report = bench_report(db, world.hr)
    mine = {r["employee_id"] for r in report["employees"] if r["business_unit_id"] == world.unit.id}
    assert len(mine) == 2

    overview = api.get("/api/v1/workforce/overview", headers=_h(world.hr)).json()
    bench_groups = sum(g["count"] for g in overview["groups"] if g["key"].startswith("BENCH_"))
    assert bench_groups == report["totals"]["people"]
    assert next(g for g in overview["groups"] if g["key"] == "NON_BILLABLE")["count"] >= 1

    bu = BUHeadDashboardService.get_bu_dashboard_data(db, world.unit.id)
    assert bu["team_size"]["bench"] == len(mine) and bu["team_size"]["non_billable"] == 1
    assert bu["team_size"]["utilization_percent"] == round(1 / 3 * 100, 1)  # 1 of 3 billable allocated

    ceo = api.get("/api/v1/revenue-targets/dashboard", headers=_h(world.hr))
    assert ceo.status_code == 200, ceo.text
    risks = {r["key"]: r for r in ceo.json()["risks"]}
    assert risks["unallocated"]["value"] == len(headcount_snapshot(db)["bench"]) >= len(mine)
    assert risks["unallocated"]["link"] == "/workforce/bench"

    pool = {e.employee_id for e in get_current_bench_pool(db, tenant_id=1)}
    flash = {r["employee_id"] for r in find_available_bench_employees(db, world.hr, "")}
    everyone = {r["employee_id"] for r in report["employees"]}
    assert pool == flash == everyone  # Demand vs Bench, Flash and the bench screen: one list

    reply = answer_internal_query(db, "how much is bench costing us", current_user=world.hr)["reply"]
    assert f"{report['totals']['people']} people on the bench" in reply and "/workforce/bench" in reply
    who = answer_internal_query(db, "who is on the bench", current_user=world.hr)["reply"]
    assert re.match(rf"{len(everyone)} available", who)

    summary = api.get("/api/v1/employees/bench-cost-summary", headers=_h(world.hr)).json()
    assert summary["total_running_cost_usd_cents"] == report["totals"]["bench_loss_usd_cents"]


def test_bench_loss_reconciles_with_the_pnl_bench_cost(db, world, mail):
    _import(db, world, *_staff(world))
    report = bench_report(db, world.hr, business_unit_id=world.unit.id)
    assert report["cost_data_complete"]
    rows = report["employees"]
    assert {r["bench_since"] for r in rows} == {BENCH_SINCE.isoformat()}
    period = pnl(db, start=BENCH_SINCE, end=date.today(), tenant_id=1)
    unit = next(r for r in period["by_business_unit"] if r["key"] == world.unit.id)
    assert unit["bench_cost_usd_cents"] == sum(r["bench_loss_usd_cents"] for r in rows)
    assert unit["overhead_cost_usd_cents"] > 0  # the internal employee, never bench
    # sorted by bench loss, the higher salary first, with a net that is earnings minus loss
    assert rows[0]["bench_loss_usd_cents"] >= rows[1]["bench_loss_usd_cents"]
    assert rows[0]["net_usd_cents"] == rows[0]["allocated_margin_usd_cents"] - rows[0]["bench_loss_usd_cents"]


def test_money_is_hidden_without_pnl_rights(db, world, mail):
    from app.core.db_contract import LEADERSHIP_ROLES, ensure_role
    from app.models.role_template import RoleTemplate

    _import(db, world, *_staff(world))
    ensure_role(db, "Employee", LEADERSHIP_ROLES["Employee"], 1)
    viewer = _user(db, db.query(RoleTemplate).filter_by(tenant_id=1, name="Employee").one(), "Viewer")
    report = bench_report(db, viewer)
    assert report["financials_visible"] is False and report["totals"]["bench_loss_usd_cents"] is None


def test_flash_reports_an_imported_employees_status(db, world, mail):
    outcome = _import(db, world, _row(world, f"zara{_uid()}@bx.test", bench_since=BENCH_SINCE.isoformat()))
    employee = db.get(Employee, outcome["rows"][0]["employee_id"])
    employee.first_name = "Zara" + "".join(chr(97 + int(c, 16)) for c in _uid())  # a unique proper name
    db.commit()
    reply = answer_internal_query(db, f"what is the status of {employee.first_name}", current_user=world.hr)["reply"]
    assert "is an employee" in reply and f"on the bench since {BENCH_SINCE}" in reply


def test_manual_bench_marking_cannot_contradict_the_rule(api, db, world, mail):
    outcome = _import(db, world, _row(world, f"al{_uid()}@bx.test", job=world.job.jobID, pct="100"))
    allocated = outcome["rows"][0]["employee_id"]
    assert api.post(f"/api/v1/employees/{allocated}/mark-bench", headers=_h(world.hr),
                    json={"reason": "OTHER"}).status_code == 409
    bench = _import(db, world, _row(world, f"bn{_uid()}@bx.test"))["rows"][0]["employee_id"]
    assert api.post(f"/api/v1/employees/{bench}/remove-from-bench", headers=_h(world.hr)).status_code == 409


def test_a_bench_group_page_is_the_bench_screen(api, db, world, mail):
    _import(db, world, *_staff(world))
    res = api.get("/api/v1/workforce/bench?group=BENCH_READY", headers=_h(world.hr))
    assert res.status_code == 200 and {r["group"] for r in res.json()["employees"]} <= {"BENCH_READY"}
    assert api.get("/api/v1/workforce/bench?group=CORE", headers=_h(world.hr)).status_code == 404
