"""
import logging
S-365/HRMS-0521 -- Buddy Program Graduation Gate: BU Head Approval.

Proves: GRADUATE sets SPECIALITY_READY (AC-3), EXTEND requires a real
50+ char improvement note and caps at 2 (AC-4/BR), EXIT triggers
PERFORMANCE_MANAGED (AC-5), and decisions accumulate in
bu_head_decision_notes rather than overwriting each other.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.buddy_program import BuddyProgramRecord
from app.models.employee import Employee, EmployeeEmploymentHistory
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.buddy_program_graduation_service import (
    MAX_EXTENSIONS,
    ExtensionLimitReached,
    InvalidGraduationDecision,
    can_extend,
    record_graduation_decision,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, Employee.__table__,
        EmployeeEmploymentHistory.__table__, BuddyProgramRecord.__table__,
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

    employee = Employee(
        tenant_id=tenant.id, first_name="New", last_name="Hire", email="newhire@blitzenx.com",
        joining_date=date(2026, 1, 1), status="ACTIVE", buddy_program_status="IN_PROGRESS",
    )
    db_session.add(employee)
    db_session.commit()

    record = BuddyProgramRecord(
        tenant_id=tenant.id, employee_id=employee.id, buddy_engineer_user_id="U-BUDDY",
        program_start_date=date(2026, 1, 1), expected_end_date=date(2026, 1, 30), status="IN_PROGRESS",
    )
    db_session.add(record)
    db_session.commit()

    return employee, record, tenant


IMPROVEMENT_NOTE = "Needs more practice with unscripted adhoc problem-solving scenarios in live client sessions."


def test_graduate_sets_speciality_ready(db_session, setup):
    employee, record, tenant = setup
    record_graduation_decision(db_session, record, employee, decision="GRADUATE", changed_by="U-BUH")
    db_session.commit()

    assert record.status == "GRADUATED"
    assert record.actual_end_date == date.today()
    assert employee.buddy_program_status == "GRADUATED"
    assert employee.buddy_program_graduation_date == date.today()
    assert employee.status == "SPECIALITY_READY"


def test_exit_sets_performance_managed(db_session, setup):
    employee, record, tenant = setup
    record_graduation_decision(
        db_session, record, employee, decision="EXIT", changed_by="U-BUH",
        notes="Consistently below threshold across all three scorecards despite two extensions.",
    )
    db_session.commit()

    assert record.status == "EXITED"
    assert employee.buddy_program_status == "EXITED"
    assert employee.status == "PERFORMANCE_MANAGED"


def test_extend_requires_minimum_note_length(db_session, setup):
    employee, record, tenant = setup
    with pytest.raises(InvalidGraduationDecision):
        record_graduation_decision(
            db_session, record, employee, decision="EXTEND", changed_by="U-BUH", notes="too short",
        )


def test_extend_increments_count_and_pushes_end_date(db_session, setup):
    employee, record, tenant = setup
    original_end_date = record.expected_end_date

    record_graduation_decision(
        db_session, record, employee, decision="EXTEND", changed_by="U-BUH", notes=IMPROVEMENT_NOTE,
    )
    db_session.commit()

    assert record.extension_count == 1
    assert record.expected_end_date == original_end_date + timedelta(days=15)
    assert record.status == "EXTENDED"
    assert employee.buddy_program_status == "EXTENDED"


def test_extend_blocked_after_max_extensions(db_session, setup):
    employee, record, tenant = setup
    record_graduation_decision(db_session, record, employee, decision="EXTEND", changed_by="U-BUH", notes=IMPROVEMENT_NOTE)
    db_session.commit()
    record_graduation_decision(db_session, record, employee, decision="EXTEND", changed_by="U-BUH", notes=IMPROVEMENT_NOTE)
    db_session.commit()

    assert record.extension_count == MAX_EXTENSIONS
    assert can_extend(record) is False

    with pytest.raises(ExtensionLimitReached):
        record_graduation_decision(db_session, record, employee, decision="EXTEND", changed_by="U-BUH", notes=IMPROVEMENT_NOTE)


def test_third_review_can_still_graduate_or_exit(db_session, setup):
    employee, record, tenant = setup
    record_graduation_decision(db_session, record, employee, decision="EXTEND", changed_by="U-BUH", notes=IMPROVEMENT_NOTE)
    db_session.commit()
    record_graduation_decision(db_session, record, employee, decision="EXTEND", changed_by="U-BUH", notes=IMPROVEMENT_NOTE)
    db_session.commit()

    record_graduation_decision(db_session, record, employee, decision="GRADUATE", changed_by="U-BUH")
    db_session.commit()
    assert record.status == "GRADUATED"


def test_invalid_decision_string_rejected(db_session, setup):
    employee, record, tenant = setup
    with pytest.raises(InvalidGraduationDecision):
        record_graduation_decision(db_session, record, employee, decision="MAYBE_LATER", changed_by="U-BUH")


def test_decision_notes_accumulate_not_overwrite(db_session, setup):
    employee, record, tenant = setup
    record_graduation_decision(db_session, record, employee, decision="EXTEND", changed_by="U-BUH", notes=IMPROVEMENT_NOTE)
    db_session.commit()
    record_graduation_decision(db_session, record, employee, decision="GRADUATE", changed_by="U-BUH")
    db_session.commit()

    assert "EXTEND" in record.bu_head_decision_notes
    assert "GRADUATE" in record.bu_head_decision_notes
