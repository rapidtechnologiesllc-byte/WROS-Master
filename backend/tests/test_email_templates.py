"""Candidate stage email templates (Templates & Checklists > Email Templates).

The server owns the stage list and the placeholder syntax; the preview substitutes exactly the
placeholders the screen tells the user to write (the screen used to say "[Candidate Name]" while
the server replaced "{{candidate_name}}", so previews never filled in).
"""
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.email_templates import (PLACEHOLDERS, STAGES, StageTemplateUpdate,
                                                  list_stage_templates, preview_stage_template,
                                                  save_stage_template)
from app.models.email_template import EmailTemplate
from app.models.role_template import RoleTemplate
from app.models.tenant import Tenant
from app.models.user import Users


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _user(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    uid = uuid.uuid4().hex[:8]
    role = RoleTemplate(tenant_id=1, name=f"tpl-{uid}", display_name="Templates", hierarchy_level=5, enabled=True)
    db.add(role)
    db.flush()
    user = Users(UserID=f"U-{uid}", UserName="Templates", UserEmail=f"t{uid}@x.com", UserPassword="x",
                 UserRole="x", tenant_id=1, role_template_id=role.id)
    db.add(user)
    db.flush()
    return user


def _clear(db):
    db.query(EmailTemplate).filter(EmailTemplate.name.like("stage_%")).delete(synchronize_session=False)
    db.flush()


def test_list_returns_the_stages_and_placeholders_the_screen_renders(db):
    _clear(db)
    data = list_stage_templates(db=db)
    assert data["stages"] == [{"key": key, "label": label} for key, label in STAGES.items()]
    assert data["placeholders"] == ["{{candidate_name}}", "{{job_title}}"]
    assert data["templates"] == []


def test_save_then_preview_substitutes_the_advertised_placeholders(db):
    _clear(db)
    user = _user(db)
    body = StageTemplateUpdate(subject=f"Interview for {PLACEHOLDERS['job_title']}",
                               body_html=f"<p>Hi {PLACEHOLDERS['candidate_name']}</p>")
    saved = save_stage_template("interview", body, db=db, current_user=user)
    assert saved["stage"] == "interview" and saved["version"] == 1 and saved["updated_by"] == user.UserID

    again = save_stage_template("interview", body, db=db, current_user=user)
    assert again["version"] == 2
    assert [t["stage"] for t in list_stage_templates(db=db)["templates"]] == ["interview"]

    preview = preview_stage_template("interview", candidate_name="Asha", job_title="Guidewire Dev", db=db)
    assert preview["subject"] == "Interview for Guidewire Dev"
    assert preview["body_html"] == "<p>Hi Asha</p>"


def test_unknown_stage_and_blank_template_are_refused(db):
    user = _user(db)
    with pytest.raises(HTTPException) as unknown:
        save_stage_template("nope", StageTemplateUpdate(subject="s", body_html="b"), db=db, current_user=user)
    assert unknown.value.status_code == 404
    with pytest.raises(HTTPException) as blank:
        save_stage_template("offer", StageTemplateUpdate(subject="  ", body_html="b"), db=db, current_user=user)
    assert blank.value.status_code == 400


def test_preview_of_an_unsaved_stage_is_404(db):
    _clear(db)
    with pytest.raises(HTTPException) as missing:
        preview_stage_template("hired", db=db)
    assert missing.value.status_code == 404
