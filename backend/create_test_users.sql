-- ============================================================
-- TEST DATA SETUP SCRIPT FOR BU SCOPING TESTS
-- ============================================================

-- Note: Adjust these queries based on your actual schema
-- This script creates all test users needed for BU scoping tests

-- 1. BUSINESS UNITS (if they don't exist)
INSERT INTO business_units (id, name, bu_code, description, tenant_id, created_at)
VALUES
('bu-001', 'North America', 'NA', 'North America Business Unit', 1, NOW()),
('bu-002', 'Europe', 'EU', 'Europe Business Unit', 1, NOW())
ON CONFLICT DO NOTHING;

-- 2. LOCATIONS (if they don't exist)
INSERT INTO locations (id, name, city, country, state, tenant_id, created_at)
VALUES
('loc-001', 'New York', 'New York', 'USA', 'NY', 1, NOW()),
('loc-002', 'London', 'London', 'UK', 'England', 1, NOW())
ON CONFLICT DO NOTHING;

-- 3. BU HEADS
INSERT INTO users (email, password, full_name, role, business_unit_id, tenant_id, created_at)
VALUES
('buhead.na@blitzenx.com', '$2b$12$...', 'Alice North America', 'bu_head', 'bu-001', 1, NOW()),
('buhead.eu@blitzenx.com', '$2b$12$...', 'Bob Europe', 'bu_head', 'bu-002', 1, NOW())
ON CONFLICT (email) DO NOTHING;

-- 4. RECRUITERS BU 1
INSERT INTO users (email, password, full_name, role, business_unit_id, tenant_id, created_at)
VALUES
('recruiter.na.1@blitzenx.com', '$2b$12$...', 'Charlie NA Recruiter 1', 'recruiter', 'bu-001', 1, NOW()),
('recruiter.na.2@blitzenx.com', '$2b$12$...', 'Diana NA Recruiter 2', 'recruiter', 'bu-001', 1, NOW())
ON CONFLICT (email) DO NOTHING;

-- 5. RECRUITERS BU 2
INSERT INTO users (email, password, full_name, role, business_unit_id, tenant_id, created_at)
VALUES
('recruiter.eu.1@blitzenx.com', '$2b$12$...', 'Eve EU Recruiter 1', 'recruiter', 'bu-002', 1, NOW()),
('recruiter.eu.2@blitzenx.com', '$2b$12$...', 'Frank EU Recruiter 2', 'recruiter', 'bu-002', 1, NOW())
ON CONFLICT (email) DO NOTHING;

-- 6. HR MANAGERS BU 1
INSERT INTO users (email, password, full_name, role, business_unit_id, tenant_id, created_at)
VALUES
('hr.na.1@blitzenx.com', '$2b$12$...', 'Grace NA HR Manager', 'hr_manager', 'bu-001', 1, NOW())
ON CONFLICT (email) DO NOTHING;

-- 7. HR MANAGERS BU 2
INSERT INTO users (email, password, full_name, role, business_unit_id, tenant_id, created_at)
VALUES
('hr.eu.1@blitzenx.com', '$2b$12$...', 'Henry EU HR Manager', 'hr_manager', 'bu-002', 1, NOW())
ON CONFLICT (email) DO NOTHING;

-- 8. HIRING MANAGERS BU 1
INSERT INTO users (email, password, full_name, role, business_unit_id, tenant_id, created_at)
VALUES
('hm.na.1@blitzenx.com', '$2b$12$...', 'Iris NA Hiring Manager', 'hiring_manager', 'bu-001', 1, NOW())
ON CONFLICT (email) DO NOTHING;

-- 9. HIRING MANAGERS BU 2
INSERT INTO users (email, password, full_name, role, business_unit_id, tenant_id, created_at)
VALUES
('hm.eu.1@blitzenx.com', '$2b$12$...', 'Jack EU Hiring Manager', 'hiring_manager', 'bu-002', 1, NOW())
ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- PASSWORD HASHING INSTRUCTION
-- ============================================================
--
-- If using bcrypt, generate hashes for:
-- - RecruiterNA1@123
-- - RecruiterNA2@123
-- - RecruiterEU1@123
-- - RecruiterEU2@123
-- - BUHeadNA@123
-- - BUHeadEU@123
-- - HRNA1@123
-- - HREU1@123
-- - HMNA1@123
-- - HMEU1@123
--
-- And replace $2b$12$... with the actual bcrypt hashes
--
-- You can use this Python to generate hashes:
-- python3 -c "import bcrypt; print(bcrypt.hashpw(b'RecruiterNA1@123', bcrypt.gensalt()).decode())"
-- ============================================================
