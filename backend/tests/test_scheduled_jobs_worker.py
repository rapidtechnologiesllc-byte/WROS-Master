"""Production background-job runner: lease, intervals, isolation, timeouts, and the
revenue jobs it can run (timesheet drafts, AR follow-up)."""
import time as time_mod
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.scheduled_jobs import JOBS, ScheduledJob
from app.models.scheduled_job_run import ScheduledJobRun
from app.workers import scheduled_jobs_worker as worker

CALLS = []
NOW = datetime(2026, 10, 8, 12, 0)


def ok_job(db):
    CALLS.append("ok")
    return {"done": 1}


def failing_job(db):
    CALLS.append("fail")
    raise RuntimeError("boom")


def slow_job(db):
    CALLS.append("slow")
    time_mod.sleep(3)


def guard(db, now):
    CALLS.append("guard")


def _job(name, target, **kw):
    return ScheduledJob(name=name, target=f"tests.test_scheduled_jobs_worker:{target}",
                        interval=kw.pop("interval", timedelta(hours=1)), timeout_s=kw.pop("timeout_s", 30), **kw)


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    session.info["connection"] = connection
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def _reset():
    CALLS.clear()


def _run(db, registry, enabled, now=NOW):
    factory = lambda: Session(bind=db.info["connection"], join_transaction_mode="create_savepoint")  # noqa: E731
    return worker.run_once(session_factory=factory, now=now, enabled=enabled, registry=registry)


def _row(db, name):
    db.expire_all()
    return db.query(ScheduledJobRun).filter_by(name=name).one()


def test_nothing_runs_unless_enabled(db):
    registry = {"a": _job("a", "ok_job")}
    assert _run(db, registry, "") == {}
    assert CALLS == []


def test_unknown_or_unguarded_external_job_refuses_to_start(db):
    registry = {"ext": _job("ext", "ok_job", sends_external=True)}
    with pytest.raises(worker.JobConfigError, match="backlog_guard"):
        _run(db, registry, "ext")
    with pytest.raises(worker.JobConfigError, match="unknown"):
        _run(db, registry, "nope")


def test_runs_once_per_interval_and_records_outcome(db):
    registry = {"a": _job("a", "ok_job")}
    assert _run(db, registry, "a") == {"a": "SUCCESS"}
    assert _run(db, registry, "a", NOW + timedelta(minutes=5)) == {"a": "NOT_DUE"}
    assert _run(db, registry, "a", NOW + timedelta(hours=1)) == {"a": "SUCCESS"}
    row = _row(db, "a")
    assert CALLS == ["ok", "ok"] and row.run_count == 2 and row.last_result == {"done": 1}
    assert row.lease_token is None and row.running_until is None


def test_live_lease_blocks_a_second_runner(db):
    registry = {"a": _job("a", "ok_job")}
    db.add(ScheduledJobRun(name="a", lease_token="other", running_until=NOW + timedelta(minutes=10),
                           run_count=0, consecutive_failures=0))
    db.commit()
    assert _run(db, registry, "a") == {"a": "NOT_DUE"}
    assert CALLS == []


def test_failing_job_is_isolated(db):
    registry = {"bad": _job("bad", "failing_job"), "good": _job("good", "ok_job")}
    assert _run(db, registry, "bad,good") == {"bad": "FAILED", "good": "SUCCESS"}
    row = _row(db, "bad")
    assert "boom" in row.last_error and row.consecutive_failures == 1 and row.lease_token is None


def test_timeout_is_recorded_and_lease_cleared(db):
    registry = {"slow": _job("slow", "slow_job", timeout_s=1)}
    assert _run(db, registry, "slow") == {"slow": "TIMEOUT"}
    assert _row(db, "slow").running_until is None


def test_daily_job_runs_once_per_day_after_its_time(db):
    registry = {"d": _job("d", "ok_job", interval=timedelta(days=1), daily_after_utc="09:30")}
    morning = datetime(2026, 10, 8, 9, 0)
    assert _run(db, registry, "d", morning) == {"d": "NOT_DUE"}
    assert _run(db, registry, "d", morning.replace(hour=10)) == {"d": "SUCCESS"}
    assert _run(db, registry, "d", morning.replace(hour=23)) == {"d": "NOT_DUE"}
    assert _run(db, registry, "d", datetime(2026, 10, 9, 9, 45)) == {"d": "SUCCESS"}


def test_backlog_guard_runs_only_before_the_first_run(db):
    registry = {"e": _job("e", "ok_job", sends_external=True, backlog_guard="tests.test_scheduled_jobs_worker:guard")}
    _run(db, registry, "e")
    _run(db, registry, "e", NOW + timedelta(hours=2))
    assert CALLS == ["guard", "ok", "ok"]


def test_stale_lease_token_cannot_overwrite_outcome(db):
    job = _job("a", "ok_job")
    db.add(ScheduledJobRun(name="a", lease_token="current", running_until=NOW + timedelta(minutes=5),
                           run_count=0, consecutive_failures=0))
    db.commit()
    assert worker.finish(db, job, "stale", "FAILED", error="late") is False
    assert _row(db, "a").last_status is None


def test_every_registered_job_target_resolves():
    for job in JOBS.values():
        assert callable(worker._resolve(job.target)), job.name
        assert not job.sends_external or job.backlog_guard, job.name


# ---- revenue jobs ---------------------------------------------------------------------

def test_weekly_timesheet_drafts_are_saved_and_idempotent(db):
    from app.models.client import Client
    from app.models.employee import Employee
    from app.models.employee_allocation import EmployeeAllocation
    from app.models.tenant import Tenant
    from app.models.timesheet import Timesheet
    from app.models.user import Jobs
    from app.services.timesheet_service import create_weekly_draft_batch

    tenant = db.query(Tenant).filter_by(id=1).first() or Tenant(id=1, name="t")
    db.add(tenant)
    db.flush()
    client = Client(tenant_id=1, company_name="Builders Insurance")
    employee = Employee(tenant_id=1, first_name="Sam", last_name="Lee", email=f"sam{id(db)}@blitzenx.com",
                        joining_date=date(2025, 1, 1), status="ALLOCATED")
    db.add_all([client, employee])
    db.flush()
    demand = Jobs(tenant_id=1, client_id=client.id, jobTitle="Guidewire Developer", jobDescription="d",
                  jobSkills="Guidewire", jobExperience="5", jobLocation="Remote")
    db.add(demand)
    db.flush()
    allocation = EmployeeAllocation(tenant_id=1, employee_id=employee.id, client_id=client.id,
                                    demand_id=demand.jobID, status="ACTIVE", start_date=date(2025, 1, 1))
    db.add(allocation)
    db.commit()

    first = create_weekly_draft_batch(db)
    db.expire_all()
    saved = db.query(Timesheet).filter_by(allocation_id=allocation.id).count()
    second = create_weekly_draft_batch(db)
    assert first["created"] >= 1 and saved == 1
    assert second["created"] == 0 and db.query(Timesheet).filter_by(allocation_id=allocation.id).count() == 1


def test_ar_follow_up_one_bad_invoice_does_not_stop_the_run(db):
    from app.services import ar_followup_service as ar

    rows = [{"invoice_id": "bad"}, {"invoice_id": "good"}]
    invoices = {"bad": object(), "good": object()}

    class Q:
        def __init__(self):
            self.id = None

        def filter(self, cond):
            self.id = cond.right.value
            return self

        def first(self):
            return invoices[self.id]

    seen = []

    def trigger(db_, invoice):
        if invoice is invoices["bad"]:
            raise ValueError("cross-tenant notification refused")
        seen.append(invoice)

    with patch.object(ar, "scan_overdue_invoices", return_value=rows), \
         patch.object(ar, "trigger_ar_follow_up", side_effect=trigger), \
         patch.object(db, "query", return_value=Q()):
        result = ar.run_ar_follow_up_job(db)
    assert result["processed"] == 1 and result["failed"] == 1 and seen == [invoices["good"]]
