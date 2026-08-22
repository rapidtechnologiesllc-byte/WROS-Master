"""Permission system models - Job Title management.
The main RBAC system uses role_template.py (RoleTemplate, Resource, RoleTemplatePermission).
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base


class JobTitle(Base):
    """Admin-managed job titles (e.g., Manager, Senior Manager, Recruiter)"""
    __tablename__ = "job_titles"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    roles = relationship("JobTitleRole", back_populates="job_title", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_job_title_name_per_tenant"),
        Index("ix_job_titles_tenant_id", "tenant_id"),
    )


class JobTitleRole(Base):
    """Junction table: maps job titles to roles"""
    __tablename__ = "job_title_roles"

    id = Column(Integer, primary_key=True, index=True)
    job_title_id = Column(Integer, ForeignKey("job_titles.id"), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("role_templates.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    job_title = relationship("JobTitle", back_populates="roles")
    role = relationship("RoleTemplate", foreign_keys=[role_id])

    __table_args__ = (
        UniqueConstraint("job_title_id", "role_id", name="uq_job_title_role"),
        Index("ix_job_title_roles_job_id", "job_title_id"),
        Index("ix_job_title_roles_role_id", "role_id"),
    )
