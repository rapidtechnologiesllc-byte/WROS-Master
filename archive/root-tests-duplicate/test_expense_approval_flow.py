"""
Avinash, 2026-08-05: "you are not adding an approval mechanism and once
approved it has to be sent to accounts@blitzenx.com and assigned to
finance team as a task to mark it paid once paid." Proves the full
loop: approve -> Finance notified + a real Task created -> completing
that Task (via mark_expense_paid) flips the expense to REIMBURSED.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.expense import ExpenseRecord
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.expense_service import (
    ExpenseValidationError, approve_expense, log_expense, mark_expense_paid,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _make_user(db, user_id, role, *, tenant_id=None):
    user = Users(UserID=user_id, UserRole=role, UserEmail=f"{user_id}@blitzenx.com", UserPassword="h", tenant_id=tenant_id)
    db.add(user)
    db.commit()
    return user


def test_approve_creates_finance_task(db_session, monkeypatch):
    from app.services import email_service

    sent = {}
    monkeypatch.setattr(
        email_service.EmailService, "send_event_notification",
        classmethod(lambda cls, **kwargs: sent.update(kwargs) or {"sent": True}),
    )

    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)
    finance_user = _make_user(db_session, "fin1", "Finance", tenant_id=tenant.id)

    expense = log_expense(
        db_session, logged_by_user=curtis, purpose="CONFERENCE", conference_name="NAMIC 2026",
        expense_category="TRAVEL", travel_type="AIRFARE", amount_usd_cents=45000,
        expense_date=date(2026, 8, 1),
    )

    approved = approve_expense(db_session, expense, approved_by="troy")

    assert approved.payment_status == "APPROVED"
    assert sent.get("to_email") == "accounts@blitzenx.com"

    task = db_session.query(Task).filter(Task.expense_id == expense.id).first()
    assert task is not None
    assert task.assigned_to_user_id == "fin1"
    assert task.status == "NEW"


def test_mark_paid_completes_task_and_flips_status(db_session, monkeypatch):
    from app.services import email_service
    monkeypatch.setattr(
        email_service.EmailService, "send_event_notification",
        classmethod(lambda cls, **kwargs: {"sent": True}),
    )

    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)

    expense = log_expense(
        db_session, logged_by_user=curtis, purpose="CONFERENCE", conference_name="NAMIC 2026",
        expense_category="TRAVEL", amount_usd_cents=20000, expense_date=date(2026, 8, 1),
    )
    approve_expense(db_session, expense, approved_by="troy")

    paid = mark_expense_paid(db_session, expense)

    assert paid.payment_status == "REIMBURSED"
    task = db_session.query(Task).filter(Task.expense_id == expense.id).first()
    assert task.status == "COMPLETED"


def test_cannot_mark_paid_before_approval(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)

    expense = log_expense(
        db_session, logged_by_user=curtis, purpose="CONFERENCE", conference_name="NAMIC 2026",
        expense_category="TRAVEL", amount_usd_cents=20000, expense_date=date(2026, 8, 1),
    )

    with pytest.raises(ExpenseValidationError):
        mark_expense_paid(db_session, expense)
