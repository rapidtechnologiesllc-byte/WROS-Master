"""
Proves HRMS-0101 (+ 0101-REV): employee number generation, the status
state machine (transitions validated, history logged, invalid
transitions rejected), the DB-level CORE-requires-certified guard, and
AES-256 field encryption for bank details.

"""
import os
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.tenant import Tenant
from app.models.employee import Employee, EmployeeEmploymentHistory, EmployeeEngineHistory
from app.services.employee_service import (
    CoreAssignmentNotAllowed,
    convert_candidate_to_employee,
    generate_employee_number,
    set_core_delivery_engine,
    transition_employee_status,
    InvalidStatusTransition,
)
from app.core.field_encryption import encrypt_field, decrypt_field, FieldEncryptionNotConfigured

@pytest.fixture()
def db_session():
    engine = create_engine(f"sqlite:///{db_path}")
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
# S-351/HRMS-0512 AC-3 -- DB CHECK constraint independently blocks CORE
# without core_certified=TRUE, even bypassing application code entirely.
# ---------------------------------------------------------------------------

def test_db_check_constraint_rejects_core_without_certification(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    with pytest.raises(IntegrityError):
        _make_employee(db_session, tenant.id, delivery_engine="CORE", core_certified=False)
    db_session.rollback()

def test_db_check_constraint_allows_core_when_certified(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    emp = _make_employee(db_session, tenant.id, delivery_engine="CORE", core_certified=True)
    assert emp.delivery_engine == "CORE"  # commit inside _make_employee didn't raise

# ---------------------------------------------------------------------------
# convert_candidate_to_employee -- BR: all new hires enter SPECIALITY
# ---------------------------------------------------------------------------

def _make_candidate(db, candidate_id="C-CONVERT"):
    candidate = Candidate(
        candidateID=candidate_id, candidateEmail=f"{candidate_id}@example.com", candidatePassword="h",
        candidateFirstName="Arjun", candidateLastName="Rao",
    )
    db.add(candidate)
    db.commit()
    return candidate

def test_convert_candidate_to_employee_always_enters_speciality(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    candidate = _make_candidate(db_session)

    employee = convert_candidate_to_employee(
        db_session, candidate, joining_date=date(2026, 2, 1), tenant_id=tenant.id, changed_by="U-HR",
    )
    db_session.commit()

    assert employee.delivery_engine == "SPECIALITY"
    assert employee.core_certified is False
    assert employee.candidate_id == candidate.candidateID

def test_convert_rejects_explicit_core_request(db_session):
    """AC-2: an attempt to set CORE on a new hire is rejected, even via
    a caller-supplied field, not just silently downgraded to SPECIALITY."""
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    candidate = _make_candidate(db_session)

    with pytest.raises(CoreAssignmentNotAllowed):
        convert_candidate_to_employee(
            db_session, candidate, joining_date=date(2026, 2, 1), tenant_id=tenant.id,
            delivery_engine="CORE",
        )

def test_convert_writes_initial_engine_history(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    candidate = _make_candidate(db_session)

    employee = convert_candidate_to_employee(
        db_session, candidate, joining_date=date(2026, 2, 1), tenant_id=tenant.id, changed_by="U-HR",
    )
    db_session.commit()

    history = db_session.query(EmployeeEngineHistory).filter(EmployeeEngineHistory.employee_id == employee.id).all()
    assert len(history) == 1
    assert history[0].from_engine is None
    assert history[0].to_engine == "SPECIALITY"

# ---------------------------------------------------------------------------
# set_core_delivery_engine -- the ONLY path to CORE
# ---------------------------------------------------------------------------

def test_set_core_requires_certification_first(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    emp = _make_employee(db_session, tenant.id, core_certified=False)

    with pytest.raises(CoreAssignmentNotAllowed):
        set_core_delivery_engine(
            db_session, emp, approval_reference="CEG-0847", changed_by="U-BUH", reason="Approved",
        )
    assert emp.delivery_engine == "SPECIALITY"

def test_set_core_requires_approval_reference(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    emp = _make_employee(db_session, tenant.id, core_certified=True)

    with pytest.raises(CoreAssignmentNotAllowed):
        set_core_delivery_engine(db_session, emp, approval_reference="", changed_by="U-BUH", reason="Approved")

def test_set_core_succeeds_when_certified_with_approval(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    emp = _make_employee(db_session, tenant.id, core_certified=True)

    set_core_delivery_engine(
        db_session, emp, approval_reference="CEG-0847", changed_by="U-BUH",
        reason="Core Eligibility Gate approved.",
    )
    db_session.commit()

    assert emp.delivery_engine == "CORE"
    history = db_session.query(EmployeeEngineHistory).filter(EmployeeEngineHistory.employee_id == emp.id).all()
    assert len(history) == 1
    assert history[0].from_engine == "SPECIALITY"
    assert history[0].to_engine == "CORE"
    assert history[0].approval_reference == "CEG-0847"

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
