"""
S-077/HRMS-0477 -- Tenant AI Configuration.

Real architecture under test (see tenant_ai_config_service module
docstring): get_tenant_ai_config() unifies the 4 Thunder-identity/pause
fields already living on Users (S-011/S-065/S-075) with the genuinely
new TenantAIConfig row -- never a second store for the same setting.
BR-01 (persona change requires ba_approved) and the follow_up_hours/
max_followup_count wiring into follow_up_scheduler_service are covered
directly.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.follow_up_schedule import FollowUpSchedule
from app.models.tenant_ai_config import TenantAIConfig, TenantAIConfigChangeLog
from app.models.user import Users

import app.services.tenant_ai_config_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__,
        FollowUpSchedule.__table__, TenantAIConfig.__table__, TenantAIConfigChangeLog.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)
        svc._CONFIG_CACHE.clear()


@pytest.fixture()
def tenant(db_session):
    user = Users(
        UserID="U-ORG", UserRole="Super User", UserEmail="org@blitzenx.com", UserPassword="h",
        tenant_id=None, ai_agent_name="Thunder", ai_agent_persona="I am Thunder.",
        digest_enabled=True, thunder_enabled=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_get_creates_config_row_with_defaults_on_first_read(db_session, tenant):
    cfg = svc.get_tenant_ai_config(db_session, "U-ORG", use_cache=False)

    assert cfg["ai_agent_name"] == "Thunder"
    assert cfg["ai_agent_persona"] == "I am Thunder."
    assert cfg["digest_enabled"] is True
    assert cfg["thunder_enabled"] is True
    assert cfg["greeting_channel"] == "BOTH_PARALLEL"
    assert cfg["whatsapp_followup_hours"] == 24
    assert cfg["email_followup_hours"] == 48
    assert cfg["max_followup_count"] == 3
    assert cfg["ghosting_reactivation_days"] == 14
    assert cfg["digest_send_time"] == "08:00"
    assert cfg["sla_first_contact_seconds"] == 60
    assert cfg["sla_no_contact_hours"] == 24

    row = db_session.query(TenantAIConfig).filter(TenantAIConfig.tenant_id == "U-ORG").first()
    assert row is not None


def test_unknown_tenant_raises(db_session):
    with pytest.raises(ValueError):
        svc.get_tenant_ai_config(db_session, "U-NOBODY", use_cache=False)


def test_update_user_backed_field_writes_to_users_not_new_table(db_session, tenant):
    svc.update_tenant_ai_config(db_session, "U-ORG", {"thunder_enabled": False}, updated_by="U-ADMIN")
    db_session.refresh(tenant)
    assert tenant.thunder_enabled is False

    config_row = db_session.query(TenantAIConfig).filter(TenantAIConfig.tenant_id == "U-ORG").first()
    # thunder_enabled is never duplicated onto the new table.
    assert not hasattr(config_row, "thunder_enabled")


def test_update_new_field_writes_to_tenant_ai_config_row(db_session, tenant):
    svc.update_tenant_ai_config(db_session, "U-ORG", {"whatsapp_followup_hours": 12}, updated_by="U-ADMIN")
    cfg = svc.get_tenant_ai_config(db_session, "U-ORG", use_cache=False)
    assert cfg["whatsapp_followup_hours"] == 12
    assert tenant.thunder_enabled is True  # untouched


def test_persona_change_without_ba_approval_rejected(db_session, tenant):
    with pytest.raises(svc.PersonaChangeRequiresApproval):
        svc.update_tenant_ai_config(db_session, "U-ORG", {"ai_agent_persona": "New persona"}, updated_by="U-ADMIN")
    db_session.refresh(tenant)
    assert tenant.ai_agent_persona == "I am Thunder."  # unchanged


def test_persona_change_with_ba_approval_succeeds(db_session, tenant):
    svc.update_tenant_ai_config(
        db_session, "U-ORG", {"ai_agent_persona": "New persona"}, updated_by="U-ADMIN", ba_approved=True,
    )
    db_session.refresh(tenant)
    assert tenant.ai_agent_persona == "New persona"


def test_invalid_greeting_channel_rejected(db_session, tenant):
    with pytest.raises(svc.InvalidTenantAIConfigField):
        svc.update_tenant_ai_config(db_session, "U-ORG", {"greeting_channel": "CARRIER_PIGEON"}, updated_by="U-ADMIN")


def test_unknown_field_rejected(db_session, tenant):
    with pytest.raises(svc.InvalidTenantAIConfigField):
        svc.update_tenant_ai_config(db_session, "U-ORG", {"not_a_real_field": 1}, updated_by="U-ADMIN")


def test_update_logs_change_with_before_after_state(db_session, tenant):
    svc.update_tenant_ai_config(db_session, "U-ORG", {"max_followup_count": 5}, updated_by="U-ADMIN")
    logs = db_session.query(TenantAIConfigChangeLog).filter(TenantAIConfigChangeLog.tenant_id == "U-ORG").all()
    assert len(logs) == 1
    assert logs[0].changed_fields == {"max_followup_count": {"before": 3, "after": 5}}
    assert logs[0].updated_by == "U-ADMIN"


def test_no_op_update_does_not_log(db_session, tenant):
    svc.update_tenant_ai_config(db_session, "U-ORG", {"max_followup_count": 3}, updated_by="U-ADMIN")  # already 3
    logs = db_session.query(TenantAIConfigChangeLog).filter(TenantAIConfigChangeLog.tenant_id == "U-ORG").all()
    assert len(logs) == 0


def test_cache_invalidated_on_update(db_session, tenant):
    first = svc.get_tenant_ai_config(db_session, "U-ORG")
    assert first["max_followup_count"] == 3

    svc.update_tenant_ai_config(db_session, "U-ORG", {"max_followup_count": 7}, updated_by="U-ADMIN")

    second = svc.get_tenant_ai_config(db_session, "U-ORG")  # cache should be invalidated
    assert second["max_followup_count"] == 7


def test_cache_returns_stale_value_within_ttl_when_bypassing_update_path(db_session, tenant):
    svc.get_tenant_ai_config(db_session, "U-ORG")  # populates cache
    # Mutate the DB row directly, bypassing update_tenant_ai_config() (which invalidates).
    row = db_session.query(TenantAIConfig).filter(TenantAIConfig.tenant_id == "U-ORG").first()
    row.max_followup_count = 99
    db_session.commit()

    cached = svc.get_tenant_ai_config(db_session, "U-ORG")
    assert cached["max_followup_count"] == 3  # still the cached value

    svc.invalidate_tenant_ai_config_cache("U-ORG")
    fresh = svc.get_tenant_ai_config(db_session, "U-ORG")
    assert fresh["max_followup_count"] == 99


def test_escalation_keywords_merge_with_builtin_legal_list(db_session, tenant):
    svc.update_tenant_ai_config(
        db_session, "U-ORG", {"escalation_keywords": ["harassment", "compensation dispute"]}, updated_by="U-ADMIN",
    )
    keywords = svc.get_escalation_keywords(db_session, "U-ORG")
    assert "harassment" in keywords
    assert "compensation dispute" in keywords


def test_followup_hours_for_channel_reads_real_tenant_config():
    """S-077 wiring into follow_up_scheduler_service.followup_hours_for_channel()."""
    from app.services.follow_up_scheduler_service import followup_hours_for_channel

    # Falls back to the module constant default when no db/tenant_id given.
    assert followup_hours_for_channel("whatsapp") == 24
    assert followup_hours_for_channel("email") == 48


def test_followup_hours_for_channel_uses_tenant_override(db_session, tenant):
    from app.services.follow_up_scheduler_service import followup_hours_for_channel

    svc.update_tenant_ai_config(db_session, "U-ORG", {"whatsapp_followup_hours": 6}, updated_by="U-ADMIN")
    assert followup_hours_for_channel("whatsapp", db_session, "U-ORG") == 6
    assert followup_hours_for_channel("email", db_session, "U-ORG") == 48  # unchanged


def test_max_followup_count_for_tenant_uses_tenant_override(db_session, tenant):
    from app.services.follow_up_scheduler_service import max_followup_count_for_tenant

    assert max_followup_count_for_tenant(db_session, "U-ORG") == 3
    svc.update_tenant_ai_config(db_session, "U-ORG", {"max_followup_count": 8}, updated_by="U-ADMIN")
    assert max_followup_count_for_tenant(db_session, "U-ORG") == 8


def test_schedule_follow_up_respects_tenant_max_followup_count(db_session, tenant):
    from app.services.follow_up_scheduler_service import schedule_follow_up

    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    db_session.add(candidate)
    db_session.commit()
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder")
    db_session.add(conv)
    db_session.commit()

    svc.update_tenant_ai_config(db_session, "U-ORG", {"max_followup_count": 1}, updated_by="U-ADMIN")

    result = schedule_follow_up(db_session, "C-1", "U-ORG", conv.id, "whatsapp", None, 2)  # #2 exceeds the new max of 1
    assert result is None
