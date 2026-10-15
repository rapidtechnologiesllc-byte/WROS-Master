"""Flash conversations (flash spec B). One ACTIVE conversation per user, kept server-side, so the
bubble resumes after a reload or on another screen. Every Flash discussion lives here: questions,
workflows opened from a deep link (e.g. a Core certification decision) and events Flash posts on
its own (decisions waiting, progress)."""
import uuid

from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func, text

from app.models.base import Base

CONVERSATION_STATUSES = ("ACTIVE", "ARCHIVED")
MESSAGE_ROLES = ("user", "flash", "event")


class FlashConversation(Base):
    __tablename__ = "flash_conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)
    status = Column(Enum(*CONVERSATION_STATUSES, name="flash_conversation_status", native_enum=False,
                         create_constraint=True), nullable=False, default="ACTIVE")
    # the workflow every message goes to while it is open (e.g. "core_cert"), its record and state
    active_workflow = Column(String(40), nullable=True)
    workflow_ref = Column(String(512), nullable=True)
    workflow_state = Column(JSON, nullable=True)
    # the brain tier this conversation last ran on (full / large_only / small_only / rules)
    brain_status = Column(String(20), nullable=True)
    last_read_message_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("uq_flash_conv_active", "user_id", unique=True, postgresql_where=text("status = 'ACTIVE'")),
    )


class FlashMessage(Base):
    __tablename__ = "flash_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(36), ForeignKey("flash_conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum(*MESSAGE_ROLES, name="flash_message_role", native_enum=False, create_constraint=True),
                  nullable=False)
    body = Column(Text, nullable=False)
    # {"tool", "args", "mission_id", "decision": {"kind", "ref"}, "intent", ...}
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_flash_messages_conversation_id_id", "conversation_id", "id"),)
