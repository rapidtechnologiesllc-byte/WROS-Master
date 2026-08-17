"""
Checklist Models — Templates and Candidate-specific checklists.

Two item types:
  - 'todo'  : Standard task the candidate completes whenever ready.
  - 'queue' : Ordered task; only the current active queue item is unlocked.
              Completing it automatically activates the next queue item.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Date, Boolean,
    ForeignKey, func
)
from sqlalchemy.orm import relationship

from app.models.base import Base


class ChecklistTemplate(Base):
    """A reusable checklist blueprint created by a Hiring Manager."""
    __tablename__ = "checklist_templates"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_by_user_id = Column(String(50), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    # Relationships
    items = relationship(
        "ChecklistTemplateItem",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="ChecklistTemplateItem.order_index"
    )
    created_by = relationship("Users", foreign_keys=[created_by_user_id])

    def __repr__(self) -> str:
        return f"<ChecklistTemplate id={self.id} name={self.name!r}>"


class ChecklistTemplateItem(Base):
    """One item definition inside a ChecklistTemplate."""
    __tablename__ = "checklist_template_items"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    template_id = Column(
        Integer,
        ForeignKey("checklist_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    item_type = Column(String(10), nullable=False, default="todo")   # 'todo' | 'queue'
    order_index = Column(Integer, nullable=False, default=0)
    due_days_offset = Column(Integer, nullable=True)  # days after assignment
    created_at = Column(DateTime(timezone=False), server_default=func.now())

    # Relationships
    template = relationship("ChecklistTemplate", back_populates="items")

    def __repr__(self) -> str:
        return f"<ChecklistTemplateItem id={self.id} type={self.item_type!r} title={self.title!r}>"


class CandidateChecklist(Base):
    """
    A specific checklist instance assigned to a candidate.
    Created by copying a ChecklistTemplate.
    """
    __tablename__ = "candidate_checklists"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    candidate_id = Column(String(36),
        ForeignKey("candidates.candidateID", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    template_id = Column(
        Integer,
        ForeignKey("checklist_templates.id", ondelete="SET NULL"),
        nullable=True
    )
    template_name = Column(String(255), nullable=True)   # snapshot of name at assignment time
    assigned_by_user_id = Column(String(50), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    assigned_at = Column(DateTime(timezone=False), server_default=func.now())
    status = Column(String(20), nullable=False, default="active")  # 'active' | 'completed'
    completed_at = Column(DateTime(timezone=False), nullable=True)

    # Relationships
    items = relationship(
        "CandidateChecklistItem",
        back_populates="checklist",
        cascade="all, delete-orphan",
        order_by="CandidateChecklistItem.order_index"
    )
    candidate = relationship("Candidate", foreign_keys=[candidate_id])
    assigned_by = relationship("Users", foreign_keys=[assigned_by_user_id])

    def __repr__(self) -> str:
        return f"<CandidateChecklist id={self.id} candidate={self.candidate_id} status={self.status!r}>"


class CandidateChecklistItem(Base):
    """
    One runtime checklist item belonging to a CandidateChecklist.
    Copied from a ChecklistTemplateItem at assignment time.
    """
    __tablename__ = "candidate_checklist_items"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    checklist_id = Column(
        Integer,
        ForeignKey("candidate_checklists.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    template_item_id = Column(
        Integer,
        ForeignKey("checklist_template_items.id", ondelete="SET NULL"),
        nullable=True
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    item_type = Column(String(10), nullable=False, default="todo")   # 'todo' | 'queue'
    order_index = Column(Integer, nullable=False, default=0)

    # Status lifecycle:
    #   todo  items:  'pending' → 'submitted' (candidate) → 'completed' (HR)
    #   queue items:  'pending' → 'active' → 'submitted' (candidate) → 'completed' (HR)
    status = Column(String(20), nullable=False, default="pending")

    due_date = Column(DateTime(timezone=False), nullable=True)
    activated_at = Column(DateTime(timezone=False), nullable=True)
    submitted_at = Column(DateTime(timezone=False), nullable=True)   # candidate marks done
    completed_at = Column(DateTime(timezone=False), nullable=True)   # HR verifies & completes

    # Relationships
    checklist = relationship("CandidateChecklist", back_populates="items")

    def __repr__(self) -> str:
        return (
            f"<CandidateChecklistItem id={self.id} "
            f"type={self.item_type!r} status={self.status!r} title={self.title!r}>"
        )
