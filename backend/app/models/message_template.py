"""
import logging
S-014/HRMS-0414 -- Message Template Engine.

tenant_id here follows this subsystem's real convention (the org-owner
Users.UserID -- see ai_conversation_service.resolve_thunder_config's
docstring), not the separate app.models.tenant.Tenant table.
"""
import logging
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base

TEMPLATE_CHANNELS = ("WHATSAPP", "EMAIL", "PORTAL", "ANY")

# Fixed system keys only -- BR: "Fixed system keys only. No freetext
# entry. Prevents breaking system references." Extend this tuple (and
# the matching migration widening the CHECK constraint) as more
# first-engagement/templated sends get built.
TEMPLATE_KEYS = ("GREETING_WHATSAPP", "GREETING_EMAIL", "EMPLOYEE_WELCOME_EMAIL")

logger = logging.getLogger(__name__)

class MessageTemplate(Base):
    __tablename__ = "message_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "template_key", "version", "channel", name="uq_message_template_version"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)

    template_key = Column(
        Enum(*TEMPLATE_KEYS, name="message_template_key", native_enum=False, create_constraint=True),
        nullable=False, index=True,
    )
    template_name = Column(String(512), nullable=False)
    channel = Column(
        Enum(*TEMPLATE_CHANNELS, name="message_template_channel", native_enum=False, create_constraint=True),
        nullable=False,
    )
    language = Column(String(10), nullable=False, default="en", server_default="en")
    subject = Column(String(512), nullable=True)
    body = Column(Text, nullable=False)

    version = Column(Integer, nullable=False, default = True)
    # BR-01: only one is_active=true per (tenant_id, template_key,
    # channel) -- enforced in application logic (activate_template()),
    # not a DB constraint (a partial/filtered unique index would need
    # per-dialect syntax; the same tradeoff this codebase already made
    # for users.whatsapp_number's own filtered-unique case is *not*
    # repeated here since is_active flips on EVERY row, not just
    # NULL-vs-not -- render_template()'s own ambiguity check is the
    # real safety net if this is ever violated).
    is_active = Column(Boolean, nullable=False, default=False, server_default="0")

    created_by = Column(String(512), nullable=True)
    approved_by = Column(String(512), nullable=True)
    approved_at = Column(DateTime(timezone=False), nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
