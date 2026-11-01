"""Expense receipts (CEO 2026-10-13): the receipt is attached, read and checked; a matching
receipt approves the manager step by itself, anything else waits for the manager with the
reasons. Finance still approves payment."""
import os
import uuid
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

os.environ.setdefault("JWT_SECRET", "test-secret-0123456789abcdef0123456789abcdef")

from app.models.user import Users  # noqa: E402
from app.services.expense_receipt_service import ReceiptError, attach_and_check  # noqa: E402
from app.services.expense_service import log_expense  # noqa: E402
from tests.hiring_fixtures import full_access_role  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def db(test_db_engine, tmp_path):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    with patch("app.core.config.settings.UPLOAD_DIR", str(tmp_path)):
        yield session
    session.close()
    outer.rollback()
    connection.close()


def expense(db, cents=12345, on=date(2026, 10, 1)):
    role = full_access_role(db)
    user = Users(UserID=f"U-{uid()}", UserName="E", UserEmail=f"{uid()}@x.com", UserPassword="x", UserRole="x",
                 tenant_id=1, role_template_id=role.id)
    db.add(user)
    db.flush()
    return log_expense(db, logged_by_user=user, purpose="OTHER", spend_for="INTERNAL", expense_category="MEALS",
                       amount_usd_cents=cents, expense_date=on, receipt_ref="r")


def reads(**receipt):
    return patch("app.services.expense_receipt_service.read_receipt",
                 return_value={"is_receipt": True, "currency": "USD", **receipt})


def test_a_matching_receipt_approves_the_manager_step_but_not_payment(db):
    e = expense(db)
    with reads(total=123.45, date="2026-10-02", merchant="Cafe"):
        e = attach_and_check(db, e, "r.png", "image/png", PNG)
    assert e.receipt_check_status == "MATCHED"
    assert e.manager_approval_status == "APPROVED" and e.payment_status == "PENDING"
    assert os.path.isfile(e.receipt_file_path)


def test_a_different_amount_or_date_waits_for_the_manager_with_reasons(db):
    e = expense(db)
    with reads(total=180.00, date="2026-09-01"):
        e = attach_and_check(db, e, "r.png", "image/png", PNG)
    assert e.receipt_check_status == "MISMATCH" and e.manager_approval_status == "PENDING"
    assert "180.00" in e.receipt_check_detail and "2026-09-01" in e.receipt_check_detail


def test_an_unreadable_receipt_waits_for_the_manager(db):
    e = expense(db)
    with patch("app.services.expense_receipt_service.read_receipt", side_effect=RuntimeError("timeout")):
        e = attach_and_check(db, e, "r.png", "image/png", PNG)
    assert e.receipt_check_status == "UNREADABLE" and e.manager_approval_status == "PENDING"


def test_only_receipt_files_are_accepted_and_a_decided_expense_is_locked(db):
    e = expense(db)
    with pytest.raises(ReceiptError):
        attach_and_check(db, e, "r.exe", "application/x-msdownload", b"MZ")
    with reads(total=123.45, date="2026-10-01"):
        attach_and_check(db, e, "r.png", "image/png", PNG)
    with pytest.raises(ReceiptError):
        attach_and_check(db, e, "r2.png", "image/png", PNG)
