from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
import logging
from sqlalchemy.sql import func

from app.models.base import Base

logger = logging.getLogger(__name__)

class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(512), unique=True, index=True, nullable=False)
    name = Column(String(512), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<NewsletterSubscriber id={self.id} email={self.email} active={self.is_active}>"

class Newsletter(Base):
    __tablename__ = "newsletters"

    id = Column(String(512), primary_key=True, index=True)
    subject = Column(String(512), nullable=False)
    content = Column(Text, nullable=False)          # HTML or plain text
    status = Column(String(512), default="draft", nullable=False)  # draft | scheduled | sent | failed
    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=False)
    scheduled_for = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Newsletter id={self.id} subject={self.subject!r} status={self.status}>"
