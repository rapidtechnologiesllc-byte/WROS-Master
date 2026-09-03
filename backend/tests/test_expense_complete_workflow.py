"""
import logging
Complete Expense Management Workflow - S-325: Expense Management

Tests the full lifecycle of expense management:
1. submit_expense - Employee logs expense with receipt
2. approve_expense (manager) - Manager approves or rejects
3. approve_expense (finance) - Finance approves and notifies
4. reimburse_expense - Mark as reimbursed when payment sent
5. track_reimbursement - Monitor status through each stage

Avinash's 2026-08-05 direction:
- Expense tracking is manual entry (receipt mandatory)
- Two-tier approval: Manager → Finance
- After finance approval, accounts@blitzenx.com is notified
- Finance Task tracks "mark paid once paid" to prevent approval-and-forget
"""
import logging
import os
import tempfile
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.client import Client
from app.models.expense import ExpenseRecord
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.expense_service import (
    ExpenseValidationError, approve_expense, approve_manager_step, log_expense,
    mark_expense_paid, track_reimbursement,
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


def _make_user(db, user_id, role, *, tenant_id=None, business_unit_id=None):
    user = Users(
        UserID=user_id, UserRole=role, UserEmail=f"{user_id}@blitzenx.com",
        UserPassword="h", tenant_id=tenant_id, business_unit_id=business_unit_id,
    )
    db.add(user)
    db.commit()
    return user


def _make_client(db, name, *, status="PROSPECT", tenant_id=None):
    client = Client(company_name=name, status=status, tenant_id=tenant_id)
    db.add(client)
    db.commit()
    return client

logger = logging.getLogger(__name__)

class TestSubmitExpense:
    """S-325: submit_expense - Employee logs expense for reimbursement."""

    def test_submit_expense_with_valid_data(self, db_session):
        """Employee can submit an expense with all required fields."""
        tenant = Tenant(name="BlitzenX")
        db_session.add(tenant)
        db_session.commit()

        curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)

        expense = log_expense(
            db_session, logged_by_user=curtis, purpose="CONFERENCE",
            conference_name="NAMIC 2026", expense_category="TRAVEL",
            travel_type="AIRFARE", amount_usd_cents=45000, expense_date=date(2026, 8, 1),
            receipt_ref="RECEIPT-001",
        )

        assert expense.id is not None
        assert expense.logged_by_user_id == "curtis"
        assert expense.purpose == "CONFERENCE"
        assert expense.amount_usd_cents == 45000
        assert expense.manager_approval_status == "PENDING"
        assert expense.payment_status == "PENDING"

    def test_submit_expense_requires_receipt(self, db_session):
        """Receipt reference is mandatory."""
        tenant = Tenant(name="BlitzenX")
        db_session.add(tenant)
        db_session.commit()

        curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)

        with pytest.raises(ExpenseValidationError, match="receipt_ref is mandatory"):
            log_expense(
                db_session, logged_by_user=curtis, purpose="CONFERENCE",
                conference_name="NAMIC 2026", expense_category="TRAVEL",
                amount_usd_cents=45000, expense_date=date(2026, 8, 1),
                receipt_ref="",  # Empty receipt
            )

    def test_submit_client_directed_expense_requires_client(self, db_session):
        """CLIENT_CURRENT/CLIENT_PROSPECT purposes require client_id."""
        tenant = Tenant(name="BlitzenX")
        db_session.add(tenant)
        db_session.commit()

        curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)

        with pytest.raises(ExpenseValidationError, match="requires client_id"):
            log_expense(
                db_session, logged_by_user=curtis, purpose="CLIENT_PROSPECT",
                expense_category="TRAVEL", amount_usd_cents=50000,
                expense_date=date(2026, 8, 1), receipt_ref="REC-001",
            )

    def test_submit_expense_creates_manager_approval_task(self, db_session):
        """Submitting an expense creates a Task for the manager."""
        tenant = Tenant(name="BlitzenX")
        db_session.add(tenant)
        db_session.commit()

        curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)

        expense = log_expense(
            db_session, logged_by_user=curtis, purpose="CONFERENCE",
            conference_name="NAMIC 2026", expense_category="TRAVEL",
            amount_usd_cents=45000, expense_date=date(2026, 8, 1),
            receipt_ref="REC-001",
        )

        task = db_session.query(Task).filter(Task.expense_id == expense.id).first()
        assert task is not None
        assert "Approve expense" in task.title

    def test_submit_expense_amount_must_be_positive(self, db_session):
        """Amount must be positive."""
        tenant = Tenant(name="BlitzenX")
        db_session.add(tenant)
        db_session.commit()

        curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)

        with pytest.raises(ExpenseValidationError, match="must be positive"):
            log_expense(
                db_session, logged_by_user=curtis, purpose="CONFERENCE",
                conference_name="NAMIC 2026", expense_category="TRAVEL",
                amount_usd_cents=-5000, expense_date=date(2026, 8, 1),
                receipt_ref="REC-001",
            )


class TestApproveExpense:
    """S-325: approve_expense - Manager and Finance approval workflow."""

    def test_manager_approval_sets_status(self, db_session):
        """Manager can approve an expense."""
        tenant = Tenant(name="BlitzenX")
        db_session.add(tenant)
        db_session.commit()

        curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)
        manager = _make_user(db_session, "manager1", "HR Manager", tenant_id=tenant.id)

        expense = log_expense(
            db_session, logged_by_user=curtis, purpose="CONFERENCE",
            conference_name="NAMIC 2026", expense_category="TRAVEL",
            amount_usd_cents=45000, expense_date=date(2026, 8, 1),
            receipt_ref="REC-001",
        )

        approved = approve_manager_step(db_session, expense, approved_by=manager.UserID)

        assert approved.manager_approval_status == "APPROVED"
        assert approved.manager_approved_by == manager.UserID
        assert approved.manager_approved_at is not None

    def test_finance_approval_requires_manager_approval(self, db_session, monkeypatch):
        """Finance cannot approve until manager has approved."""
        from app.services import email_service
        monkeypatch.setattr(
            email_service.EmailService, "send_event_notification",
            classmethod(lambda cls, **kwargs: {"sent": True}),
        )

        tenant = Tenant(name="BlitzenX")
        db_session.add(tenant)
        db_session.commit()

        curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)
        finance = _make_user(db_session, "finance1", "Finance", tenant_id=tenant.id)

        expense = log_expense(
            db_session, logged_by_user=curtis, purpose="CONFERENCE",
            conference_name="NAMIC 2026", expense_category="TRAVEL",
            amount_usd_cents=45000, expense_date=date(2026, 8, 1),
            receipt_ref="REC-001",
        )

        # Finance cannot approve while manager approval is PENDING
        with pytest.raises(ExpenseValidationError, match="manager approves"):
            approve_expense(db_session, expense, approved_by=finance.UserID)

    def test_finance_approval_after_manager_approval(self, db_session, monkeypatch):
        """Finance can approve after manager has approved."""
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
        manager = _make_user(db_session, "manager1", "HR Manager", tenant_id=tenant.id)
        finance = _make_user(db_session, "finance1", "Finance", tenant_id=tenant.id)

        expense = log_expense(
            db_session, logged_by_user=curtis, purpose="CONFERENCE",
            conference_name="NAMIC 2026", expense_category="TRAVEL",
            amount_usd_cents=45000, expense_date=date(2026, 8, 1),
            receipt_ref="REC-001",
        )

        # Manager approves first
        expense = approve_manager_step(db_session, expense, approved_by=manager.UserID)
        assert expense.manager_approval_status == "APPROVED"

        # Then finance approves
        approved = approve_expense(db_session, expense, approved_by=finance.UserID)

        assert approved.payment_status == "APPROVED"
        assert approved.approved_by == finance.UserID
        assert sent.get("to_email") == "accounts@blitzenx.com"

    def test_finance_approval_creates_mark_paid_task(self, db_session, monkeypatch):
        """Finance approval creates a Task to mark the expense as paid."""
        from app.services import email_service
        monkeypatch.setattr(
            email_service.EmailService, "send_event_notification",
            classmethod(lambda cls, **kwargs: {"sent": True}),
        )

        tenant = Tenant(name="BlitzenX")
        db_session.add(tenant)
        db_session.commit()

        curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)
        manager = _make_user(db_session, "manager1", "HR Manager", tenant_id=tenant.id)
        finance = _make_user(db_session, "finance1", "Finance", tenant_id=tenant.id)

        expense = log_expense(
            db_session, logged_by_user=curtis, purpose="CONFERENCE",
            conference_name="NAMIC 2026", expense_category="TRAVEL",
            amount_usd_cents=45000, expense_date=date(2026, 8, 1),
            receipt_ref="REC-001",
        )

        approve_manager_step(db_session, expense, approved_by=manager.UserID)
        approved = approve_expense(db_session, expense, approved_by=finance.UserID)

        task = db_session.query(Task).filter(
            Task.expense_id == expense.id, Task.status != "COMPLETED"
        ).first()
        assert task is not None
        assert "Mark expense as paid" in task.title


class TestReimburseExpense:
    """S-325: reimburse_expense - Mark expense as reimbursed."""

    def test_reimburse_expense_after_finance_approval(self, db_session, monkeypatch):
        """Can mark as reimbursed after finance approval."""
        from app.services import email_service
        monkeypatch.setattr(
            email_service.EmailService, "send_event_notification",
            classmethod(lambda cls, **kwargs: {"sent": True}),
        )

        tenant = Tenant(name="BlitzenX")
        db_session.add(tenant)
        db_session.commit()

        curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)
        manager = _make_user(db_session, "manager1", "HR Manager", tenant_id=tenant.id)
        finance = _make_user(db_session, "finance1", "Finance", tenant_id=tenant.id)

        expense = log_expense(
            db_session, logged_by_user=curtis, purpose="CONFERENCE",
            conference_name="NAMIC 2026", expense_category="TRAVEL",
            amount_usd_cents=45000, expense_date=date(2026, 8, 1),
            receipt_ref="REC-001",
        )

        approve_manager_step(db_session, expense, approved_by=manager.UserID)
        approve_expense(db_session, expense, approved_by=finance.UserID)

        reimbursed = mark_expense_paid(db_session, expense)

        assert reimbursed.payment_status == "REIMBURSED"

    def test_reimburse_expense_closes_task(self, db_session, monkeypatch):
        """Marking as reimbursed closes the associated Task."""
        from app.services import email_service
        monkeypatch.setattr(
            email_service.EmailService, "send_event_notification",
            classmethod(lambda cls, **kwargs: {"sent": True}),
        )

        tenant = Tenant(name="BlitzenX")
        db_session.add(tenant)
        db_session.commit()

        curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)
        manager = _make_user(db_session, "manager1", "HR Manager", tenant_id=tenant.id)
        finance = _make_user(db_session, "finance1", "Finance", tenant_id=tenant.id)

        expense = log_expense(
            db_session, logged_by_user=curtis, purpose="CONFERENCE",
            conference_name="NAMIC 2026", expense_category="TRAVEL",
            amount_usd_cents=45000, expense_date=date(2026, 8, 1),
            receipt_ref="REC-001",
        )

        approve_manager_step(db_session, expense, approved_by=manager.UserID)
        approve_expense(db_session, expense, approved_by=finance.UserID)

        mark_expense_paid(db_session, expense)

        task = db_session.query(Task).filter(Task.expense_id == expense.id).first()
        assert task.status == "COMPLETED"

    def test_cannot_reimburse_before_approval(self, db_session):
        """Cannot mark as reimbursed before finance approval."""
        tenant = Tenant(name="BlitzenX")
        db_session.add(tenant)
        db_session.commit()

        curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)

        expense = log_expense(
            db_session, logged_by_user=curtis, purpose="CONFERENCE",
            conference_name="NAMIC 2026", expense_category="TRAVEL",
            amount_usd_cents=45000, expense_date=date(2026, 8, 1),
            receipt_ref="REC-001",
        )

        with pytest.raises(ExpenseValidationError, match="must be APPROVED"):
            mark_expense_paid(db_session, expense)


class TestTrackReimbursement:
    """S-325: track_reimbursement - Monitor expense status through workflow."""

    def test_track_single_user_reimbursement(self, db_session, monkeypatch):
        """Can track reimbursement status for a single user."""
        from app.services import email_service
        monkeypatch.setattr(
            email_service.EmailService, "send_event_notification",
            classmethod(lambda cls, **kwargs: {"sent": True}),
        )

        tenant = Tenant(name="BlitzenX")
        db_session.add(tenant)
        db_session.commit()

        curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)
        manager = _make_user(db_session, "manager1", "HR Manager", tenant_id=tenant.id)
        finance = _make_user(db_session, "finance1", "Finance", tenant_id=tenant.id)

        # Create multiple expenses in different states
        exp1 = log_expense(
            db_session, logged_by_user=curtis, purpose="CONFERENCE",
            conference_name="NAMIC 2026", expense_category="TRAVEL",
            amount_usd_cents=45000, expense_date=date(2026, 8, 1),
            receipt_ref="REC-001",
        )

        exp2 = log_expense(
            db_session, logged_by_user=curtis, purpose="CONFERENCE",
            conference_name="IEEE 2026", expense_category="TRAVEL",
            amount_usd_cents=30000, expense_date=date(2026, 8, 5),
            receipt_ref="REC-002",
        )

        # Approve exp1 all the way through
        approve_manager_step(db_session, exp1, approved_by=manager.UserID)
        approve_expense(db_session, exp1, approved_by=finance.UserID)
        mark_expense_paid(db_session, exp1)

        # Leave exp2 at manager approval
        approve_manager_step(db_session, exp2, approved_by=manager.UserID)

        tracking = track_reimbursement(db_session, user_id="curtis")

        assert tracking["total_count"] == 2
        assert tracking["reimbursed_count"] == 1
        assert tracking["approved_count"] == 1
        assert tracking["pending_count"] == 0
        assert tracking["total_amount_usd_cents"] == 75000
        assert len(tracking["reimbursements"]) == 2

    def test_track_all_reimbursement(self, db_session, monkeypatch):
        """Can track reimbursement status for all users."""
        from app.services import email_service
        monkeypatch.setattr(
            email_service.EmailService, "send_event_notification",
            classmethod(lambda cls, **kwargs: {"sent": True}),
        )

        tenant = Tenant(name="BlitzenX")
        db_session.add(tenant)
        db_session.commit()

        curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)
        troy = _make_user(db_session, "troy", "Partner", tenant_id=tenant.id)
        manager = _make_user(db_session, "manager1", "HR Manager", tenant_id=tenant.id)
        finance = _make_user(db_session, "finance1", "Finance", tenant_id=tenant.id)

        # Create expenses from multiple users
        exp1 = log_expense(
            db_session, logged_by_user=curtis, purpose="CONFERENCE",
            conference_name="NAMIC 2026", expense_category="TRAVEL",
            amount_usd_cents=45000, expense_date=date(2026, 8, 1),
            receipt_ref="REC-001",
        )

        exp2 = log_expense(
            db_session, logged_by_user=troy, purpose="CONFERENCE",
            conference_name="IEEE 2026", expense_category="TRAVEL",
            amount_usd_cents=30000, expense_date=date(2026, 8, 5),
            receipt_ref="REC-002",
        )

        approve_manager_step(db_session, exp1, approved_by=manager.UserID)
        approve_manager_step(db_session, exp2, approved_by=manager.UserID)
        approve_expense(db_session, exp1, approved_by=finance.UserID)

        tracking = track_reimbursement(db_session)  # No user_id filter

        assert tracking["total_count"] == 2
        assert tracking["approved_count"] == 1
        assert tracking["pending_count"] == 1
        assert tracking["total_amount_usd_cents"] == 75000

    def test_reimbursement_tracking_shows_timeline(self, db_session, monkeypatch):
        """Reimbursement tracking includes days in each workflow stage."""
        from app.services import email_service
        monkeypatch.setattr(
            email_service.EmailService, "send_event_notification",
            classmethod(lambda cls, **kwargs: {"sent": True}),
        )

        tenant = Tenant(name="BlitzenX")
        db_session.add(tenant)
        db_session.commit()

        curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)
        manager = _make_user(db_session, "manager1", "HR Manager", tenant_id=tenant.id)
        finance = _make_user(db_session, "finance1", "Finance", tenant_id=tenant.id)

        expense = log_expense(
            db_session, logged_by_user=curtis, purpose="CONFERENCE",
            conference_name="NAMIC 2026", expense_category="TRAVEL",
            amount_usd_cents=45000, expense_date=date(2026, 8, 1),
            receipt_ref="REC-001",
        )

        approve_manager_step(db_session, expense, approved_by=manager.UserID)
        approve_expense(db_session, expense, approved_by=finance.UserID)

        tracking = track_reimbursement(db_session, user_id="curtis")

        reimbursement = tracking["reimbursements"][0]
        assert "days_pending" in reimbursement
        assert "days_awaiting_manager" in reimbursement
        assert "days_awaiting_finance" in reimbursement
        assert reimbursement["is_fully_processed"] is False  # Not yet reimbursed


class TestCompleteExpenseWorkflow:
    """S-325: Complete end-to-end workflow from submission to reimbursement."""

    def test_complete_workflow(self, db_session, monkeypatch):
        """Complete workflow: submit → manager approval → finance approval → reimburse."""
        from app.services import email_service
        monkeypatch.setattr(
            email_service.EmailService, "send_event_notification",
            classmethod(lambda cls, **kwargs: {"sent": True}),
        )

        tenant = Tenant(name="BlitzenX")
        db_session.add(tenant)
        db_session.commit()

        curtis = _make_user(db_session, "curtis", "Partner", tenant_id=tenant.id)
        manager = _make_user(db_session, "manager1", "HR Manager", tenant_id=tenant.id)
        finance = _make_user(db_session, "finance1", "Finance", tenant_id=tenant.id)

        # Step 1: Employee submits expense
        expense = log_expense(
            db_session, logged_by_user=curtis, purpose="CONFERENCE",
            conference_name="NAMIC 2026", expense_category="TRAVEL",
            travel_type="AIRFARE", amount_usd_cents=45000, expense_date=date(2026, 8, 1),
            receipt_ref="RECEIPT-NAMIC-2026-001",
        )

        assert expense.manager_approval_status == "PENDING"
        assert expense.payment_status == "PENDING"

        # Step 2: Manager approves
        expense = approve_manager_step(db_session, expense, approved_by=manager.UserID)
        assert expense.manager_approval_status == "APPROVED"

        # Step 3: Finance approves
        expense = approve_expense(db_session, expense, approved_by=finance.UserID)
        assert expense.payment_status == "APPROVED"

        # Step 4: Finance marks as reimbursed
        expense = mark_expense_paid(db_session, expense)
        assert expense.payment_status == "REIMBURSED"

        # Step 5: Track shows it's complete
        tracking = track_reimbursement(db_session, user_id="curtis")
        assert tracking["reimbursed_count"] == 1
        assert tracking["reimbursements"][0]["is_fully_processed"] is True
