import logging
"""System Module and Module Permission models for database-driven permission system."""

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base

logger = logging.getLogger(__name__)

class SystemModule(Base):
    """Represents a system module (Candidates, Jobs, Interviews, etc.)

    This is the database-driven configuration for application modules.
    Each module has verbs (actions) that users can perform.
    Separate from role_template.Module which is for RBAC resource definitions.
    """
    __tablename__ = "system_modules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(512), unique=True, nullable=False, index=True)
    display_name = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(512), nullable=False)  # Recruitment, Sales, Delivery, Finance, Admin
    is_active = Column(Boolean, default=True)
    tenant_id = Column(Integer, nullable=False, default = True)

    # Relationships
    permissions = relationship("SystemModulePermission", back_populates="module", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SystemModule(id={self.id}, name='{self.name}', category='{self.category}')>"

class SystemModulePermission(Base):
    """Represents a verb (action) available for a module: candidates.view, jobs.create, etc.

    Each SystemModulePermission defines an action (verb) that can be performed on a module.
    Used to compose granular permissions for role-based access control.
    """
    __tablename__ = "system_module_permissions"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("system_modules.id"), nullable=False, index=True)
    verb = Column(String(512), nullable=False)  # view, create, edit, delete, merge, approve, manage, etc.
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    tenant_id = Column(Integer, nullable=False, default = True)

    # Relationships
    module = relationship("SystemModule", back_populates="permissions")

    # Unique constraint: each verb only once per module
    __table_args__ = (UniqueConstraint('module_id', 'verb', name='_system_module_verb_uc'),)

    @property
    def permission_name(self):
        """Generate permission name: 'candidates.view', 'jobs.create'"""
        return f"{self.module.name}.{self.verb}"

    def __repr__(self):
        return f"<SystemModulePermission(module='{self.module.name}', verb='{self.verb}')>"

# For backwards compatibility, export with simpler names
Module = SystemModule
ModulePermission = SystemModulePermission
