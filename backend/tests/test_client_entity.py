"""
Proves HRMS-0102: BR-01 (no ACTIVE status without a contact) and BR-02
import logging
(markup rate hidden from CS/recruiter-facing serialization).

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
from app.services.client_service import (
    set_client_status,
    serialize_client_for_role,
    ClientValidationError,
)

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[Tenant.__table__, Client.__table__, ClientContact.__table__, ClientHistory.__table__])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

def _make_client(db, tenant_id, **overrides):
    defaults = dict(tenant_id=tenant_id, company_name="Acme Insurance", status="PROSPECT")
    defaults.update(overrides)
    client = Client(**defaults)
    db.add(client)
    db.commit()
    return client

# ---------------------------------------------------------------------------
# BR-01: ACTIVE requires at least one contact
# ---------------------------------------------------------------------------

def test_negative_case_cannot_activate_without_a_contact(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    client = _make_client(db_session, tenant.id)

    with pytest.raises(ClientValidationError):
        set_client_status(db_session, client, "ACTIVE")

    assert client.status == "PROSPECT"  # unchanged
    assert db_session.query(ClientHistory).count() == 0

def test_positive_case_activation_succeeds_with_a_contact(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    client = _make_client(db_session, tenant.id)
    db_session.add(ClientContact(
        tenant_id=tenant.id, client_id=client.id, name="Priya Sharma",
        email="priya@acme.com", role_type="HIRING_MANAGER",
    ))
    db_session.commit()

    set_client_status(db_session, client, "ACTIVE", changed_by="U-BUHEAD")
    db_session.commit()

    assert client.status == "ACTIVE"
    history = db_session.query(ClientHistory).filter(ClientHistory.client_id == client.id).all()
    assert len(history) == 1

def test_non_active_status_does_not_require_a_contact(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    client = _make_client(db_session, tenant.id)

    set_client_status(db_session, client, "ON_HOLD")  # must not raise
    assert client.status == "ON_HOLD"

# ---------------------------------------------------------------------------
# BR-02: markup rate visibility
# ---------------------------------------------------------------------------

def test_markup_rate_hidden_from_recruiter(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    client = _make_client(db_session, tenant.id, markup_rate_pct="35.00")

    serialized = serialize_client_for_role(client, "Recruiter")
    assert "markup_rate_pct" not in serialized

def test_markup_rate_visible_to_bu_head(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    client = _make_client(db_session, tenant.id, markup_rate_pct="35.00")

    serialized = serialize_client_for_role(client, "BU Head")
    assert serialized["markup_rate_pct"] == 35.00

def test_markup_rate_hidden_from_cs_role(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    client = _make_client(db_session, tenant.id, markup_rate_pct="20.00")

    serialized = serialize_client_for_role(client, "HR Operations")
    assert "markup_rate_pct" not in serialized
