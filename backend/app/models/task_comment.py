"""Comments on a task (CEO 2026-10-22): a thread anyone who can see the task may read and add to --
its assignee, its creator, and whoever the task view lets see it. Approval decisions post their
note here too, so the reason travels with the task."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base


class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True, index=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
