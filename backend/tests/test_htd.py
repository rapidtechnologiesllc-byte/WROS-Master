"""Hire-Train-Deploy (CEO 2026-10-24): trainees are not deployable, so never on the bench, and the
payroll of their training days is a P&L line of its own (HTD training), not bench, not overhead,
not revenue. Completing or leaving the track puts a billable, unallocated person on the bench."""
from datetime import date

import pytest

from app.models.employee import Employee
from app.models.resource_management import BenchPoolEntry
from app.services import bench_service
from app.services.employee_service import activate_joined_employees
from app.services.htd_service import HtdRefused, update_htd
from app.services.revenue_chain_service import CostBook, pnl
from tests.test_billable import MONTH_END, MONTH_START, _person, _unit
from tests.test_core_certification import _h, _uid, db  # noqa: F401 -- fixtures
from tests.test_employee_import import api, mail, world  # noqa: F401 -- fixtures


def _on_bench(db, employee) -> bool:
    return db.query(BenchPoolEntry).filter_by(employee_id=employee.id).count() == 1


def test_starting_htd_takes_a_bench_person_off_the_bench(db, world):
    person = _person(db, world)
    bench_service.reconcile_bench_pool(db)
    assert _on_bench(db, person)
    update_htd(db, person, on_track=True, start=date(2026, 9, 1), changed_by="test")
    db.commit()
    assert (person.htd_track, person.htd_phase, person.htd_start_date, person.htd_end_date) == \
        (True, "INDUCTION", date(2026, 9, 1), None)
    assert person.status == "ACTIVE" and not _on_bench(db, person)
    bench_service.reconcile_bench_pool(db)  # the startup reconcile leaves trainees off the bench
    assert not _on_bench(db, person)


@pytest.mark.parametrize("finish", ["COMPLETED", "EXITED", "off"])
def test_ending_htd_records_the_end_and_puts_them_on_the_bench(db, world, finish):
    person = _person(db, world)
    update_htd(db, person, on_track=True, start=date(2026, 9, 1), changed_by="test")
    if finish == "off":
        update_htd(db, person, on_track=False, changed_by="test", today=date(2026, 9, 21))
    else:
        update_htd(db, person, on_track=True, phase=finish, changed_by="test", today=date(2026, 9, 21))
    db.commit()
    assert person.htd_start_date == date(2026, 9, 1) and person.htd_end_date == date(2026, 9, 21)
    assert person.status == "BENCH" and _on_bench(db, person)


def test_moving_phases_keeps_the_start(db, world):
    person = _person(db, world)
    update_htd(db, person, on_track=True, start=date(2026, 8, 1), changed_by="test")
    update_htd(db, person, on_track=True, phase="SHADOW_DELIVERY", changed_by="test")
    assert (person.htd_phase, person.htd_start_date, person.htd_end_date) == ("SHADOW_DELIVERY", date(2026, 8, 1), None)
    with pytest.raises(HtdRefused):
        update_htd(db, person, on_track=True, phase="NAPPING", changed_by="test")


def test_an_internal_person_finishing_htd_is_never_benched(db, world):
    person = _person(db, world, billable=False, status="ACTIVE")
    update_htd(db, person, on_track=True, start=date(2026, 9, 1), changed_by="test")
    update_htd(db, person, on_track=True, phase="COMPLETED", changed_by="test")
    db.commit()
    assert person.status == "ACTIVE" and not _on_bench(db, person)


def test_a_joiner_hired_for_htd_joins_active_not_on_the_bench(db, world):
    person = _person(db, world, status="PRE_JOINING")
    person.joining_date = date(2026, 9, 1)
    update_htd(db, person, on_track=True, start=person.joining_date, changed_by="test")
    db.commit()
    activate_joined_employees(db, today=date(2026, 9, 2), employee_ids=[person.id])
    db.refresh(person)
    assert person.status == "ACTIVE" and not _on_bench(db, person)


def test_htd_training_days_are_their_own_cost_line(db, world):
    person = _person(db, world)
    db.commit()
    before = pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1)
    update_htd(db, person, on_track=True, start=date(2026, 9, 1), changed_by="test")
    update_htd(db, person, on_track=True, phase="COMPLETED", changed_by="test", today=date(2026, 9, 15))
    db.commit()
    after = pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1)
    training = CostBook(db).period(person, date(2026, 9, 1), date(2026, 9, 15))
    assert training > 0
    assert after["total_cost_usd_cents"] == before["total_cost_usd_cents"]  # a reclassification, not new cost
    assert after["htd_cost_usd_cents"] - before["htd_cost_usd_cents"] == training
    assert before["bench_cost_usd_cents"] - after["bench_cost_usd_cents"] == training
    unit = _unit(after, world)
    assert unit["htd_cost_usd_cents"] >= training
    company = next(r for r in after["by_company"] if r["key"] == world.company.id)
    assert company["htd_cost_usd_cents"] >= training
    assert company["total_cost_usd_cents"] == (company["delivery_cost_usd_cents"] + company["bench_cost_usd_cents"]
                                               + company["overhead_cost_usd_cents"] + company["htd_cost_usd_cents"]
                                               + company["expense_cost_usd_cents"]
                                               + company["intercompany_cost_usd_cents"])


def test_add_employee_hired_for_htd(api, db, world, mail):
    body = {"first_name": "Hira", "last_name": _uid(), "email": f"{_uid()}@bx.test", "joining_date": "2026-09-01",
            "business_unit_id": world.unit.id, "company_id": world.company.id, "base_salary_usd_cents": 200_000,
            "billable": True, "existing_staff": False, "hired_for_htd": True}
    response = api.post("/api/v1/employees", headers=_h(world.hr), json=body)
    assert response.status_code == 200, response.text
    item = response.json()
    assert (item["htd_track"], item["htd_phase"], item["htd_start_date"], item["deployment_status"]) == \
        (True, "INDUCTION", "2026-09-01", "HTD")
    row = db.query(Employee).filter(Employee.id == item["id"]).one()
    assert not _on_bench(db, row)
