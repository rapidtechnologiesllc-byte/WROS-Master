"""Candidate stage email templates (Settings > Templates screen).

One template per pipeline stage, stored in the existing email_template
table as name "stage_<stage>". Subject/body use {{candidate_name}} and
{{job_title}} placeholders. Note: these are the saved templates; sending
them automatically on stage change is a separate feature.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.models.email_template import EmailTemplate
from app.models.user import Users

router = APIRouter(prefix="/email-templates", tags=["email-templates"])

STAGES = ("screening", "interview", "offer", "hired", "rejected")


class StageTemplateUpdate(BaseModel):
    subject: str
    body_html: str


def _stage(stage: str) -> str:
    if stage not in STAGES:
        raise HTTPException(status_code=404, detail=f"Unknown stage {stage!r}; stages: {STAGES}")
    return f"stage_{stage}"


def _item(t: EmailTemplate) -> dict:
    return {
        "stage": t.name.removeprefix("stage_"),
        "subject": t.subject_template,
        "body_html": t.body_template,
        "version": t.version,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "updated_by": t.created_by,
    }


@router.get("", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def list_stage_templates(db: Session = Depends(get_db)):
    rows = db.query(EmailTemplate).filter(EmailTemplate.name.in_([f"stage_{s}" for s in STAGES])).all()
    return {"templates": [_item(t) for t in rows]}


@router.put("/{stage}")
def save_stage_template(
    stage: str,
    body: StageTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("candidates", "edit")),
):
    name = _stage(stage)
    if not body.subject.strip() or not body.body_html.strip():
        raise HTTPException(status_code=400, detail="Subject and body are required")
    template = db.query(EmailTemplate).filter(EmailTemplate.name == name).first()
    if template is None:
        template = EmailTemplate(name=name, display_name=f"{stage.title()} stage email", version=0)
        db.add(template)
    template.subject_template = body.subject
    template.body_template = body.body_html
    template.version = (template.version or 0) + 1
    template.created_by = current_user.UserID
    db.commit()
    db.refresh(template)
    return _item(template)


@router.get("/{stage}/preview", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def preview_stage_template(stage: str, candidate_name: str = "Candidate", job_title: str = "Position", db: Session = Depends(get_db)):
    template = db.query(EmailTemplate).filter(EmailTemplate.name == _stage(stage)).first()
    if template is None:
        raise HTTPException(status_code=404, detail=f"No template saved for the {stage} stage yet")

    def render(text: str) -> str:
        return text.replace("{{candidate_name}}", candidate_name).replace("{{job_title}}", job_title)

    return {"stage": stage, "subject": render(template.subject_template), "body_html": render(template.body_template)}
