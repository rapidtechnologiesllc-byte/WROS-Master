import logging
"""Role Template system - Dynamic roles defined via modules and resources."""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

logger = logging.getLogger(__name__)

class Module(Base):
    """Top-level modules (Recruitment, Finance, Admin, Executive, etc.)"""
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True)
    name = Column(String(512), nullable=False)  # e.g., "Recruitment"
    display_name = Column(String(150), nullable=False)  # e.g., "Recruitment Management"
    description = Column(Text)
    enabled = Column(Boolean, default=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Composite unique constraint: (name, tenant_id) - allows same module name in different tenants
    __table_args__ = (UniqueConstraint('name', 'tenant_id', name='uq_module_name_tenant'),)

    # Relationships
    resources = relationship("Resource", back_populates="module", cascade="all, delete-orphan")

class Resource(Base):
    """Resources/Features under each module (Candidates, Jobs, Invoices, etc.)"""
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=False)
    name = Column(String(512), nullable=False)  # e.g., "candidates"
    display_name = Column(String(150), nullable=False)  # e.g., "Candidates"
    route_path = Column(String(200))  # e.g., "/candidates", "/admin/users-access-control"
    description = Column(Text)
    enabled = Column(Boolean, default=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    module = relationship("Module", back_populates="resources")
    role_permissions = relationship("RoleTemplatePermission", back_populates="resource", cascade="all, delete-orphan")

class RoleTemplate(Base):
    """Predefined or custom role templates (Recruiter, HR Manager, Admin, CEO, etc.)"""
    __tablename__ = "role_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String(512), nullable=False)  # e.g., "Recruiter", "HR Manager"
    display_name = Column(String(150), nullable=False)
    description = Column(Text)

    # Hierarchy: 17 levels (1=Intern → 17=CEO)
    hierarchy_level = Column(Integer, nullable=False, default=5)  # 1-17: defines authority level
    # Specialization: what they do day-to-day (Recruitment, Development, HR, Finance, PM, QA, etc.)
    specialization = Column(String(512), nullable=False, default="General")  # Defines expertise domain

    is_system = Column(Boolean, default=False)  # True for built-in roles, False for custom
    # PRODUCTION SAFETY: enabled MUST default to True, never allow None
    enabled = Column(Boolean, default=True, nullable=False, server_default="true")
    # PRODUCTION SAFETY: tenant_id MUST be set, never allow None. Default to 1 (single tenant)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, server_default="1", default=1)
    created_by = Column(String(255))  # user email who created it
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    permissions = relationship("RoleTemplatePermission", back_populates="role_template", cascade="all, delete-orphan")

class RoleTemplatePermission(Base):
    """Permissions matrix: Role Template × Resource × Actions (View/Create/Edit/Delete)"""
    __tablename__ = "role_template_permissions"

    id = Column(Integer, primary_key=True)
    role_template_id = Column(Integer, ForeignKey("role_templates.id"), nullable=False)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False)
    can_view = Column(Boolean, default=False)
    can_create = Column(Boolean, default=False)
    can_edit = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    role_template = relationship("RoleTemplate", back_populates="permissions")
    resource = relationship("Resource", back_populates="role_permissions")
