"""
Proves the new create_client() path (2026-08-05) enforces Avinash's
"client attribution locking" rule: BU is derived from the creating
user's own business_unit_id, never caller-suppliable, with a
Corporate-BU fallback for a BU-less creator (Super User/CEO) and a
null (Org-Pool) fallback when even that doesn't exist.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.client import Client, ClientContact, ClientHistory
from app.models.rbac_template import BusinessUnit
from app.models.user import Users
from app.services.client_service import (
    ClientValidationError, DuplicateClientError, create_client, update_client_details,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(
        engine,
        tables=[
            Tenant.__table__, Client.__table__, ClientContact.__table__,
            ClientHistory.__table__, BusinessUnit.__table__, Users.__table__,
        ],
    )
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _make_user(db, user_id, *, business_unit_id=None):
    user = Users(
        UserID=user_id, UserRole="Partner", UserEmail=f"{user_id}@blitzenx.com",
        UserPassword="hashed", business_unit_id=business_unit_id,
    )
    db.add(user)
    db.commit()
    return user


def test_client_bu_locked_to_creators_own_bu(db_session):
    axion = BusinessUnit(name="Axion")
    db_session.add(axion)
    db_session.commit()
    troy = _make_user(db_session, "troy", business_unit_id=axion.id)

    client = create_client(db_session, company_name="Builders Insurance", created_by_user=troy)

    assert client.business_unit_id == axion.id


def test_bu_less_creator_falls_back_to_corporate_bu(db_session):
    corporate = BusinessUnit(name="Corporate")
    db_session.add(corporate)
    db_session.commit()
    avinash = _make_user(db_session, "avinash", business_unit_id=None)

    client = create_client(db_session, company_name="Guidewire", created_by_user=avinash)

    assert client.business_unit_id == corporate.id


def test_bu_less_creator_with_no_corporate_row_leaves_client_unassigned(db_session):
    someone = _make_user(db_session, "someone", business_unit_id=None)

    client = create_client(db_session, company_name="Zensar", created_by_user=someone)

    assert client.business_unit_id is None


def test_duplicate_client_name_rejected(db_session):
    axion = BusinessUnit(name="Axion")
    db_session.add(axion)
    db_session.commit()
    troy = _make_user(db_session, "troy", business_unit_id=axion.id)
    create_client(db_session, company_name="Builders Insurance", created_by_user=troy)

    with pytest.raises(DuplicateClientError):
        create_client(db_session, company_name="Builders Insurance", created_by_user=troy)


# ---------------------------------------------------------------------------
# update_client_details()
# ---------------------------------------------------------------------------

def test_update_client_editable_fields(db_session):
    axion = BusinessUnit(name="Axion")
    db_session.add(axion)
    db_session.commit()
    troy = _make_user(db_session, "troy", business_unit_id=axion.id)
    client = create_client(db_session, company_name="Builders Insurance", created_by_user=troy)

    updated = update_client_details(db_session, client, {"industry": "Insurance", "notes": "Direct relationship"})

    assert updated.industry == "Insurance"
    assert updated.notes == "Direct relationship"


def test_update_client_business_unit_id_rejected(db_session):
    axion = BusinessUnit(name="Axion")
    db_session.add(axion)
    db_session.commit()
    troy = _make_user(db_session, "troy", business_unit_id=axion.id)
    client = create_client(db_session, company_name="Builders Insurance", created_by_user=troy)

    with pytest.raises(ClientValidationError):
        update_client_details(db_session, client, {"business_unit_id": 999})


def test_update_client_name_to_existing_name_rejected(db_session):
    axion = BusinessUnit(name="Axion")
    db_session.add(axion)
    db_session.commit()
    troy = _make_user(db_session, "troy", business_unit_id=axion.id)
    create_client(db_session, company_name="Builders Insurance", created_by_user=troy)
    other = create_client(db_session, company_name="Alfa Insurance", created_by_user=troy)

    with pytest.raises(DuplicateClientError):
        update_client_details(db_session, other, {"company_name": "Builders Insurance"})


# ---------------------------------------------------------------------------
# 2026-08-06 Client Management redesign: website dedup, line_type,
# hiring_manager/timesheet_approver contacts.
# ---------------------------------------------------------------------------

def test_website_dedup_rejects_second_client_same_domain(db_session):
    axion = BusinessUnit(name="Axion")
    db_session.add(axion)
    db_session.commit()
    troy = _make_user(db_session, "troy", business_unit_id=axion.id)
    create_client(db_session, company_name="Builders Insurance", created_by_user=troy, website="https://Builders.com/")

    with pytest.raises(DuplicateClientError):
        create_client(db_session, company_name="Builders Insurance Group", created_by_user=troy, website="www.builders.com")


def test_website_dedup_ignores_scheme_www_trailing_slash_case(db_session):
    """https://Builders.com/ and builders.com must be recognized as the
    same site -- proves _normalize_website(), not just exact string match."""
    axion = BusinessUnit(name="Axion")
    db_session.add(axion)
    db_session.commit()
    troy = _make_user(db_session, "troy", business_unit_id=axion.id)
    create_client(db_session, company_name="Builders Insurance", created_by_user=troy, website="https://Builders.com/")

    with pytest.raises(DuplicateClientError):
        create_client(db_session, company_name="Different Name", created_by_user=troy, website="builders.com")


def test_create_client_hiring_manager_and_timesheet_approver_contacts_created(db_session):
    axion = BusinessUnit(name="Axion")
    db_session.add(axion)
    db_session.commit()
    troy = _make_user(db_session, "troy", business_unit_id=axion.id)

    client = create_client(
        db_session, company_name="Builders Insurance", created_by_user=troy, line_type="CORE",
        website="builders.com",
        hiring_manager={"name": "Jane HM", "email": "jane@builders.com"},
        timesheet_approver={"name": "Sam TA", "email": "sam@builders.com"},
    )

    contacts = db_session.query(ClientContact).filter(ClientContact.client_id == client.id).all()
    roles = {c.role_type for c in contacts}
    assert roles == {"HIRING_MANAGER", "TIMESHEET_APPROVER"}
    assert client.line_type == "CORE"
