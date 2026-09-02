"""
import logging
S-215/HRMS-0117 -- Error Logging Framework.

Proves: log_error() writes a real DB-queryable row (AC-3's real
prerequisite -- HRMS-1108 needs to filter by integration_name/time
window, which file logs can't do), CRITICAL severity pages on-call
synchronously (AC-1/BR-0117-01) via the real notification_service,
non-CRITICAL severities don't page, and query_error_log()'s filters
work.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.error_log import ErrorLog
from app.models.notification import Notification
from app.models.tenant import Tenant
from app.models.user import Users

import app.services.error_log_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, Notification.__table__, ErrorLog.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def super_user(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    user = Users(UserID="U-SU", UserRole="Super User", UserName="Avinash", UserEmail="avinash@blitzenx.com", UserPassword="h", tenant_id=tenant.id)
    db_session.add(user)
    db_session.commit()
    return user


def test_log_error_writes_real_row(db_session, super_user):
    row = svc.log_error(db_session, error_type="ValueError", severity="ERROR", message="something broke")
    assert row.id is not None
    assert db_session.query(ErrorLog).count() == 1


def test_log_error_rejects_unknown_severity(db_session, super_user):
    with pytest.raises(svc.UnknownSeverity):
        svc.log_error(db_session, error_type="X", severity="WHATEVER", message="x")


def test_critical_severity_pages_on_call_synchronously(db_session, super_user):
    svc.log_error(db_session, error_type="DatabaseError", severity="CRITICAL", message="DB connection lost")
    notes = db_session.query(Notification).filter(Notification.recipient_id == "U-SU", Notification.priority_tier == "P0").all()
    assert len(notes) == 1
    assert "DatabaseError" in notes[0].message


def test_non_critical_severity_does_not_page(db_session, super_user):
    svc.log_error(db_session, error_type="ValueError", severity="ERROR", message="minor issue")
    assert db_session.query(Notification).count() == 0


def test_log_error_captures_real_stack_trace(db_session, super_user):
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        row = svc.log_error(db_session, error_type="RuntimeError", severity="WARN", message="boom", exc=exc)
    assert row.stack_trace is not None
    assert "RuntimeError" in row.stack_trace
    assert "boom" in row.stack_trace


def test_query_error_log_filters_by_integration_name(db_session, super_user):
    svc.log_error(db_session, error_type="A", severity="INFO", message="a", integration_name="msgraph")
    svc.log_error(db_session, error_type="B", severity="INFO", message="b", integration_name="gemini")

    results = svc.query_error_log(db_session, integration_name="msgraph")
    assert len(results) == 1
    assert results[0].integration_name == "msgraph"


def test_query_error_log_filters_by_time_window(db_session, super_user):
    old = svc.log_error(db_session, error_type="Old", severity="INFO", message="old")
    old.created_at = datetime.utcnow() - timedelta(days=10)
    db_session.add(old)
    db_session.commit()
    svc.log_error(db_session, error_type="Recent", severity="INFO", message="recent")

    results = svc.query_error_log(db_session, since=datetime.utcnow() - timedelta(days=1))
    assert len(results) == 1
    assert results[0].error_type == "Recent"
