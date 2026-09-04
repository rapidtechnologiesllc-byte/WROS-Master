"""
S-014/HRMS-0414 -- Message Template Engine.
"""
import re
from datetime import datetime
import logging
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.message_template import TEMPLATE_KEYS, MessageTemplate

VARIABLE_RE = re.compile(r"\{\{.*?\}\}")

logger = logging.getLogger(__name__)

class TemplateNotFoundError(Exception):
    """No active template for this key+channel+tenant -- caller falls
    back to its own hardcoded default (S-012/S-013's own fallback)."""

class TemplateRenderError(Exception):
    """A {{variable}} survived substitution -- never send this."""

class TemplateActivationConflict(Exception):
    pass

def create_template_version(
    db: Session, *, tenant_id: str, template_key: str, template_name: str,
    channel: str, body: str, subject: Optional[str] = None, language: str = "en",
    created_by: Optional[str] = None,
) -> MessageTemplate:
    """BR-03: editing always creates a new version -- never mutates an
    existing record. Auto-increments version for this (tenant_id,
    template_key, channel) combination."""
    if template_key not in TEMPLATE_KEYS:
        raise ValueError(f"Unknown template_key {template_key!r} -- must be one of {TEMPLATE_KEYS}.")

    latest = (
        db.query(MessageTemplate)
        .filter(
            MessageTemplate.tenant_id == tenant_id,
            MessageTemplate.template_key == template_key,
            MessageTemplate.channel == channel,
        )
        .order_by(MessageTemplate.version.desc())
        .first()
    )
    next_version = (latest.version + 1) if latest else 1

    template = MessageTemplate(
        tenant_id=tenant_id, template_key=template_key, template_name=template_name,
        channel=channel, language=language, subject=subject, body=body,
        version=next_version, is_active=False, created_by=created_by,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template

def list_templates(
    db: Session, tenant_id: str, *, channel: Optional[str] = None, template_key: Optional[str] = None,
) -> List[MessageTemplate]:
    query = db.query(MessageTemplate).filter(MessageTemplate.tenant_id == tenant_id)
    if channel:
        query = query.filter(MessageTemplate.channel == channel)
    if template_key:
        query = query.filter(MessageTemplate.template_key == template_key)
    return query.order_by(MessageTemplate.template_key.asc(), MessageTemplate.channel.asc(), MessageTemplate.version.desc()).all()

def get_template(db: Session, template_id: int) -> Optional[MessageTemplate]:
    return db.query(MessageTemplate).filter(MessageTemplate.id == template_id).first()

def activate_template(db: Session, template_id: int, *, activated_by: str) -> MessageTemplate:
    """BR-01: atomic -- this version becomes the only is_active=true row
    for its (tenant_id, template_key, channel). BR-02's role check is
    the caller's (endpoint-level require_permission), not this
    function's concern."""
    template = get_template(db, template_id)
    if not template:
        raise TemplateActivationConflict(f"Template {template_id} not found.")

    db.query(MessageTemplate).filter(
        MessageTemplate.tenant_id == template.tenant_id,
        MessageTemplate.template_key == template.template_key,
        MessageTemplate.channel == template.channel,
        MessageTemplate.id != template.id,
    ).update({"is_active": False})

    template.is_active = True
    template.approved_by = activated_by
    template.approved_at = datetime.utcnow()
    db.add(template)
    db.commit()
    db.refresh(template)
    return template

def _substitute(text: str, variables: Dict[str, str]) -> str:
    def replace(match: re.Match) -> str:
        name = match.group(0)[2:-2].strip()
        return str(variables.get(name, match.group(0)))
    return re.sub(r"\{\{(.*?)\}\}", replace, text)

def render_template(
    db: Session, template_key: str, channel: str, tenant_id: str, variables: Dict[str, str],
) -> Dict[str, Optional[str]]:
    """
    S-014's renderTemplate(). Raises TemplateNotFoundError if zero OR
    more than one active version exists for this key+channel+tenant
    (BR-01's "ambiguity" case -- both are real safety-net conditions,
    not just "not found"), so the caller's own hardcoded fallback
    always has a well-defined trigger.
    """
    active = (
        db.query(MessageTemplate)
        .filter(
            MessageTemplate.tenant_id == tenant_id,
            MessageTemplate.template_key == template_key,
            MessageTemplate.channel == channel,
            MessageTemplate.is_active == True,
        )
        .all()
    )
    if len(active) != 1:
        if len(active) > 1:
            logger.error(f"[MessageTemplate] TEMPLATE_AMBIGUITY_ERROR: {len(active)} active versions for {template_key}/{channel}/{tenant_id}")
        raise TemplateNotFoundError(f"No single active template for {template_key}/{channel}/tenant {tenant_id}.")

    template = active[0]
    rendered_body = _substitute(template.body, variables)
    rendered_subject = _substitute(template.subject, variables) if template.subject else None

    for label, text in (("body", rendered_body), ("subject", rendered_subject or "")):
        remaining = VARIABLE_RE.findall(text)
        if remaining:
            raise TemplateRenderError(f"Un-replaced variable(s) in {label}: {remaining}")

    return {"rendered_body": rendered_body, "rendered_subject": rendered_subject}

def preview_template(db: Session, template_id: int, candidate_id: str, *, agent_name: str, company_name: str) -> Dict:
    template = get_template(db, template_id)
    if not template:
        raise TemplateNotFoundError(f"Template {template_id} not found.")

    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise ValueError(f"Candidate {candidate_id} not found.")

    candidate_name = candidate.candidateFirstName or candidate.candidateEmail
    variables = {"candidate_name": candidate_name, "agent_name": agent_name, "company_name": company_name}

    rendered_body = _substitute(template.body, variables)
    rendered_subject = _substitute(template.subject, variables) if template.subject else None

    return {
        "rendered_body": rendered_body,
        "rendered_subject": rendered_subject,
        "channel": template.channel,
        "candidate_name_used": candidate_name,
    }
