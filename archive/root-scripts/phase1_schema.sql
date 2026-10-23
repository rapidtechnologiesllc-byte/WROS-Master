-- Phase 1 Security Foundation Schema
-- Minimal tables for RBAC, multi-tenancy, audit logging

-- Tenants (multi-tenancy root)
CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Business Units
CREATE TABLE IF NOT EXISTS business_units (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    name VARCHAR(100) NOT NULL,
    code VARCHAR(10) NOT NULL,
    manager_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, code)
);

-- Roles
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Permissions
CREATE TABLE IF NOT EXISTS permissions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    module VARCHAR(50),
    action VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Role-Permission mappings
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY(role_id, permission_id)
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    UserID VARCHAR(50) PRIMARY KEY,
    UserEmail VARCHAR(100) NOT NULL UNIQUE,
    UserPassword VARCHAR(500) NOT NULL,
    UserRole VARCHAR(50),
    role_id INTEGER REFERENCES roles(id),
    tenant_id INTEGER DEFAULT 1 REFERENCES tenants(id),
    business_unit_id INTEGER REFERENCES business_units(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- User-Role mappings (many-to-many)
CREATE TABLE IF NOT EXISTS user_roles (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL REFERENCES users(UserID) ON DELETE CASCADE,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    business_unit_id INTEGER REFERENCES business_units(id),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, role_id, business_unit_id)
);

-- Business Unit Access tracking
CREATE TABLE IF NOT EXISTS business_unit_access (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL REFERENCES users(UserID) ON DELETE CASCADE,
    business_unit_id INTEGER NOT NULL REFERENCES business_units(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, business_unit_id)
);

-- Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    user_id VARCHAR(50),
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(100),
    changes JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_bu ON users(business_unit_id);

-- Seed Data --

-- Create default tenant
INSERT INTO tenants(name) VALUES('Default') ON CONFLICT DO NOTHING;

-- Create 7 default roles
INSERT INTO roles(name, description) VALUES
    ('Super User', 'Full system access'),
    ('Admin', 'Administrative access'),
    ('Recruiter', 'Recruiter role'),
    ('HR Manager', 'HR Manager role'),
    ('Finance', 'Finance role'),
    ('Partner', 'Partner role'),
    ('BU Head', 'Business Unit Head role')
ON CONFLICT (name) DO NOTHING;

-- Create 17 default permissions
INSERT INTO permissions(name, module, action) VALUES
    ('candidate.view', 'candidates', 'view'),
    ('candidate.create', 'candidates', 'create'),
    ('candidate.edit', 'candidates', 'edit'),
    ('candidate.delete', 'candidates', 'delete'),
    ('interview.manage', 'interviews', 'manage'),
    ('employee.view', 'employees', 'view'),
    ('employee.manage', 'employees', 'manage'),
    ('recruitment.view', 'recruitment', 'view'),
    ('reports.view', 'reports', 'view'),
    ('user.manage', 'users', 'manage'),
    ('role.manage', 'roles', 'manage'),
    ('business_unit.manage', 'business_units', 'manage'),
    ('invoices.view', 'invoices', 'view'),
    ('invoices.manage', 'invoices', 'manage'),
    ('reports.financial', 'reports', 'financial'),
    ('team.view', 'team', 'view'),
    ('business_unit.view', 'business_units', 'view')
ON CONFLICT (name) DO NOTHING;

-- Create 3 default business units
INSERT INTO business_units(tenant_id, name, code)
SELECT 1, name, code FROM (
    VALUES ('North America', 'NA'), ('Europe', 'EU'), ('Asia Pacific', 'APAC')
) AS t(name, code)
WHERE NOT EXISTS (SELECT 1 FROM business_units WHERE tenant_id = 1 AND code = t.code)
ON CONFLICT (tenant_id, code) DO NOTHING;
