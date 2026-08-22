# PostgreSQL Setup - Quick Checklist (2026-08-14)

**Total Time:** 1 hour  
**Goal:** Get Phase 1 working on PostgreSQL

---

## ✅ SETUP CHECKLIST

### Step 1: Install PostgreSQL (30 minutes)
- [ ] Download PostgreSQL 15 from: https://www.postgresql.org/download/windows/
- [ ] Run installer, accept defaults
- [ ] Superuser password: `postgres`
- [ ] Port: 5432
- [ ] Verify: `psql --version` (should show PostgreSQL 15.x)

### Step 2: Create Database (2 minutes)
```bash
psql -U postgres -h localhost -c "CREATE DATABASE wros_dev;"
```
- [ ] Command executed successfully
- [ ] Verify: `psql -U postgres -d wros_dev -h localhost` (should connect)

### Step 3: Navigate to Backend (1 minute)
```bash
cd C:\Users\AvinashMukund\Documents\Claude\OnboardingModule-Backend
```

### Step 4: Run Alembic Migrations (5 minutes)
```bash
alembic upgrade head
```
- [ ] All migrations applied successfully
- [ ] Verify: `alembic current` (should show latest migration)

### Step 5: Initialize Seed Data (3 minutes)
```bash
python init_wros_db.py
```
- [ ] All roles, permissions, BUs created
- [ ] Output shows: ✓ Tenant, ✓ Business Units, ✓ Roles, ✓ Permissions

### Step 6: Start Backend (1 minute)
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```
- [ ] Backend starts without errors
- [ ] Shows: "Uvicorn running on http://0.0.0.0:8080"

### Step 7: Verify in New Terminal (5 minutes)
```bash
# Health check
curl http://localhost:8080/health
# Should return: {"status":"ok"}

# List roles (should show 7)
curl http://localhost:8080/api/v1/rbac/roles

# List permissions (should show 17)
curl http://localhost:8080/api/v1/rbac/permissions

# List business units (should show 3)
curl http://localhost:8080/api/v1/business-units
```

- [ ] Health check returns ok
- [ ] 7 roles visible
- [ ] 17 permissions visible  
- [ ] 3 business units visible (NA, EU, APAC)

### Step 8: Verify Phase 1 Complete (5 minutes)
```bash
# Connect to database
psql -U postgres -d wros_dev -h localhost

# Check tables exist
\dt
# Should show: users, roles, permissions, user_roles, business_units, business_unit_access, audit_logs, etc.

# Count roles
SELECT COUNT(*) FROM roles;
# Should return: 7

# Count permissions
SELECT COUNT(*) FROM permissions;
# Should return: 17

# Count business units
SELECT COUNT(*) FROM business_units;
# Should return: 3

# Exit
\q
```

- [ ] All Phase 1 tables exist
- [ ] 7 roles in database
- [ ] 17 permissions in database
- [ ] 3 business units in database

---

## ❌ TROUBLESHOOTING

### PostgreSQL Command Not Found
```bash
# Add to PATH:
$env:Path += ";C:\Program Files\PostgreSQL\15\bin"
# Then: psql --version
```
- [ ] Fixed

### Failed to Connect to Database
```bash
# Start PostgreSQL service
net start postgresql-x64-15
# Or via Services.msc → postgresql-x64-15 → Start
```
- [ ] PostgreSQL running

### Alembic Migration Failed
```bash
# Check connection string in .env.local
cat .env.local | grep DATABASE_URL
# Should show: postgresql://postgres:postgres@localhost:5432/wros_dev

# Verify database exists
psql -U postgres -h localhost -c "\l"
# Should show: wros_dev in list

# Try again
alembic upgrade head
```
- [ ] Fixed

### Backend Fails to Start
```bash
# Check logs in terminal
# Look for: "Connection refused" or "Database not found"

# Verify PostgreSQL connection
psql -U postgres -d wros_dev -h localhost

# Check .env.local is in backend directory
ls -la .env.local

# Try again
python -m uvicorn app.main:app --reload
```
- [ ] Fixed

---

## 📋 PHASE 1 REQUIREMENTS VERIFICATION

After all steps above pass, verify these 5 Phase 1 requirements:

### 1. Multi-Tenancy ✅
```bash
psql -U postgres -d wros_dev -h localhost
SELECT COUNT(*) as table_count FROM information_schema.columns 
WHERE column_name = 'tenant_id' AND table_schema = 'public';
# Should return: 20+
\q
```
- [ ] 20+ tables have tenant_id

### 2. RBAC (7 Roles, 17 Permissions) ✅
```bash
curl http://localhost:8080/api/v1/rbac/roles | grep -c '"id"'
# Should return: 7

curl http://localhost:8080/api/v1/rbac/permissions | grep -c '"id"'
# Should return: 17
```
- [ ] 7 roles exist
- [ ] 17 permissions exist

### 3. Business Units ✅
```bash
curl http://localhost:8080/api/v1/business-units | grep -c '"id"'
# Should return: 3 (NA, EU, APAC)
```
- [ ] 3 business units created

### 4. Audit Logging ✅
```bash
psql -U postgres -d wros_dev -h localhost
\d audit_logs
# Should show table with: id, tenant_id, user_id, action, resource_type, created_at, etc.
\q
```
- [ ] audit_logs table exists with all fields

### 5. PII Masking ✅
```bash
# Can test after creating test candidates in Phase 2
# For now: Verify middleware exists
cat app/middleware/pii_masking_middleware.py | head -20
# Should show PII masking code
```
- [ ] Middleware file exists

---

## ✅ COMPLETION CHECKLIST

**When all checkboxes above are checked:**

- [ ] PostgreSQL installed and running
- [ ] Database created (wros_dev)
- [ ] Alembic migrations applied (Phase 1 schema)
- [ ] Seed data initialized (roles, permissions, BUs)
- [ ] Backend starts without errors
- [ ] All API endpoints respond correctly
- [ ] 7 roles visible
- [ ] 17 permissions visible
- [ ] 3 business units visible
- [ ] All Phase 1 tables exist in database
- [ ] All 5 Phase 1 requirements verified

**Result: Phase 1 = 100% COMPLETE WITH POSTGRESQL ✅**

---

## 🎯 NEXT STEP

Once this checklist is 100% complete:

**Phase 2 can begin immediately:**
- Data models (42 tables)
- Hard rules (R-01 to R-10)
- API endpoints
- Frontend screens
- Integration tests

**Timeline:** 2-3 weeks (82 hours total)

---

## 📞 SUPPORT

**If stuck at any step:**
1. Check error message carefully
2. See "TROUBLESHOOTING" section above
3. Refer to detailed guides:
   - `POSTGRESQL_SETUP_WINDOWS.md` (full setup guide)
   - `PHASE_1_POSTGRESQL_ACTION_PLAN.md` (detailed action plan)
4. Contact support with error message

---

**Estimated Total Time: 1 hour**

**Current Time: 2026-08-14 [Your Time]**

**Expected Completion: 2026-08-14 [Your Time + 1 hour]**

**Status:** Ready to begin - proceed with Step 1
