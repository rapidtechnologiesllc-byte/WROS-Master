"""
EPIC-16 AR Follow-Up. Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.client import Client
from app.models.employee import Employee
from app.models.invoice import Invoice
from app.models.project import Project
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.ar_followup_service import scan_overdue_invoices, trigger_ar_follow_up
import app.models  # noqa: F401


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


@pytest.fixture()
def world(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    am_employee = Employee(
        tenant_id=tenant.id, first_name="Account", last_name="Manager", email="am@blitzenx.com",
        joining_date=date(2024, 1, 1),
    )
    db_session.add(am_employee)
    db_session.commit()

    am_user = Users(UserID="U-AM", UserRole="Recruiter", UserEmail="am@blitzenx.com", UserPassword="h", tenant_id=tenant.id)
    db_session.add(am_user)
    db_session.commit()

    client = Client(
        tenant_id=tenant.id, company_name="Builders Insurance",
        account_manager_employee_id=am_employee.id,
    )
    db_session.add(client)
    db_session.commit()

    project = Project(tenant_id=tenant.id, client_id=client.id, name="Builders Engagement")
    db_session.add(project)
    db_session.commit()

    return {"tenant": tenant, "client": client, "project": project, "am_user": am_user}


def _make_invoice(db, world, *, sent_days_ago, total_usd_cents=50_000_00):
    invoice = Invoice(
        tenant_id=world["tenant"].id, client_id=world["client"].id, project_id=world["project"].id,
        status="SENT", total_usd_cents=total_usd_cents,
        billing_period_start=date(2026, 7, 1), billing_period_end=date(2026, 7, 31),
        sent_at=datetime.utcnow() - timedelta(days=sent_days_ago),
    )
    db.add(invoice)
    db.commit()
    return invoice


def test_scan_overdue_invoices_respects_grace_period(db_session, world):
    _make_invoice(db_session, world, sent_days_ago=45)  # overdue
    _make_invoice(db_session, world, sent_days_ago=10)  # within grace

    overdue = scan_overdue_invoices(db_session, grace_days=30)
    assert len(overdue) == 1
    assert overdue[0]["days_overdue"] >= 45


def test_scan_overdue_invoices_excludes_paid(db_session, world):
    invoice = _make_invoice(db_session, world, sent_days_ago=45)
    invoice.status = "PAID"
    db_session.add(invoice)
    db_session.commit()

    overdue = scan_overdue_invoices(db_session, grace_days=30)
    assert overdue == []


def test_trigger_ar_follow_up_creates_task_assigned_to_account_manager(db_session, world):
    invoice = _make_invoice(db_session, world, sent_days_ago=45)

    task = trigger_ar_follow_up(db_session, invoice)

    assert task.invoice_id == invoice.id
    assert task.assigned_to_user_id == "U-AM"
    assert "Builders Insurance" in task.title


def test_trigger_ar_follow_up_idempotent(db_session, world):
    invoice = _make_invoice(db_session, world, sent_days_ago=45)

    first = trigger_ar_follow_up(db_session, invoice)
    second = trigger_ar_follow_up(db_session, invoice)

    assert first.id == second.id
    assert db_session.query(Task).filter(Task.invoice_id == invoice.id).count() == 1


def test_trigger_ar_follow_up_creates_new_task_after_prior_one_completed(db_session, world):
    """Completing the follow-up Task (invoice finally paid, or manually
    resolved) should let a genuinely new overdue cycle open a fresh
    Task -- idempotency is "no duplicate open Task," not "never again.\""""
    invoice = _make_invoice(db_session, world, sent_days_ago=45)
    first = trigger_ar_follow_up(db_session, invoice)
    first.status = "COMPLETED"
    db_session.add(first)
    db_session.commit()

    second = trigger_ar_follow_up(db_session, invoice)
    assert second.id != first.id


def test_trigger_ar_follow_up_unassigned_when_no_account_manager(db_session, world):
    world["client"].account_manager_employee_id = None
    db_session.add(world["client"])
    db_session.commit()

    invoice = _make_invoice(db_session, world, sent_days_ago=45)
    task = trigger_ar_follow_up(db_session, invoice)

    assert task.assigned_to_user_id is None
    assert task.invoice_id == invoice.id
