"""Every message the system sends to people, in one place (CEO 2026-11-03: "make sure all email, text, whatsapp templates
are all here and is calling this with dynamic fields"). The three stores stay where the senders read them: message
templates (notices, occasions, greetings, versioned), stage email templates, and Thunder's outreach copy. This screen
reads and edits all of them; a field a template uses is listed so nobody has to guess the {{name}}.
"""
import re
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.email_template import EmailTemplate
from app.models.message_template import TEMPLATE_CHANNELS, MessageTemplate
from app.models.thunder_email import ThunderOutreachVariant
from app.models.user import Users

router = APIRouter(prefix="/template-catalog", tags=["template-catalog"])

MUSTACHE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
SINGLE = re.compile(r"(?<!\{)\{(\w+)\}(?!\})")
GROUP_LABELS = (("OCCASION_", "Occasions"), ("CANDIDATE_", "Candidate notices"), ("GREETING_", "First contact"), ("EMPLOYEE_", "Employees"))


class TemplateEdit(BaseModel):
    subject: Optional[str] = None
    body: str
    channel: Optional[str] = None  # message templates: add or change the version for this channel


def _fields(*texts) -> List[str]:
    found = set()
    for text in texts:
        found |= set(MUSTACHE.findall(text or "")) | set(SINGLE.findall(text or ""))
    return sorted(found)


def _group(key: str) -> str:
    return next((label for prefix, label in GROUP_LABELS if key.startswith(prefix)), "Other")


@router.get("", dependencies=[Depends(require_resource_permission("checklists", "view"))],
            summary="Every email, text and WhatsApp template with the fields it uses")
def catalog(db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    from app.services.candidate_status_notifications import seed_templates

    if seed_templates(db, user.tenant_id):  # a tenant that predates a template sees it
        db.commit()
    rows = []
    active = db.query(MessageTemplate).filter(MessageTemplate.tenant_id == str(user.tenant_id), MessageTemplate.is_active.is_(True)).all()
    for t in active:
        rows.append({"store": "message", "id": str(t.id), "key": t.template_key, "name": t.template_name, "group": _group(t.template_key),
                     "channel": t.channel, "subject": t.subject, "body": t.body, "version": t.version, "fields": _fields(t.subject, t.body),
                     "syntax": "{{field}}"})
    for t in db.query(EmailTemplate).filter(EmailTemplate.is_active.is_(True)).all():
        rows.append({"store": "email", "id": t.id, "key": t.name, "name": t.display_name, "group": "Hiring stages" if t.name.startswith("stage_") else "Other",
                     "channel": "EMAIL", "subject": t.subject_template, "body": t.body_template, "version": t.version,
                     "fields": _fields(t.subject_template, t.body_template), "syntax": "{{field}}"})
    for t in db.query(ThunderOutreachVariant).filter(ThunderOutreachVariant.active.is_(True)).all():
        rows.append({"store": "thunder", "id": str(t.id), "key": t.key, "name": f"Thunder step {t.step}: {t.key}", "group": "Thunder outreach",
                     "channel": "EMAIL", "subject": t.subject_template, "body": t.body_template, "version": 1,
                     "fields": _fields(t.subject_template, t.body_template), "syntax": "{field}"})
    return {"templates": sorted(rows, key=lambda r: (r["group"], r["name"])), "channels": [c for c in TEMPLATE_CHANNELS if c != "ANY"]}


@router.put("/{store}/{template_id}", dependencies=[Depends(require_resource_permission("checklists", "edit"))],
            summary="Save a template; message templates keep their earlier versions")
def save(store: str, template_id: str, body: TemplateEdit, db: Session = Depends(get_db),
         user: Users = Depends(get_current_internal_user)):
    from app.services.message_template_service import activate_template, create_template_version

    if not body.body.strip():
        raise HTTPException(status_code=400, detail="A template needs a body.")
    if store == "message":
        current = db.query(MessageTemplate).filter(MessageTemplate.id == int(template_id), MessageTemplate.tenant_id == str(user.tenant_id)).first()
        if current is None:
            raise HTTPException(status_code=404, detail="Template not found.")
        channel = body.channel or current.channel
        if channel not in TEMPLATE_CHANNELS:
            raise HTTPException(status_code=400, detail=f"Channel must be one of {list(TEMPLATE_CHANNELS)}.")
        if channel == "EMAIL" and not (body.subject or "").strip():
            raise HTTPException(status_code=400, detail="An email needs a subject.")
        version = create_template_version(db, tenant_id=current.tenant_id, template_key=current.template_key, template_name=current.template_name,
                                          channel=channel, body=body.body, subject=body.subject, created_by=user.UserID)
        db.flush()
        activate_template(db, version.id, activated_by=user.UserID)
        db.commit()
        return {"id": str(version.id), "version": version.version}
    if store == "email":
        row = db.get(EmailTemplate, template_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Template not found.")
        row.subject_template, row.body_template = body.subject or row.subject_template, body.body
        row.version, row.created_by, row.updated_at = (row.version or 1) + 1, user.UserID, datetime.utcnow()
        db.commit()
        return {"id": row.id, "version": row.version}
    if store == "thunder":
        row = db.get(ThunderOutreachVariant, int(template_id))
        if row is None:
            raise HTTPException(status_code=404, detail="Template not found.")
        try:  # a stray brace would break every email of this step
            (body.subject or row.subject_template).format_map(_AnyField())
            body.body.format_map(_AnyField())
        except (ValueError, IndexError) as exc:
            raise HTTPException(status_code=400, detail=f"Check the {{field}} braces: {exc}")
        row.subject_template, row.body_template = body.subject or row.subject_template, body.body
        db.commit()
        return {"id": str(row.id), "version": 1}
    raise HTTPException(status_code=404, detail="Unknown template store.")


class _AnyField(dict):
    def __missing__(self, key):
        return ""
