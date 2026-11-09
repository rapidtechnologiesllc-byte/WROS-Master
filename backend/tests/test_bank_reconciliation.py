"""Bank reconciliation: a statement (CSV) records each credit once, each unmatched credit is shown with the
sent invoices for exactly that amount and one suggested, and Finance confirms the match (which pays the invoice)."""
import uuid
from datetime import date, datetime

import pytest
from sqlalchemy.orm import Session

from app.models.bank_reconciliation import BankTransaction
from app.models.business_unit import BusinessUnit
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.project import Project
from app.models.role_template import RoleTemplate
from app.models.tenant import Tenant
from app.services.bank_reconciliation_service import (
    BankReconciliationError, import_statement, parse_statement, reconciliation_view,
)
from tests.hiring_fixtures import full_access_role
from tests.test_core_certification import _h, _user


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def api(db):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def client_row(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    unit = BusinessUnit(tenant_id=1, name=f"bu-{_uid()}", display_name="BU")
    db.add(unit)
    db.flush()
    client = Client(tenant_id=1, company_name=f"Client {_uid()}", business_unit_id=unit.id)
    db.add(client)
    db.flush()
    project = Project(tenant_id=1, client_id=client.id, name=f"Project {_uid()}", delivery_engine="CORE")
    db.add(project)
    db.flush()
    client.project = project
    return client


def _sent(db, client, total, number=None):
    invoice = Invoice(tenant_id=1, project_id=client.project.id, client_id=client.id, status="SENT",
                      billing_period_start=date(2026, 9, 1), billing_period_end=date(2026, 9, 30),
                      total_usd_cents=total, invoice_number=number or f"INV-{_uid()}", sent_at=datetime(2026, 10, 1))
    db.add(invoice)
    db.flush()
    return invoice


def _credit(db, amount, description="WIRE IN", tenant_id=1):
    row = BankTransaction(tenant_id=tenant_id, transaction_date=date(2026, 10, 5), amount_usd_cents=amount,
                          description=description)
    db.add(row)
    db.flush()
    return row


def _mine(view, *credits):
    ids = {c.id for c in credits}
    return {t["id"]: t for t in view["transactions"] if t["id"] in ids}


STATEMENT = (
    "Date,Description,Amount\n"
    "2026-10-05,WIRE ACME INV-7,\"12,345.60\"\n"
    "10/06/2026,ACH GLOBEX,$900\n"
    "07-Oct-2026,BANK FEE,-25.00\n"
    "2026-10-08,CARD PAYMENT,(40.00)\n"
    "\n"
    "08.10.2026,ODD DATE,10.00\n"
    "2026-10-09,BAD AMOUNT,ten\n"
)


# ------------------------------------------------------------------------------ statement file

def test_statement_credits_are_read_and_debits_left_out():
    credits, unread, debits = parse_statement(STATEMENT.encode())
    assert [(c["transaction_date"], c["amount_usd_cents"], c["description"]) for c in credits] == [
        (date(2026, 10, 5), 1234560, "WIRE ACME INV-7"), (date(2026, 10, 6), 90000, "ACH GLOBEX")]
    assert debits == 2
    assert [(u["line"], u["reason"]) for u in unread] == [
        (7, "date '08.10.2026' is not YYYY-MM-DD, MM/DD/YYYY or DD-Mon-YYYY"), (8, "amount 'ten' is not a number")]


def test_statement_with_separate_credit_column_and_bank_headings():
    content = "Value Date,Narration,Debit,Credit\n2026-10-05,NEFT IN,,500.5\n2026-10-06,RENT,1000,\n".encode("utf-8-sig")
    credits, unread, debits = parse_statement(content)
    assert [(c["amount_usd_cents"], c["description"]) for c in credits] == [(50050, "NEFT IN")]
    assert (unread, debits) == ([], 1)


def test_statement_without_the_needed_columns_is_refused():
    with pytest.raises(BankReconciliationError, match="found: When, What"):
        parse_statement(b"When,What\n2026-10-05,x\n")
    with pytest.raises(BankReconciliationError, match="not UTF-8"):
        parse_statement("Date,Amount,Description\n2026-10-05,1,caf\xe9\n".encode("latin-1"))


def test_the_same_statement_uploaded_twice_records_each_credit_once(db, client_row):
    marker = _uid()
    content = f"Date,Description,Amount\n2026-10-05,WIRE {marker},100.00\n2026-10-05,WIRE {marker},100.00\n".encode()
    first = import_statement(db, content, created_by=None, tenant_id=1)
    assert (first["recorded"], first["duplicates"]) == (1, 1)
    second = import_statement(db, content, created_by=None, tenant_id=1)
    assert (second["recorded"], second["duplicates"]) == (0, 2)
    assert db.query(BankTransaction).filter(BankTransaction.description == f"WIRE {marker}").count() == 1


# ------------------------------------------------------------------------------ suggested matches

def test_a_credit_is_suggested_the_only_sent_invoice_for_its_amount(db, client_row):
    invoice = _sent(db, client_row, 777701)
    credit = _credit(db, 777701)
    row = _mine(reconciliation_view(db, tenant_id=1), credit)[credit.id]
    assert row["suggested_invoice_id"] == invoice.id
    assert [(c["invoice_number"], c["client_name"]) for c in row["candidates"]] == [
        (invoice.invoice_number, client_row.company_name)]


def test_two_invoices_for_the_amount_need_the_number_in_the_description(db, client_row):
    first, second = _sent(db, client_row, 888802, "BX-US-0041"), _sent(db, client_row, 888802, "BX-US-0042")
    unclear, named = _credit(db, 888802, "WIRE IN"), _credit(db, 888802, "Wire ref bx-us-0042 thanks")
    rows = _mine(reconciliation_view(db, tenant_id=1), unclear, named)
    assert rows[unclear.id]["suggested_invoice_id"] is None
    assert {c["invoice_id"] for c in rows[unclear.id]["candidates"]} == {first.id, second.id}
    assert rows[named.id]["suggested_invoice_id"] == second.id


def test_no_invoice_for_the_amount_and_other_tenants_stay_out(db, client_row):
    _sent(db, client_row, 999903)
    if db.query(Tenant).filter_by(id=2).first() is None:
        db.add(Tenant(id=2, name="other-tenant"))
        db.flush()
    lonely, foreign = _credit(db, 123), _credit(db, 999903, tenant_id=2)
    view = reconciliation_view(db, tenant_id=1)
    assert _mine(view, lonely)[lonely.id]["candidates"] == []
    assert _mine(view, foreign) == {}
    assert _mine(reconciliation_view(db, tenant_id=2), foreign)[foreign.id]["candidates"] == []


def test_a_paid_invoice_without_a_bank_credit_is_listed(db, client_row):
    invoice = _sent(db, client_row, 5000)
    invoice.status, invoice.paid_at = "PAID", datetime(2026, 10, 6)
    db.flush()
    listed = {i["invoice_id"] for i in reconciliation_view(db, tenant_id=1)["unmatched_paid_invoices"]}
    assert invoice.id in listed


# ------------------------------------------------------------------------------ routes

def test_upload_then_confirm_the_suggested_match_pays_the_invoice(db, api, client_row):
    user = _user(db, full_access_role(db), "Finance")
    invoice = _sent(db, client_row, 4321000)
    db.commit()
    marker = _uid()
    upload = api.post("/api/v1/bank-transactions/import", headers=_h(user),
                      files={"file": ("statement.csv", f"Date,Description,Amount\n2026-10-05,WIRE {marker},43210.00\n", "text/csv")})
    assert upload.status_code == 200, upload.text
    assert upload.json() == {"recorded": 1, "duplicates": 0, "debits_left_out": 0, "unread": []}

    view = api.get("/api/v1/bank-transactions/reconciliation", headers=_h(user))
    assert view.status_code == 200, view.text
    row = next(t for t in view.json()["transactions"] if t["description"] == f"WIRE {marker}")
    assert row["suggested_invoice_id"] == invoice.id

    matched = api.post(f"/api/v1/bank-transactions/{row['id']}/match", headers=_h(user), json={"invoice_id": invoice.id})
    assert matched.status_code == 200, matched.text
    db.refresh(invoice)
    assert (invoice.status, invoice.paid_at) == ("PAID", datetime(2026, 10, 5))
    after = api.get("/api/v1/bank-transactions/reconciliation", headers=_h(user)).json()
    assert all(t["id"] != row["id"] for t in after["transactions"])
    assert all(i["invoice_id"] != invoice.id for i in after["unmatched_paid_invoices"])


def test_a_bad_file_is_refused_and_a_role_without_finance_operations_is_too(db, api, client_row):
    user = _user(db, full_access_role(db), "Finance")
    bare = RoleTemplate(tenant_id=1, name=f"bare-{_uid()}", display_name="Bare", enabled=True)
    db.add(bare)
    db.flush()
    outsider = _user(db, bare, "Outsider")
    db.commit()
    bad = api.post("/api/v1/bank-transactions/import", headers=_h(user), files={"file": ("x.csv", "a,b\n1,2\n", "text/csv")})
    assert bad.status_code == 422 and "first line must name a date column" in bad.json()["detail"]
    assert api.get("/api/v1/bank-transactions/reconciliation", headers=_h(outsider)).status_code == 403
    refused = api.post("/api/v1/bank-transactions/import", headers=_h(outsider),
                       files={"file": ("x.csv", "Date,Description,Amount\n2026-10-05,x,1\n", "text/csv")})
    assert refused.status_code == 403
