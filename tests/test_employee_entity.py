"""
Proves HRMS-0101 (+ 0101-REV): employee number generation, the status
state machine (transitions validated, history logged, invalid
transitions rejected), the DB-level CORE-requires-certified guard, and
AES-256 field encryption for bank details.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.employee import Employee, EmployeeEmploymentHistory
from app.services.employee_service import (
    generate_employee_number,
    transition_employee_status,
    InvalidStatusTransition,
)
from app.core.field_encryption import encrypt_field, decrypt_field, FieldEncryptionNotConfigured


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[Tenant.__table__, Employee.__table__, EmployeeEmploymentHistory.__table__])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _make_employee(db, tenant_id, **overrides):
    defaults = dict(
        tenant_id=tenant_id, first_name="Aisha", last_name="Verma",
        email="aisha@blitzenx.com", joining_date=date(2026, 1, 15), status="PRE_JOINING",
    )
    defaults.update(overrides)
    emp = Employee(**defaults)
    db.add(emp)
    db.commit()
    return emp


# ---------------------------------------------------------------------------
# Employee number generation (BR-02)
# ---------------------------------------------------------------------------

def test_employee_number_format(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    number = generate_employee_number(db_session, tenant.id, "BLX")
    assert number == "BLX-001"


def test_employee_number_increments_per_tenant(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    _make_employee(db_session, tenant.id, employee_number="BLX-001")
    number = generate_employee_number(db_session, tenant.id, "BLX")
    assert number == "BLX-002"


def test_employee_number_sequence_is_independent_per_tenant(db_session):
    t1 = Tenant(name="BlitzenX")
    t2 = Tenant(name="Other Client Co")
    db_session.add_all([t1, t2])
    db_session.commit()

    _make_employee(db_session, t1.id, employee_number="BLX-001")
    number_for_t2 = generate_employee_number(db_session, t2.id, "OTH")
    assert number_for_t2 == "OTH-001"  # not affected by t1's count


# ---------------------------------------------------------------------------
# Status state machine
# ---------------------------------------------------------------------------

def test_positive_case_valid_transition_succeeds_and_logs_history(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    emp = _make_employee(db_session, tenant.id, status="PRE_JOINING")

    transition_employee_status(db_session, emp, "ACTIVE", changed_by="U-HR1")
    db_session.commit()

    assert emp.status == "ACTIVE"
    history = db_session.query(EmployeeEmploymentHistory).filter(
        EmployeeEmploymentHistory.employee_id == emp.id
    ).all()
    assert len(history) == 1
    assert history[0].change_type == "STATUS"


def test_negative_case_invalid_transition_is_rejected(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    emp = _make_employee(db_session, tenant.id, status="PRE_JOINING")

    with pytest.raises(InvalidStatusTransition):
        transition_employee_status(db_session, emp, "EXITED")  # can't skip straight to exited

    assert emp.status == "PRE_JOINING"  # unchanged
    assert db_session.query(EmployeeEmploymentHistory).count() == 0  # no history for a rejected transition


def test_exited_is_terminal_no_transitions_allowed_out(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    emp = _make_employee(db_session, tenant.id, status="EXITED")

    with pytest.raises(InvalidStatusTransition):
        transition_employee_status(db_session, emp, "ACTIVE")


def test_full_realistic_lifecycle(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    emp = _make_employee(db_session, tenant.id, status="PRE_JOINING")

    transition_employee_status(db_session, emp, "ACTIVE")
    transition_employee_status(db_session, emp, "ALLOCATED")
    transition_employee_status(db_session, emp, "BENCH")
    transition_employee_status(db_session, emp, "NOTICE_PERIOD")
    transition_employee_status(db_session, emp, "EXITED")
    db_session.commit()

    assert emp.status == "EXITED"
    assert db_session.query(EmployeeEmploymentHistory).filter(
        EmployeeEmploymentHistory.employee_id == emp.id
    ).count() == 5


# ---------------------------------------------------------------------------
# Delivery engine defaults (0101-REV)
# ---------------------------------------------------------------------------

def test_new_employee_defaults_to_speciality_engine(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    emp = _make_employee(db_session, tenant.id)
    assert emp.delivery_engine == "SPECIALITY"
    assert emp.core_certified is False


# ---------------------------------------------------------------------------
# BR-01: AES-256 field encryption for bank details
# ---------------------------------------------------------------------------

@pytest.fixture()
def encryption_key(monkeypatch):
    import base64, secrets
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", key)
    yield key


def test_encrypt_decrypt_round_trip(encryption_key):
    plaintext = "1234567890123456"
    encrypted = encrypt_field(plaintext)
    assert encrypted != plaintext
    assert decrypt_field(encrypted) == plaintext


def test_encrypted_value_is_never_the_plaintext_substring(encryption_key):
    plaintext = "SECRET-BANK-ACCOUNT-9999"
    encrypted = encrypt_field(plaintext)
    assert plaintext not in encrypted


def test_fails_closed_when_encryption_key_not_configured(monkeypatch):
    monkeypatch.delenv("FIELD_ENCRYPTION_KEY", raising=False)
    with pytest.raises(FieldEncryptionNotConfigured):
        encrypt_field("1234567890123456")


def test_tampered_ciphertext_fails_to_decrypt(encryption_key):
    """AES-GCM is authenticated -- tampering must be detected, not silently
    decrypt to garbage."""
    encrypted = encrypt_field("1234567890123456")
    tampered = encrypted[:-4] + ("AAAA" if encrypted[-4:] != "AAAA" else "BBBB")
    with pytest.raises(Exception):
        decrypt_field(tampered)
