"""Permission system models for comprehensive RBAC implementation"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey, func, Index, UniqueConstraint
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


class DetailedPermission(Base):
    """Granular permissions: module, field, scope, action, dashboard (detailed permission system, 2026-08-13)"""
    __tablename__ = "detailed_permissions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String(100), nullable=False)  # e.g., "candidate.view", "invoice.approve"
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)  # "candidate", "employee", "financial", "admin"
    layer = Column(String(50), nullable=True)  # "module", "field", "scope", "action", "dashboard"
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    role_permissions = relationship("DetailedRolePermission", back_populates="permission", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_permission_name_per_tenant"),
        Index("ix_permissions_tenant_id", "tenant_id"),
        Index("ix_permissions_category", "category"),
        Index("ix_permissions_layer", "layer"),
    )


class DetailedRolePermission(Base):
    """Junction table: maps roles to detailed permissions (2026-08-13)"""
    __tablename__ = "detailed_role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("role_templates.id"), nullable=False)
    permission_id = Column(Integer, ForeignKey("detailed_permissions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    role = relationship("RoleTemplate", foreign_keys=[role_id])
    permission = relationship("DetailedPermission", back_populates="role_permissions")

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
        Index("ix_detailed_role_permissions_role_id", "role_id"),
        Index("ix_detailed_role_permissions_permission_id", "permission_id"),
    )


class FieldPermission(Base):
    """Field-level access control: determines if field is hidden, masked, readonly, or editable per role"""
    __tablename__ = "field_permissions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("role_templates.id"), nullable=False)
    table_name = Column(String(100), nullable=False)  # "employees", "candidates", "invoices"
    field_name = Column(String(100), nullable=False)  # "salary", "ssn", "bank_account"
    access_level = Column(String(20), nullable=False)  # "hidden", "masked", "readonly", "editable"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("role_id", "table_name", "field_name", name="uq_field_permission"),
        Index("ix_field_permissions_tenant_id", "tenant_id"),
        Index("ix_field_permissions_role_id", "role_id"),
        Index("ix_field_permissions_table", "table_name"),
    )


class DataScopePermission(Base):
    """Data scope access control: BU, multi-BU, team, own, org-wide per role per module"""
    __tablename__ = "data_scope_permissions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("role_templates.id"), nullable=False)
    module = Column(String(100), nullable=False)  # "candidates", "employees", "invoices"
    scope_type = Column(String(50), nullable=False)  # "ORG_WIDE", "MULTI_BU", "BU_ONLY", "TEAM_ONLY", "OWN_ONLY", "CUSTOM"
    filter_rule = Column(Text, nullable=True)  # JSON filter rule for custom scoping
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("role_id", "module", name="uq_data_scope_per_role_module"),
        Index("ix_data_scope_tenant_id", "tenant_id"),
        Index("ix_data_scope_role_id", "role_id"),
        Index("ix_data_scope_module", "module"),
    )
