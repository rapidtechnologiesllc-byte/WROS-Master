"""
Email template rendering service with dynamic field support.

Supports rendering templates from the message_templates table with
dynamic field substitution. Fields are specified as {{field_name}} in
template body and replaced with values from the context dict.
"""
import logging
from sqlalchemy.orm import Session
from app.models.message_template import MessageTemplate

logger = logging.getLogger(__name__)


class TemplateService:
    """Service for rendering email templates with dynamic fields."""

    @staticmethod
    def render_template(
        db: Session,
        tenant_id: str,
        template_key: str,
        channel: str,
        context: dict = None,
    ) -> str:
        """
        Render an email template with dynamic field substitution.

        Args:
            db: Database session
            tenant_id: Tenant ID (org owner)
            template_key: Template key (e.g., "EMPLOYEE_WELCOME_EMAIL")
            channel: Channel (e.g., "EMAIL")
            context: Dictionary of field values to substitute

        Returns:
            Rendered template body with fields substituted, or None if template not found
        """
        if context is None:
            context = {}

        # Get active template
        template = db.query(MessageTemplate).filter(
            MessageTemplate.tenant_id == tenant_id,
            MessageTemplate.template_key == template_key,
            MessageTemplate.channel == channel,
            MessageTemplate.is_active == True,
        ).first()

        if not template:
            logger.warning(
                f"No active template found for {template_key} ({channel}) in tenant {tenant_id}"
            )
            return None

        # Render body with field substitution
        body = template.body
        for field_name, field_value in context.items():
            placeholder = "{{" + field_name + "}}"
            body = body.replace(placeholder, str(field_value))

        return body

    @staticmethod
    def get_template(
        db: Session,
        tenant_id: str,
        template_key: str,
        channel: str,
    ):
        """Get the active template for a given key and channel."""
        return db.query(MessageTemplate).filter(
            MessageTemplate.tenant_id == tenant_id,
            MessageTemplate.template_key == template_key,
            MessageTemplate.channel == channel,
            MessageTemplate.is_active == True,
        ).first()

    @staticmethod
    def create_template(
        db: Session,
        tenant_id: str,
        template_key: str,
        template_name: str,
        channel: str,
        subject: str,
        body: str,
        created_by: str,
    ):
        """Create a new template version."""
        # Get next version number
        latest = db.query(MessageTemplate).filter(
            MessageTemplate.tenant_id == tenant_id,
            MessageTemplate.template_key == template_key,
            MessageTemplate.channel == channel,
        ).order_by(MessageTemplate.version.desc()).first()

        next_version = (latest.version + 1) if latest else 1

        template = MessageTemplate(
            tenant_id=tenant_id,
            template_key=template_key,
            template_name=template_name,
            channel=channel,
            subject=subject,
            body=body,
            version=next_version,
            is_active=False,
            created_by=created_by,
        )

        db.add(template)
        db.commit()
        db.refresh(template)

        return template

    @staticmethod
    def activate_template(db: Session, template_id: int) -> bool:
        """Activate a template and deactivate others in the same group."""
        template = db.query(MessageTemplate).filter(
            MessageTemplate.id == template_id
        ).first()

        if not template:
            return False

        # Deactivate all other templates in the same group
        db.query(MessageTemplate).filter(
            MessageTemplate.tenant_id == template.tenant_id,
            MessageTemplate.template_key == template.template_key,
            MessageTemplate.channel == template.channel,
            MessageTemplate.id != template_id,
        ).update({MessageTemplate.is_active: False})

        # Activate this template
        template.is_active = True
        db.add(template)
        db.commit()

        return True

    @staticmethod
    def list_templates(db: Session, tenant_id: str, template_key: str = None):
        """List all template versions for a tenant, optionally filtered by key."""
        query = db.query(MessageTemplate).filter(
            MessageTemplate.tenant_id == tenant_id
        )

        if template_key:
            query = query.filter(MessageTemplate.template_key == template_key)

        return query.order_by(
            MessageTemplate.template_key,
            MessageTemplate.channel,
            MessageTemplate.version.desc(),
        ).all()
