"""Where an employee stands (app.services.employee_standing): employment from the status, deployment
from the active allocations, the Buddy Program and the bench pool."""
from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.services.employee_standing import deployment_status, employment_status, ending_soon

TODAY = date(2026, 10, 24)


@pytest.fixture(autouse=True)
def _alert_window(monkeypatch):
    monkeypatch.setattr(settings, "RENEWAL_ALERT_DAYS", "60,30,15")


def _alloc(days_from_today=None, renewal="NOT_STARTED"):
    end = None if days_from_today is None else (TODAY + timedelta(days=days_from_today)).isoformat()
    return {"end_date": end, "renewal_status": renewal}


@pytest.mark.parametrize("status, expected", [
    ("PRE_JOINING", "JOINING"), ("ACTIVE", "EMPLOYED"), ("BENCH", "EMPLOYED"), ("ALLOCATED", "EMPLOYED"),
    ("SPECIALITY_READY", "EMPLOYED"), ("ON_LEAVE", "ON_LEAVE"), ("NOTICE_PERIOD", "SERVING_NOTICE"),
    ("EXITED", "TERMINATED"),
])
def test_employment_follows_the_employee_status(status, expected):
    assert employment_status(status) == expected


def test_no_deployment_for_people_not_on_the_payroll():
    for status in ("PRE_JOINING", "EXITED"):
        assert deployment_status(status, "NOT_STARTED", [_alloc()], 3, TODAY)["status"] is None


def test_open_ended_allocation_is_on_project():
    assert deployment_status("ALLOCATED", "GRADUATED", [_alloc()], None, TODAY) == \
        {"status": "PROJECT", "until": None, "days": None}


def test_allocation_ending_outside_the_window_is_on_project_with_its_date():
    result = deployment_status("ALLOCATED", "GRADUATED", [_alloc(90)], None, TODAY)
    assert result == {"status": "PROJECT", "until": "2027-01-22", "days": 90}


def test_allocation_ending_inside_the_window_is_project_ending():
    assert deployment_status("ALLOCATED", "GRADUATED", [_alloc(45)], None, TODAY)["status"] == "PROJECT_ENDING"


def test_agreed_extension_is_not_ending_and_rolling_off_always_is():
    assert deployment_status("ALLOCATED", "GRADUATED", [_alloc(10, "EXTENDED")], None, TODAY)["status"] == "PROJECT"
    assert deployment_status("ALLOCATED", "GRADUATED", [_alloc(200, "ROLLING_OFF")], None, TODAY)["status"] == \
        "PROJECT_ENDING"


def test_ending_only_when_every_active_allocation_is_ending():
    assert deployment_status("ALLOCATED", "GRADUATED", [_alloc(20), _alloc(120)], None, TODAY)["status"] == "PROJECT"
    assert deployment_status("ALLOCATED", "GRADUATED", [_alloc(20), _alloc()], None, TODAY)["status"] == "PROJECT"


def test_buddy_program_without_an_allocation_is_buddy():
    for buddy in ("IN_PROGRESS", "EXTENDED"):
        assert deployment_status("ACTIVE", buddy, [], 5, TODAY)["status"] == "BUDDY"


def test_no_allocation_after_the_buddy_program_is_bench_with_its_days():
    assert deployment_status("BENCH", "GRADUATED", [], 12, TODAY) == {"status": "BENCH", "until": None, "days": 12}


def test_serving_notice_still_shows_where_they_are_deployed():
    assert deployment_status("NOTICE_PERIOD", "GRADUATED", [_alloc(90)], None, TODAY)["status"] == "PROJECT"


def test_ending_soon_uses_the_largest_alert_threshold(monkeypatch):
    monkeypatch.setattr(settings, "RENEWAL_ALERT_DAYS", "30,10")
    assert ending_soon(TODAY + timedelta(days=30), None, TODAY)
    assert not ending_soon(TODAY + timedelta(days=31), None, TODAY)
    assert not ending_soon(None, None, TODAY)
