"""
import logging
S-364/HRMS-0520 -- 30-Day Buddy Program: 35-KPI Framework & Tracking.

Proves: self-buddy prevention, KPI submission validation + upsert,
week-completeness (all 35 required, partial = draft), the 2-consecutive-
week low-score alert rule, and the Day-30 composite scorecard (category
averages, HR 34%/Buddy 43%/RM 23% weighting, trajectory, lowest-scoring
flags) -- only counting complete weeks.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.buddy_program import BuddyKPIScore, BuddyProgramRecord
from app.models.employee import Employee
from app.models.performance_store import EmployeePerformanceEvent
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.buddy_program_service import (
    ALL_KPI_NUMBERS,
    InvalidKPISubmission,
    SelfBuddyNotAllowed,
    check_low_kpi_alert,
    compute_day30_scorecard,
    create_buddy_program_record,
    is_week_complete,
    submit_weekly_scores,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, Employee.__table__,
        BuddyProgramRecord.__table__, BuddyKPIScore.__table__, EmployeePerformanceEvent.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def setup(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    mentee_user = Users(UserID="U-MENTEE", UserRole="Employee", UserEmail="mentee@blitzenx.com", UserPassword="h")
    buddy_user = Users(UserID="U-BUDDY", UserRole="Employee", UserEmail="buddy@blitzenx.com", UserPassword="h")
    db_session.add_all([mentee_user, buddy_user])
    db_session.commit()

    employee = Employee(
        tenant_id=tenant.id, first_name="New", last_name="Hire", email="newhire@blitzenx.com",
        joining_date=date(2026, 1, 1), wros_user_id="U-MENTEE",
    )
    db_session.add(employee)
    db_session.commit()

    return employee, tenant


def _submit_full_week(db, record, *, week_number, score_by_kpi=None, default_score=4):
    scores = {n: (score_by_kpi or {}).get(n, default_score) for n in ALL_KPI_NUMBERS}
    submit_weekly_scores(db, record, scores=scores, scored_by="U-BUDDY", week_number=week_number)
    db.commit()


# ---------------------------------------------------------------------------
# create_buddy_program_record -- self-buddy prevention
# ---------------------------------------------------------------------------

def test_create_record_succeeds_normally(db_session, setup):
    employee, tenant = setup
    record = create_buddy_program_record(
        db_session, employee, buddy_engineer_user_id="U-BUDDY",
        program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30), tenant_id=tenant.id,
    )
    db_session.commit()
    assert record.status == "IN_PROGRESS"


def test_self_buddy_rejected(db_session, setup):
    employee, tenant = setup
    with pytest.raises(SelfBuddyNotAllowed):
        create_buddy_program_record(
            db_session, employee, buddy_engineer_user_id="U-MENTEE",  # employee's own linked account
            program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30),
        )


# ---------------------------------------------------------------------------
# submit_weekly_scores -- validation and upsert
# ---------------------------------------------------------------------------

def test_submit_rejects_unknown_kpi_number(db_session, setup):
    employee, tenant = setup
    record = create_buddy_program_record(
        db_session, employee, buddy_engineer_user_id="U-BUDDY",
        program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30),
    )
    db_session.commit()
    with pytest.raises(InvalidKPISubmission):
        submit_weekly_scores(db_session, record, scores={99: 4}, scored_by="U-BUDDY", week_number=1)


def test_submit_rejects_out_of_range_score(db_session, setup):
    employee, tenant = setup
    record = create_buddy_program_record(
        db_session, employee, buddy_engineer_user_id="U-BUDDY",
        program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30),
    )
    db_session.commit()
    with pytest.raises(InvalidKPISubmission):
        submit_weekly_scores(db_session, record, scores={1: 6}, scored_by="U-BUDDY", week_number=1)


def test_resubmitting_same_kpi_and_week_updates_not_duplicates(db_session, setup):
    employee, tenant = setup
    record = create_buddy_program_record(
        db_session, employee, buddy_engineer_user_id="U-BUDDY",
        program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30),
    )
    db_session.commit()

    submit_weekly_scores(db_session, record, scores={1: 3}, scored_by="U-BUDDY", week_number=1)
    db_session.commit()
    submit_weekly_scores(db_session, record, scores={1: 5}, scored_by="U-BUDDY", week_number=1)
    db_session.commit()

    rows = db_session.query(BuddyKPIScore).filter(
        BuddyKPIScore.buddy_record_id == record.id, BuddyKPIScore.kpi_number == 1,
    ).all()
    assert len(rows) == 1
    assert rows[0].score == 5


# ---------------------------------------------------------------------------
# is_week_complete -- BR: all 35 required, partial = draft
# ---------------------------------------------------------------------------

def test_week_incomplete_with_partial_submission(db_session, setup):
    employee, tenant = setup
    record = create_buddy_program_record(
        db_session, employee, buddy_engineer_user_id="U-BUDDY",
        program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30),
    )
    db_session.commit()
    submit_weekly_scores(db_session, record, scores={1: 4, 2: 4}, scored_by="U-BUDDY", week_number=1)
    db_session.commit()
    assert is_week_complete(db_session, record, 1) is False


def test_week_complete_with_all_35_submitted(db_session, setup):
    employee, tenant = setup
    record = create_buddy_program_record(
        db_session, employee, buddy_engineer_user_id="U-BUDDY",
        program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30),
    )
    db_session.commit()
    _submit_full_week(db_session, record, week_number=1)
    assert is_week_complete(db_session, record, 1) is True


# ---------------------------------------------------------------------------
# check_low_kpi_alert -- 2 consecutive weeks < 2.0
# ---------------------------------------------------------------------------

def test_no_alert_before_two_weeks_scored(db_session, setup):
    employee, tenant = setup
    record = create_buddy_program_record(
        db_session, employee, buddy_engineer_user_id="U-BUDDY",
        program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30),
    )
    db_session.commit()
    submit_weekly_scores(db_session, record, scores={5: 1}, scored_by="U-BUDDY", week_number=1)
    db_session.commit()
    assert check_low_kpi_alert(db_session, record, 5, through_week=1) is False


def test_alert_fires_after_two_consecutive_low_weeks(db_session, setup):
    employee, tenant = setup
    record = create_buddy_program_record(
        db_session, employee, buddy_engineer_user_id="U-BUDDY",
        program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30),
    )
    db_session.commit()
    submit_weekly_scores(db_session, record, scores={5: 1}, scored_by="U-BUDDY", week_number=1)
    submit_weekly_scores(db_session, record, scores={5: 1}, scored_by="U-BUDDY", week_number=2)
    db_session.commit()
    assert check_low_kpi_alert(db_session, record, 5, through_week=2) is True


def test_no_alert_when_one_of_two_weeks_recovers(db_session, setup):
    employee, tenant = setup
    record = create_buddy_program_record(
        db_session, employee, buddy_engineer_user_id="U-BUDDY",
        program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30),
    )
    db_session.commit()
    submit_weekly_scores(db_session, record, scores={5: 1}, scored_by="U-BUDDY", week_number=1)
    submit_weekly_scores(db_session, record, scores={5: 4}, scored_by="U-BUDDY", week_number=2)
    db_session.commit()
    assert check_low_kpi_alert(db_session, record, 5, through_week=2) is False


# ---------------------------------------------------------------------------
# compute_day30_scorecard
# ---------------------------------------------------------------------------

def test_scorecard_reports_incomplete_weeks_and_excludes_them(db_session, setup):
    employee, tenant = setup
    record = create_buddy_program_record(
        db_session, employee, buddy_engineer_user_id="U-BUDDY",
        program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30),
    )
    db_session.commit()
    _submit_full_week(db_session, record, week_number=1, default_score=4)
    submit_weekly_scores(db_session, record, scores={1: 5}, scored_by="U-BUDDY", week_number=2)  # partial
    db_session.commit()

    scorecard = compute_day30_scorecard(db_session, record)
    assert scorecard["complete_weeks"] == [1]
    assert 2 in scorecard["incomplete_weeks"]
    # Category averages/weighted overall only need at least one complete
    # week; week 1 alone is enough here (all scored 4).
    assert scorecard["weighted_overall_score"] == 4.0
    # Trajectory specifically needs week 1 AND week 4 complete.
    assert scorecard["trajectory"] is None


def test_scorecard_computes_weighted_overall_when_all_weeks_complete(db_session, setup):
    employee, tenant = setup
    record = create_buddy_program_record(
        db_session, employee, buddy_engineer_user_id="U-BUDDY",
        program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30),
    )
    db_session.commit()
    for week in (1, 2, 3, 4):
        _submit_full_week(db_session, record, week_number=week, default_score=4)

    scorecard = compute_day30_scorecard(db_session, record)
    assert scorecard["complete_weeks"] == [1, 2, 3, 4]
    assert scorecard["category_averages"]["HR"] == 4.0
    assert scorecard["category_averages"]["BUDDY"] == 4.0
    assert scorecard["category_averages"]["RM"] == 4.0
    assert scorecard["weighted_overall_score"] == 4.0
    assert scorecard["trajectory"] == "STABLE"


def test_scorecard_trajectory_improving(db_session, setup):
    employee, tenant = setup
    record = create_buddy_program_record(
        db_session, employee, buddy_engineer_user_id="U-BUDDY",
        program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30),
    )
    db_session.commit()
    _submit_full_week(db_session, record, week_number=1, default_score=2)
    _submit_full_week(db_session, record, week_number=2, default_score=3)
    _submit_full_week(db_session, record, week_number=3, default_score=4)
    _submit_full_week(db_session, record, week_number=4, default_score=5)

    scorecard = compute_day30_scorecard(db_session, record)
    assert scorecard["trajectory"] == "IMPROVING"


def test_scorecard_flags_lowest_scoring_kpis(db_session, setup):
    employee, tenant = setup
    record = create_buddy_program_record(
        db_session, employee, buddy_engineer_user_id="U-BUDDY",
        program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30),
    )
    db_session.commit()
    low_scores = {1: 1, 2: 1}
    for week in (1, 2, 3, 4):
        _submit_full_week(db_session, record, week_number=week, score_by_kpi=low_scores, default_score=5)

    scorecard = compute_day30_scorecard(db_session, record)
    lowest_numbers = {item["kpi_number"] for item in scorecard["lowest_scoring_kpis"]}
    assert {1, 2}.issubset(lowest_numbers)


# ---------------------------------------------------------------------------
# HRMS-0515 performance store wiring
# ---------------------------------------------------------------------------

def test_submitting_scores_writes_performance_events(db_session, setup):
    employee, tenant = setup
    record = create_buddy_program_record(
        db_session, employee, buddy_engineer_user_id="U-BUDDY",
        program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30),
    )
    db_session.commit()

    submit_weekly_scores(db_session, record, scores={1: 4, 2: 3}, scored_by="U-BUDDY", week_number=1)
    db_session.commit()

    events = (
        db_session.query(EmployeePerformanceEvent)
        .filter(EmployeePerformanceEvent.employee_id == employee.id, EmployeePerformanceEvent.event_type == "BUDDY_KPI")
        .all()
    )
    assert len(events) == 2
