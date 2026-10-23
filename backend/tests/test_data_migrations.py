"""One-time data migrations (db_contract.run_data_migrations): a persisted marker makes each run
exactly once. interview_times_to_utc moves interview times saved as India wall-clock time to the
naive-UTC storage convention, and leaves interviews made by the new scheduling path alone."""
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db_contract import DATA_MIGRATIONS, run_data_migrations
from app.models.channel_queue import ChannelQueueItem
from app.models.data_migration import DataMigration
from app.models.user import Interview


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    # The app's startup (another test's client) may already have run the migrations here.
    session.query(DataMigration).delete()
    session.flush()
    yield session
    session.close()
    outer.rollback()
    connection.close()


def test_interview_times_move_from_india_time_to_utc_exactly_once(db):
    legacy = Interview(start_time=datetime(2026, 10, 20, 15, 30), end_time=datetime(2026, 10, 20, 16, 30),
                       status="Scheduled")
    db.add(legacy)
    db.flush()

    assert run_data_migrations(db) == ["interview_times_to_utc", "employee_org_history_backfill"]
    db.refresh(legacy)
    assert (legacy.start_time, legacy.end_time) == (datetime(2026, 10, 20, 10, 0), datetime(2026, 10, 20, 11, 0))
    assert db.get(DataMigration, "interview_times_to_utc").applied_at is not None

    assert run_data_migrations(db) == []  # second startup: the marker is there, nothing converts again
    db.refresh(legacy)
    assert legacy.start_time == datetime(2026, 10, 20, 10, 0)


def test_interviews_scheduled_by_the_new_path_are_already_utc(db):
    new = Interview(start_time=datetime(2026, 10, 21, 4, 0), end_time=datetime(2026, 10, 21, 5, 0),
                    status="Scheduled")
    db.add(new)
    db.flush()
    db.add(ChannelQueueItem(id=f"interview-scheduled:{new.id}", message_id=f"m-{new.id}", tenant_id=1,
                            type="interview_scheduled", channel_type="FLASH_QUEUE", payload={},
                            status="COMPLETED"))
    db.flush()

    run_data_migrations(db)
    db.refresh(new)
    assert new.start_time == datetime(2026, 10, 21, 4, 0)


def test_a_failing_migration_leaves_no_marker_and_fails_loudly(db):
    def broken(session):
        session.execute(text("SELECT 1/0"))

    with pytest.raises(Exception):
        run_data_migrations(db, migrations=(("broken_once", broken),))
    assert db.get(DataMigration, "broken_once") is None
    assert [name for name, _ in DATA_MIGRATIONS] == ["interview_times_to_utc", "employee_org_history_backfill"]


def test_every_employee_gets_a_cost_object_history_row_once(db):
    """Existing employees get where they sit now, from their joining date (cost object history)."""
    from datetime import date

    from app.core.db_contract import _employee_org_history_backfill
    from app.models.employee import Employee
    from app.models.employee_org_history import EmployeeOrgHistory
    from app.models.tenant import Tenant

    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    employee = Employee(tenant_id=1, first_name="Old", last_name="Timer", email="old.timer@backfill.test",
                        joining_date=date(2020, 5, 1))
    db.add(employee)
    db.flush()
    db.query(EmployeeOrgHistory).filter_by(employee_id=employee.id).delete()  # as before history existed
    db.flush()
    assert _employee_org_history_backfill(db) >= 1
    rows = db.query(EmployeeOrgHistory).filter_by(employee_id=employee.id).all()
    assert [(r.effective_from, r.bu_id) for r in rows] == [(date(2020, 5, 1), None)]
    _employee_org_history_backfill(db)
    assert db.query(EmployeeOrgHistory).filter_by(employee_id=employee.id).count() == 1
