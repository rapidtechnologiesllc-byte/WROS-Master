"""
S-372/HRMS-0528 Confirmed vs Potential Demand Workflow
import logging
(app.services.demand_confirmation_service).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.client import Client
from app.models.demand import Demand, DemandHistory
from app.models.demand_confirmation import DemandAlignmentCall
from app.models.employee import Employee, EmployeeEmploymentHistory
from app.models.notification import Notification
from app.models.tenant import Tenant
from app.models.user import Users

from app.services.demand_confirmation_service import (
    FitConfirmationAlreadyRecorded,
    InvalidParticipant,
    SOWReferenceRequired,
    SpecialtyClientReleaseNotAllowed,
    confirm_demand_with_sow,
    confirm_fit,
    schedule_alignment_call,
    trigger_specialty_client_release,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, Client.__table__,
        Demand.__table__, DemandHistory.__table__,
        Employee.__table__, EmployeeEmploymentHistory.__table__,
        Notification.__table__, DemandAlignmentCall.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def fixtures(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    client = Client(tenant_id=tenant.id, company_name="Acme Insurance")
    db_session.add(client)
    db_session.commit()

    demand = Demand(
        tenant_id=tenant.id, client_id=client.id, job_title="Sr. Guidewire Developer",
        required_skills="[]", min_experience_years=5.0, work_location="REMOTE",
        status="OPEN", billing_rate_usd_cents=15000,
    )
    db_session.add(demand)
    db_session.commit()

    employee = Employee(
        tenant_id=tenant.id, first_name="Sam", last_name="Lee", email="sam@blitzenx.com",
        joining_date=date(2025, 1, 1), status="ALLOCATED", core_certified=True,
    )
    db_session.add(employee)
    db_session.commit()

    return tenant, client, demand, employee


# ---------------------------------------------------------------------------
# confirm_demand_with_sow -- AC-6
# ---------------------------------------------------------------------------

def test_confirm_demand_requires_sow_reference(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    with pytest.raises(SOWReferenceRequired):
        confirm_demand_with_sow(db_session, demand, sow_reference="")


def test_confirm_demand_requires_non_whitespace_sow_reference(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    with pytest.raises(SOWReferenceRequired):
        confirm_demand_with_sow(db_session, demand, sow_reference="   ")


def test_confirm_demand_sets_confirmed_status(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    assert demand.confirmation_status == "POTENTIAL"

    confirm_demand_with_sow(db_session, demand, sow_reference="SOW-2026-001", sow_received_date=date(2026, 7, 1))
    db_session.commit()

    assert demand.confirmation_status == "CONFIRMED"
    assert demand.sow_reference == "SOW-2026-001"
    assert demand.sow_received_date == date(2026, 7, 1)


def test_confirm_demand_defaults_sow_date_to_today(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    confirm_demand_with_sow(db_session, demand, sow_reference="SOW-2026-002")
    assert demand.sow_received_date == date.today()


# ---------------------------------------------------------------------------
# schedule_alignment_call -- AC-3
# ---------------------------------------------------------------------------

def test_schedule_alignment_call_uses_injected_scheduler(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    fixed_time = datetime(2026, 7, 22, 15, 0, 0)

    call = schedule_alignment_call(
        db_session, demand, employee, curtis_user_id="U-CURTIS", bu_head_user_id="U-BUHEAD",
        scheduler=lambda c, b, e: fixed_time,
    )

    assert call.scheduled_at == fixed_time
    assert call.curtis_user_id == "U-CURTIS"
    assert call.bu_head_user_id == "U-BUHEAD"


def test_schedule_alignment_call_defaults_to_same_day_without_scheduler(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    before = datetime.utcnow()
    call = schedule_alignment_call(db_session, demand, employee)
    after = datetime.utcnow()

    assert before <= call.scheduled_at <= after


def test_schedule_alignment_call_is_idempotent(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    first = schedule_alignment_call(db_session, demand, employee)
    db_session.commit()
    second = schedule_alignment_call(db_session, demand, employee)

    assert first.id == second.id
    assert db_session.query(DemandAlignmentCall).count() == 1


# ---------------------------------------------------------------------------
# confirm_fit -- AC-4/AC-5 + employee decision is final
# ---------------------------------------------------------------------------

def test_confirm_fit_rejects_invalid_participant(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    call = schedule_alignment_call(db_session, demand, employee)
    with pytest.raises(InvalidParticipant):
        confirm_fit(db_session, call, participant="RECRUITER", confirmed=True)


def test_confirm_fit_records_employee_confirmation(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    call = schedule_alignment_call(db_session, demand, employee)

    confirm_fit(db_session, call, participant="EMPLOYEE", confirmed=True, notes="Excited about this")

    assert call.employee_fit_confirmed is True
    assert call.employee_fit_confirmed_at is not None
    assert call.employee_fit_notes == "Excited about this"


def test_confirm_fit_records_employee_decline_without_penalty(db_session, fixtures):
    """An employee saying no is a legitimate, recorded outcome -- not an error."""
    tenant, client, demand, employee = fixtures
    call = schedule_alignment_call(db_session, demand, employee)

    result = confirm_fit(db_session, call, participant="EMPLOYEE", confirmed=False, notes="Not interested right now")
    assert result.employee_fit_confirmed is False


def test_confirm_fit_cannot_be_overridden_once_recorded(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    call = schedule_alignment_call(db_session, demand, employee)
    confirm_fit(db_session, call, participant="EMPLOYEE", confirmed=False)
    db_session.commit()

    with pytest.raises(FitConfirmationAlreadyRecorded):
        confirm_fit(db_session, call, participant="EMPLOYEE", confirmed=True)


def test_bu_head_and_employee_confirmations_are_independent(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    call = schedule_alignment_call(db_session, demand, employee)

    confirm_fit(db_session, call, participant="BU_HEAD", confirmed=True)
    assert call.employee_fit_confirmed is None  # unaffected

    confirm_fit(db_session, call, participant="EMPLOYEE", confirmed=True)
    assert call.bu_head_fit_confirmed is True
    assert call.employee_fit_confirmed is True


# ---------------------------------------------------------------------------
# trigger_specialty_client_release -- the hard sequence gate
# ---------------------------------------------------------------------------

def test_release_blocked_when_demand_not_confirmed(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    call = schedule_alignment_call(db_session, demand, employee)
    confirm_fit(db_session, call, participant="EMPLOYEE", confirmed=True)
    confirm_fit(db_session, call, participant="BU_HEAD", confirmed=True)

    with pytest.raises(SpecialtyClientReleaseNotAllowed):
        trigger_specialty_client_release(db_session, call, demand)


def test_release_blocked_without_both_fit_confirmations(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    confirm_demand_with_sow(db_session, demand, sow_reference="SOW-2026-003")
    call = schedule_alignment_call(db_session, demand, employee)
    confirm_fit(db_session, call, participant="EMPLOYEE", confirmed=True)
    # BU Head hasn't confirmed yet.

    with pytest.raises(SpecialtyClientReleaseNotAllowed):
        trigger_specialty_client_release(db_session, call, demand)


def test_release_blocked_when_employee_declined(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    confirm_demand_with_sow(db_session, demand, sow_reference="SOW-2026-004")
    call = schedule_alignment_call(db_session, demand, employee)
    confirm_fit(db_session, call, participant="EMPLOYEE", confirmed=False)
    confirm_fit(db_session, call, participant="BU_HEAD", confirmed=True)

    with pytest.raises(SpecialtyClientReleaseNotAllowed):
        trigger_specialty_client_release(db_session, call, demand)


def test_release_succeeds_once_full_sequence_complete(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    confirm_demand_with_sow(db_session, demand, sow_reference="SOW-2026-005")
    call = schedule_alignment_call(db_session, demand, employee)
    confirm_fit(db_session, call, participant="EMPLOYEE", confirmed=True)
    confirm_fit(db_session, call, participant="BU_HEAD", confirmed=True)
    db_session.commit()

    result = trigger_specialty_client_release(db_session, call, demand)

    assert result.specialty_client_release_triggered_at is not None


def test_release_notifies_speciality_rm_not_client_directly(db_session, fixtures):
    tenant, client, demand, employee = fixtures
    rm = Users(UserID="U-RM", UserRole="Recruiter", UserEmail="rm@blitzenx.com", UserPassword="h", tenant_id=tenant.id)
    db_session.add(rm)
    db_session.commit()

    confirm_demand_with_sow(db_session, demand, sow_reference="SOW-2026-006")
    call = schedule_alignment_call(db_session, demand, employee)
    confirm_fit(db_session, call, participant="EMPLOYEE", confirmed=True)
    confirm_fit(db_session, call, participant="BU_HEAD", confirmed=True)
    db_session.commit()

    trigger_specialty_client_release(db_session, call, demand, speciality_rm=rm, tenant_id=tenant.id)
    db_session.commit()

    notification = db_session.query(Notification).first()
    assert notification is not None
    assert notification.recipient_id == "U-RM"
