"""
import logging
S-205/HRMS-0107 -- Business Unit Entity & Context Switching.

Proves: switching to a BU the user actually has access to succeeds
(AC-1/AC-2), a tampered/unauthorized business_unit_id is rejected
(AC-3), only the mapped "All BUs" role can activate the unscoped view
and it writes exactly one real audit_log row per activation
(AC-4/BR-0107-02), and ensure_default_bu_access() seeds the one real
default row a user should always have without duplicating it.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.bu_access import BUAccess
from app.models.rbac_template import BusinessUnit
from app.models.tenant import Tenant
from app.models.user import Users

import app.services.bu_context_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, BusinessUnit.__table__, Users.__table__, BUAccess.__table__, AuditLog.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def seeded(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    bu_east = BusinessUnit(name="BXUS-East", tenant_id=tenant.id, continent="NA")
    bu_west = BusinessUnit(name="BXUS-West", tenant_id=tenant.id, continent="NA")
    db_session.add_all([bu_east, bu_west])
    db_session.commit()

    single_bu_user = Users(UserID="U1", UserRole="Recruiter", UserName="Single", UserEmail="single@blitzenx.com", UserPassword="h", tenant_id=tenant.id, business_unit_id=bu_east.id)
    multi_bu_user = Users(UserID="U2", UserRole="BU Head", UserName="Multi", UserEmail="multi@blitzenx.com", UserPassword="h", tenant_id=tenant.id, business_unit_id=bu_east.id)
    director = Users(UserID="U3", UserRole="Super User", UserName="Avinash", UserEmail="avinash@blitzenx.com", UserPassword="h", tenant_id=tenant.id)
    db_session.add_all([single_bu_user, multi_bu_user, director])
    db_session.commit()

    db_session.add_all([
        BUAccess(user_id="U2", business_unit_id=bu_east.id, is_default=True),
        BUAccess(user_id="U2", business_unit_id=bu_west.id, is_default=False),
    ])
    db_session.commit()

    return {"tenant": tenant, "bu_east": bu_east, "bu_west": bu_west, "single": single_bu_user, "multi": multi_bu_user, "director": director}


def test_ensure_default_bu_access_seeds_home_bu(db_session, seeded):
    access = svc.ensure_default_bu_access(db_session, seeded["single"])
    assert access.business_unit_id == seeded["bu_east"].id
    assert access.is_default is True


def test_ensure_default_bu_access_is_idempotent(db_session, seeded):
    svc.ensure_default_bu_access(db_session, seeded["single"])
    svc.ensure_default_bu_access(db_session, seeded["single"])
    rows = svc.get_user_bu_access(db_session, "U1")
    assert len(rows) == 1


def test_multi_bu_user_has_real_multiple_access_rows(db_session, seeded):
    rows = svc.get_user_bu_access(db_session, "U2")
    assert len(rows) == 2
    assert {r.business_unit_id for r in rows} == {seeded["bu_east"].id, seeded["bu_west"].id}


def test_switch_to_accessible_bu_succeeds(db_session, seeded):
    result = svc.switch_active_bu(db_session, seeded["multi"], seeded["bu_west"].id)
    assert result.business_unit_id == seeded["bu_west"].id


def test_switch_to_unauthorized_bu_rejected(db_session, seeded):
    with pytest.raises(svc.NotYourBusinessUnit):
        svc.switch_active_bu(db_session, seeded["single"], seeded["bu_west"].id)


def test_validate_active_bu_rejects_tampered_id(db_session, seeded):
    with pytest.raises(svc.NotYourBusinessUnit):
        svc.validate_active_bu(db_session, "U1", 99999)


def test_only_all_bus_role_can_activate_unscoped_view(db_session, seeded):
    with pytest.raises(svc.NotAuthorizedForAllBUs):
        svc.activate_all_bus_view(db_session, seeded["multi"])


def test_all_bus_activation_writes_exactly_one_audit_row(db_session, seeded):
    svc.activate_all_bus_view(db_session, seeded["director"])
    rows = db_session.query(AuditLog).filter(AuditLog.entity_type == "bu_context", AuditLog.action == "all_bus_view_activated").all()
    assert len(rows) == 1
    assert rows[0].user_id == "U3"
