"""
Partner/BU spend tracking, 2026-08-05. Proves the purpose/client
tagging rules and the client investment-position ledger (prospect-era
expense -> conversion -> revenue -> breakeven), reusing ClientHistory's
import logging
existing STATUS log rather than a second tracking mechanism.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.client import Client, ClientContact, ClientHistory
from app.models.expense import ExpenseRecord
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.project import Project
from app.models.rbac_template import BusinessUnit
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.client_service import set_client_status
from app.services.expense_service import (
    ExpenseValidationError, get_client_investment_position, log_expense,
)

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, BusinessUnit.__table__, Users.__table__, Client.__table__,
        ClientContact.__table__, ClientHistory.__table__, ExpenseRecord.__table__,
        Project.__table__, Invoice.__table__, InvoiceLineItem.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

def _make_user(db, user_id, *, business_unit_id=None):
    user = Users(UserID=user_id, UserRole="Partner", UserEmail=f"{user_id}@blitzenx.com", UserPassword="h", business_unit_id=business_unit_id)
    db.add(user)
    db.commit()
    return user

def _make_client(db, name, *, status="PROSPECT"):
    client = Client(company_name=name, status=status)
    db.add(client)
    db.commit()
    return client

def test_client_directed_purpose_requires_client_id(db_session):
    curtis = _make_user(db_session, "curtis")
    with pytest.raises(ExpenseValidationError):
        log_expense(
            db_session, logged_by_user=curtis, purpose="CLIENT_PROSPECT",
            expense_category="TRAVEL", amount_usd_cents=50000, expense_date=date(2026, 8, 1),
        )

def test_conference_purpose_requires_conference_name(db_session):
    curtis = _make_user(db_session, "curtis")
    with pytest.raises(ExpenseValidationError):
        log_expense(
            db_session, logged_by_user=curtis, purpose="CONFERENCE",
            expense_category="TRAVEL", amount_usd_cents=50000, expense_date=date(2026, 8, 1),
        )

def test_conference_expense_has_no_client(db_session):
    curtis = _make_user(db_session, "curtis")
    expense = log_expense(
        db_session, logged_by_user=curtis, purpose="CONFERENCE", conference_name="NAMIC 2026",
        expense_category="TRAVEL", travel_type="AIRFARE", amount_usd_cents=45000,
        expense_date=date(2026, 8, 1),
    )
    assert expense.client_id is None
    assert expense.conference_name == "NAMIC 2026"

def test_expense_bu_derived_from_logger_never_caller_supplied(db_session):
    axion = BusinessUnit(name="Axion")
    db_session.add(axion)
    db_session.commit()
    troy = _make_user(db_session, "troy", business_unit_id=axion.id)
    goldenbear = _make_client(db_session, "Goldenbear", status="PROSPECT")

    expense = log_expense(
        db_session, logged_by_user=troy, purpose="CLIENT_PROSPECT", client_id=goldenbear.id,
        expense_category="TRAVEL", travel_type="AIRFARE", amount_usd_cents=120000,
        expense_date=date(2026, 8, 1), trip_label="Seattle - Goldenbear - Aug 2026",
    )
    assert expense.business_unit_id == axion.id
    assert expense.logged_by_user_id == "troy"

def test_client_investment_position_prospect_to_breakeven(db_session):
    curtis = _make_user(db_session, "curtis")
    builders = _make_client(db_session, "Builders Insurance", status="PROSPECT")

    # Prospect-era spend: two trips before conversion.
    log_expense(
        db_session, logged_by_user=curtis, purpose="CLIENT_PROSPECT", client_id=builders.id,
        expense_category="TRAVEL", travel_type="AIRFARE", amount_usd_cents=80000,
        expense_date=date(2026, 3, 1),
    )
    log_expense(
        db_session, logged_by_user=curtis, purpose="CLIENT_PROSPECT", client_id=builders.id,
        expense_category="LODGING", amount_usd_cents=40000,
        expense_date=date(2026, 4, 1),
    )

    # Converts to a real client (BR-01: needs a contact first).
    db_session.add(ClientContact(client_id=builders.id, name="Jane Doe", email="jane@builders.com", role_type="PRIMARY", is_primary=True))
    db_session.commit()
    set_client_status(db_session, builders, "ACTIVE", changed_by="curtis")
    db_session.commit()

    # Post-conversion spend continues.
    log_expense(
        db_session, logged_by_user=curtis, purpose="CLIENT_CURRENT", client_id=builders.id,
        expense_category="TRAVEL", travel_type="GROUND_TRANSPORT", amount_usd_cents=5000,
        expense_date=date(2026, 5, 1),
    )

    # Revenue starts coming in via a real Project + Invoice.
    project = Project(client_id=builders.id, name="Builders SI Engagement", status="ACTIVE", billing_type="TIME_AND_MATERIALS")
    db_session.add(project)
    db_session.commit()

    invoice1 = Invoice(
        client_id=builders.id, project_id=project.id, status="PAID", total_usd_cents=70000,
        billing_period_start=date(2026, 5, 1), billing_period_end=date(2026, 5, 31),
        created_at=datetime(2026, 5, 15),
    )
    invoice2 = Invoice(
        client_id=builders.id, project_id=project.id, status="PAID", total_usd_cents=90000,
        billing_period_start=date(2026, 6, 1), billing_period_end=date(2026, 6, 30),
        created_at=datetime(2026, 6, 15),
    )
    db_session.add_all([invoice1, invoice2])
    db_session.commit()

    position = get_client_investment_position(db_session, builders.id)

    assert position["total_expense_usd_cents"] == 80000 + 40000 + 5000
    assert position["total_revenue_usd_cents"] == 70000 + 90000
    assert position["net_position_usd_cents"] == (70000 + 90000) - (80000 + 40000 + 5000)
    assert position["converted_on"] is not None
    # Running balance: -80000, -120000, -125000, -55000 (after inv1), +35000 (after inv2)
    assert position["breakeven_date"] == date(2026, 6, 15)
    assert position["expense_count"] == 3

def test_client_investment_position_never_reaches_breakeven(db_session):
    curtis = _make_user(db_session, "curtis")
    goldenbear = _make_client(db_session, "Goldenbear", status="PROSPECT")
    log_expense(
        db_session, logged_by_user=curtis, purpose="CLIENT_PROSPECT", client_id=goldenbear.id,
        expense_category="TRAVEL", amount_usd_cents=150000, expense_date=date(2026, 8, 1),
    )

    position = get_client_investment_position(db_session, goldenbear.id)

    assert position["total_revenue_usd_cents"] == 0
    assert position["breakeven_date"] is None
    assert position["net_position_usd_cents"] == -150000
