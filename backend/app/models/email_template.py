"""Email Template Model - Store dynamic email templates for variable substitution"""
from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean
from datetime import datetime
import uuid

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class EmailTemplate(Base):
    """Email template for dynamic rendering with variable substitution"""

    __tablename__ = "email_template"

    id = Column(String(36), primary_key=True, default=_new_uuid)

    # Template identification
    name = Column(String(100), nullable=False, unique=True, index=True)
    display_name = Column(String(150), nullable=False)
    description = Column(Text(), nullable=True)

    # Template content with {{variable}} placeholders
    subject_template = Column(Text(), nullable=False)
    body_template = Column(Text(), nullable=False)

    # Version tracking
    version = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Audit fields
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<EmailTemplate {self.name} v{self.version}>"
