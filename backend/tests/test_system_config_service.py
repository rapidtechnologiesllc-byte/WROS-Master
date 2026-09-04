"""
import logging
S-213/HRMS-0115 -- System Configuration & Admin Settings Panel.

Proves: BU-specific override beats tenant default (AC-3/BR-0115-03),
tenant default is used when no BU override exists, an unknown key/an
out-of-range value is rejected (AC-1-adjacent input validation), a
config write produces exactly one audit_log entry with old/new values
(AC-2/BR-0115-02), and the Locale category reads/writes the real Tenant
columns rather than a shadow copy.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.rbac_template import BusinessUnit
from app.models.system_config import SystemConfig
from app.models.tenant import Tenant
from app.models.user import Users

import app.services.system_config_service as svc

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, BusinessUnit.__table__, Users.__table__, SystemConfig.__table__, AuditLog.__table__,
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

    bu = BusinessUnit(name="Delivery", tenant_id=tenant.id)
    db_session.add(bu)
    db_session.commit()

    admin = Users(UserID="U-ADMIN", UserRole="Admin", UserEmail="admin@blitzenx.com", UserPassword="h", tenant_id=tenant.id)
    db_session.add(admin)
    db_session.commit()

    svc.invalidate_config_cache(tenant.id)
    return {"tenant_id": tenant.id, "bu_id": bu.id, "admin_id": admin.UserID}

def test_unconfigured_key_returns_real_default(db_session, seeded):
    value = svc.get_config_value(db_session, tenant_id=seeded["tenant_id"], key="business_hours_start", use_cache=False)
    assert value == 8  # notification_service.BUSINESS_HOURS_START

def test_tenant_default_used_when_no_bu_override(db_session, seeded):
    svc.set_config_value(
        db_session, tenant_id=seeded["tenant_id"], key="business_hours_start", value=9,
        updated_by=seeded["admin_id"], business_unit_id=None,
    )
    value = svc.get_config_value(
        db_session, tenant_id=seeded["tenant_id"], key="business_hours_start",
        business_unit_id=seeded["bu_id"], use_cache=False,
    )
    assert value == 9

def test_bu_override_beats_tenant_default(db_session, seeded):
    svc.set_config_value(
        db_session, tenant_id=seeded["tenant_id"], key="business_hours_start", value=9,
        updated_by=seeded["admin_id"], business_unit_id=None,
    )
    svc.set_config_value(
        db_session, tenant_id=seeded["tenant_id"], key="business_hours_start", value=7,
        updated_by=seeded["admin_id"], business_unit_id=seeded["bu_id"],
    )
    bu_scoped = svc.get_config_value(
        db_session, tenant_id=seeded["tenant_id"], key="business_hours_start",
        business_unit_id=seeded["bu_id"], use_cache=False,
    )
    tenant_scoped = svc.get_config_value(
        db_session, tenant_id=seeded["tenant_id"], key="business_hours_start",
        business_unit_id=None, use_cache=False,
    )
    assert bu_scoped == 7
    assert tenant_scoped == 9

def test_unknown_key_rejected(db_session, seeded):
    with pytest.raises(svc.UnknownConfigKey):
        svc.set_config_value(
            db_session, tenant_id=seeded["tenant_id"], key="not_a_real_key", value=1, updated_by=seeded["admin_id"],
        )

def test_out_of_range_percent_rejected(db_session, seeded):
    with pytest.raises(svc.InvalidConfigValue):
        svc.set_config_value(
            db_session, tenant_id=seeded["tenant_id"], key="low_confidence_threshold", value=1.5,
            updated_by=seeded["admin_id"],
        )

def test_config_write_produces_exactly_one_audit_entry_with_old_and_new(db_session, seeded):
    before_count = db_session.query(AuditLog).count()
    svc.set_config_value(
        db_session, tenant_id=seeded["tenant_id"], key="low_confidence_threshold", value=0.8,
        updated_by=seeded["admin_id"],
    )
    entries = db_session.query(AuditLog).filter(AuditLog.entity_type == "system_config").all()
    assert len(entries) == before_count + 1
    entry = entries[-1]
    assert entry.entity_id == "low_confidence_threshold"
    assert entry.old_value == "None"
    assert entry.new_value == "0.8"
    assert entry.user_id == seeded["admin_id"]

def test_locale_reads_real_tenant_columns_not_a_shadow_copy(db_session, seeded):
    locale = svc.get_locale_config(db_session, seeded["tenant_id"])
    assert locale["default_currency"] == "USD"  # Tenant's own real server_default

    svc.update_locale_config(
        db_session, seeded["tenant_id"], {"default_currency": "INR"}, updated_by=seeded["admin_id"],
    )
    tenant = db_session.query(Tenant).filter(Tenant.id == seeded["tenant_id"]).first()
    assert tenant.default_currency == "INR"  # written straight to Tenant, no shadow row anywhere

def test_locale_rejects_invalid_currency(db_session, seeded):
    with pytest.raises(svc.InvalidConfigValue):
        svc.update_locale_config(
            db_session, seeded["tenant_id"], {"default_currency": "NOT_A_CURRENCY"}, updated_by=seeded["admin_id"],
        )

def test_settings_panel_groups_by_category(db_session, seeded):
    panel = svc.get_settings_panel(db_session, tenant_id=seeded["tenant_id"])
    assert {item["config_key"] for item in panel["AI_THRESHOLDS"]} == {
        "low_confidence_threshold", "profile_update_confidence_threshold", "response_parser_confidence_threshold",
    }
    # No SLA key seeded yet -- see system_config_service's own comment on
    # why (sla_monitoring_service already routes through TenantAIConfig).
    assert panel["SLA"] == []
    assert {item["config_key"] for item in panel["CHANNELS"]} == {"business_hours_start", "business_hours_end"}
    assert panel["LOCALE"]["default_currency"] == "USD"
