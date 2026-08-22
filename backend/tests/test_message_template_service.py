"""
S-014/HRMS-0414 -- Message Template Engine (app.services.message_template_service).

"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.message_template_service as svc
from app.models.base import Base
from app.models.candidate import Candidate
from app.models.message_template import MessageTemplate
from app.models.user import Users

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

@pytest.fixture()
def tenant(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    db_session.add(owner)
    db_session.commit()
    return owner

def test_create_template_version_starts_at_1_inactive(db_session, tenant):
    t = svc.create_template_version(
        db_session, tenant_id="U-ORG", template_key="GREETING_WHATSAPP", template_name="Standard Greeting",
        channel="WHATSAPP", body="Hi {{candidate_name}}!",
    )
    assert t.version == 1
    assert t.is_active is False

def test_create_template_version_increments(db_session, tenant):
    svc.create_template_version(db_session, tenant_id="U-ORG", template_key="GREETING_WHATSAPP", template_name="V1", channel="WHATSAPP", body="Hi {{candidate_name}}")
    t2 = svc.create_template_version(db_session, tenant_id="U-ORG", template_key="GREETING_WHATSAPP", template_name="V2", channel="WHATSAPP", body="Hey {{candidate_name}}")
    assert t2.version == 2

def test_create_template_unknown_key_rejected(db_session, tenant):
    with pytest.raises(ValueError):
        svc.create_template_version(db_session, tenant_id="U-ORG", template_key="NOT_A_REAL_KEY", template_name="X", channel="WHATSAPP", body="hi")

def test_activate_deactivates_previous_version(db_session, tenant):
    t1 = svc.create_template_version(db_session, tenant_id="U-ORG", template_key="GREETING_WHATSAPP", template_name="V1", channel="WHATSAPP", body="Hi {{candidate_name}}")
    svc.activate_template(db_session, t1.id, activated_by="U-ORG")
    t2 = svc.create_template_version(db_session, tenant_id="U-ORG", template_key="GREETING_WHATSAPP", template_name="V2", channel="WHATSAPP", body="Hey {{candidate_name}}")
    svc.activate_template(db_session, t2.id, activated_by="U-ORG")

    db_session.refresh(t1)
    db_session.refresh(t2)
    assert t1.is_active is False
    assert t2.is_active is True

def test_activate_records_approved_by(db_session, tenant):
    t1 = svc.create_template_version(db_session, tenant_id="U-ORG", template_key="GREETING_WHATSAPP", template_name="V1", channel="WHATSAPP", body="Hi {{candidate_name}}")
    activated = svc.activate_template(db_session, t1.id, activated_by="U-ADMIN")
    assert activated.approved_by == "U-ADMIN"
    assert activated.approved_at is not None

def test_render_template_happy_path(db_session, tenant):
    t = svc.create_template_version(db_session, tenant_id="U-ORG", template_key="GREETING_WHATSAPP", template_name="V1", channel="WHATSAPP", body="Hi {{candidate_name}}, I am {{agent_name}} from {{company_name}}.")
    svc.activate_template(db_session, t.id, activated_by="U-ORG")

    result = svc.render_template(db_session, "GREETING_WHATSAPP", "WHATSAPP", "U-ORG", {"candidate_name": "Jordan", "agent_name": "Thunder", "company_name": "BlitzenX"})
    assert result["rendered_body"] == "Hi Jordan, I am Thunder from BlitzenX."
    assert "{" not in result["rendered_body"]

def test_render_template_no_active_raises_not_found(db_session, tenant):
    svc.create_template_version(db_session, tenant_id="U-ORG", template_key="GREETING_WHATSAPP", template_name="V1", channel="WHATSAPP", body="Hi {{candidate_name}}")
    with pytest.raises(svc.TemplateNotFoundError):
        svc.render_template(db_session, "GREETING_WHATSAPP", "WHATSAPP", "U-ORG", {"candidate_name": "Jordan"})

def test_render_template_missing_variable_raises_render_error(db_session, tenant):
    t = svc.create_template_version(db_session, tenant_id="U-ORG", template_key="GREETING_WHATSAPP", template_name="V1", channel="WHATSAPP", body="Hi {{candidate_name}}, from {{company_name}}")
    svc.activate_template(db_session, t.id, activated_by="U-ORG")

    with pytest.raises(svc.TemplateRenderError) as exc_info:
        svc.render_template(db_session, "GREETING_WHATSAPP", "WHATSAPP", "U-ORG", {"candidate_name": "Jordan"})
    assert "company_name" in str(exc_info.value)

def test_render_template_ambiguity_multiple_active_raises_not_found(db_session, tenant):
    t1 = svc.create_template_version(db_session, tenant_id="U-ORG", template_key="GREETING_WHATSAPP", template_name="V1", channel="WHATSAPP", body="Hi {{candidate_name}}")
    t1.is_active = True
    t2 = svc.create_template_version(db_session, tenant_id="U-ORG", template_key="GREETING_WHATSAPP", template_name="V2", channel="WHATSAPP", body="Hey {{candidate_name}}")
    t2.is_active = True
    db_session.commit()

    with pytest.raises(svc.TemplateNotFoundError):
        svc.render_template(db_session, "GREETING_WHATSAPP", "WHATSAPP", "U-ORG", {"candidate_name": "Jordan"})

def test_editing_creates_new_version_does_not_mutate_original(db_session, tenant):
    t1 = svc.create_template_version(db_session, tenant_id="U-ORG", template_key="GREETING_WHATSAPP", template_name="V1", channel="WHATSAPP", body="Original body")
    original_body = t1.body

    svc.create_template_version(db_session, tenant_id="U-ORG", template_key="GREETING_WHATSAPP", template_name="V2", channel="WHATSAPP", body="Edited body")

    db_session.refresh(t1)
    assert t1.body == original_body == "Original body"

def test_preview_template_uses_real_candidate_data(db_session, tenant):
    candidate = Candidate(candidateID="C-100", candidateEmail="cand@example.com", candidatePassword="h", candidateFirstName="Priya")
    db_session.add(candidate)
    db_session.commit()

    t = svc.create_template_version(db_session, tenant_id="U-ORG", template_key="GREETING_WHATSAPP", template_name="V1", channel="WHATSAPP", body="Hi {{candidate_name}}, I am {{agent_name}} from {{company_name}}.")

    result = svc.preview_template(db_session, t.id, "C-100", agent_name="Thunder", company_name="BlitzenX")
    assert result["candidate_name_used"] == "Priya"
    assert "Priya" in result["rendered_body"]
    assert "Thunder" in result["rendered_body"]

def test_list_templates_filters_by_channel(db_session, tenant):
    svc.create_template_version(db_session, tenant_id="U-ORG", template_key="GREETING_WHATSAPP", template_name="WA", channel="WHATSAPP", body="Hi {{candidate_name}}")
    svc.create_template_version(db_session, tenant_id="U-ORG", template_key="GREETING_EMAIL", template_name="Email", channel="EMAIL", body="Hi {{candidate_name}}", subject="Subj")

    whatsapp_only = svc.list_templates(db_session, "U-ORG", channel="WHATSAPP")
    assert len(whatsapp_only) == 1
    assert whatsapp_only[0].channel == "WHATSAPP"
