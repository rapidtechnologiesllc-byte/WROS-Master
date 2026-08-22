# Phase 1 PostgreSQL Migration Action Plan (2026-08-14)

**Critical Requirement:** Phase 1 must be 100% complete with PostgreSQL BEFORE Phase 2 can proceed

**Status:** 🔴 BLOCKED - PostgreSQL not yet installed locally

**Timeline:** 
- Setup: 30 minutes (PostgreSQL installation)
- Migration: 5 minutes (Alembic migrations)
- Verification: 10 minutes (seed data + API tests)
- **Total: 45 minutes**

---

## EXECUTIVE SUMMARY

The project has moved from SQLite to PostgreSQL. Phase 1 (Security Foundation) code is already written and committed, but needs to be applied to PostgreSQL via Alembic migrations.

**What's needed:**
1. ✅ Code: All Phase 1 files exist (RBAC, permissions, auth middleware)
2. ✅ Migrations: Alembic migration files exist in `alembic/versions/`
3. ✅ Configuration: database.py updated for PostgreSQL support
4. ✅ .env.local: Created with PostgreSQL connection string
5. ❌ **ACTION NEEDED:** Install PostgreSQL locally
6. ❌ **ACTION NEEDED:** Run Alembic migrations
7. ❌ **ACTION NEEDED:** Verify Phase 1 working

---

## PHASE 1 SECURITY FOUNDATION REQUIREMENTS

These 5 requirements must all be met for Phase 1 to be 100% complete:

1. **Multi-Tenancy (tenant_id on all tables):**
   - Every table has `tenant_id NOT NULL, indexed`
   - Middleware scopes queries by tenant
   - Data isolation enforced at DB level

2. **RBAC (8 roles, 17 permissions):**
   - roles table with 7 roles (Super User, Admin, Recruiter, HR Manager, Finance, Partner, BU Head)
   - permissions table with 17 core permissions
   - user_roles junction table (users can have multiple roles)
   - role_permissions junction table (roles → permissions)

3. **Business Unit Isolation:**
   - business_units table with 3 default BUs (NA, EU, APAC)
   - BU-level data filtering in middleware
   - Users scoped to BU except Super User

4. **Audit Logging:**
   - audit_logs table with compliance fields
   - All data changes logged (CREATE, READ, UPDATE, DELETE)
   - Immutable audit trail

5. **PII Masking:**
   - Sensitive fields masked for non-admin users
   - Email, phone, SSN, address masked
   - Admin/HR can see unmasked data

---

## QUICK START

```bash
# 1. Install PostgreSQL 15 from https://www.postgresql.org/download/windows/
# 2. Create database: psql -U postgres -h localhost -c "CREATE DATABASE wros_dev;"
# 3. From backend directory:
cd C:\Users\AvinashMukund\Documents\Claude\OnboardingModule-Backend
# 4. Run migrations
alembic upgrade head
# 5. Initialize seed data
python init_wros_db.py
# 6. Start backend
python -m uvicorn app.main:app --reload
# 7. Verify: curl http://localhost:8080/health
```

**See:** `POSTGRESQL_SETUP_WINDOWS.md` for detailed steps

---

## VERIFICATION CHECKLIST

After completing setup:

- [ ] PostgreSQL installed and running (`psql --version`)
- [ ] Database created (`psql -U postgres -d wros_dev -h localhost`)
- [ ] Alembic migrations applied (`alembic current` shows latest)
- [ ] Seed data initialized (`python init_wros_db.py` completes)
- [ ] Backend starts (`python -m uvicorn app.main:app --reload`)
- [ ] Health check works (`curl http://localhost:8080/health`)
- [ ] RBAC endpoints respond (`curl http://localhost:8080/api/v1/rbac/roles`)
- [ ] 7 roles visible in database
- [ ] 17 permissions visible in database
- [ ] 3 business units visible in database
- [ ] All Phase 1 requirements met

---

## FILES READY FOR USE

**Configuration:**
- ✅ `.env.local` - PostgreSQL connection (DATABASE_URL=postgresql://...)
- ✅ `app/core/database.py` - Updated with PostgreSQL support
- ✅ `requirements.txt` - Already includes psycopg2-binary

**Alembic Migrations (in `alembic/versions/`):**
- ✅ `51a6401ffa5e_add_rbac_tables_and_users_role_id.py` - RBAC tables
- ✅ `a8f9b0c1d2e3_expand_rbac_permissions.py` - Permissions tables
- ✅ `f7c9d1e3a5b7_add_comprehensive_permission_system.py` - Business units + audit
- ✅ `2026_08_12_expand_permissions.py` - Final permission setup

**Seed Data:**
- ✅ `init_wros_db.py` - Initialize 7 roles, 17 permissions, 3 BUs

**Documentation:**
- ✅ `POSTGRESQL_SETUP_WINDOWS.md` - Detailed setup guide
- 📄 This file - Action plan and checklist

---

## WHAT'S IN PHASE 1

Phase 1 is a comprehensive security foundation that MUST be complete before any Phase 2 work:

**Users & Authentication:**
- User registration/login (bcrypt hashing)
- JWT token generation/validation
- Email-based authentication

**Role-Based Access Control (RBAC):**
- 7 predefined roles with 17 permissions
- Users can have multiple roles (e.g., Partner + BU Head + Hiring Manager)
- Role composition: permissions from all roles UNION'd

**Multi-Tenancy:**
- All data scoped by tenant_id
- Business unit filtering for non-super-users
- Complete data isolation at DB level

**Audit Logging:**
- All data changes logged (who, what, when, why)
- Compliance trail for finance/HR
- Immutable audit records

**Permission-Based Access:**
- Fine-grained permissions (candidate.create, interview.manage, etc.)
- Permission-based middleware on all endpoints
- Dynamic navigation based on user's permissions

**Data Masking:**
- PII (Email, Phone, SSN, Address) masked for non-admins
- Configurable per-permission (admin.see_pii)
- Prevents data leakage in screenshots/reports

---

## NEXT STEPS AFTER PHASE 1

Once Phase 1 is 100% verified with PostgreSQL:

### Backend (Phase 2):
1. Create 42 data models (candidates, employees, jobs, interviews, etc.)
2. Implement 10 hard rules (R-01 to R-10)
3. Build REST API endpoints
4. Add service layer (business logic)
5. Create integration tests

### Frontend (Phase 2):
1. Build recruiter screens (candidate, job, interview)
2. Build HR screens (employee, allocation)
3. Build admin dashboard
4. Integrate RBAC into navigation
5. Add form validation and error handling

### Phase 3:
1. Thunder autonomous recruitment loop
2. AI Recruiter agent (OpenAI integration)
3. Multi-stage interview scheduling
4. Offer generation and e-signature
5. Onboarding workflow

---

## TIMELINE ESTIMATE

**Today (2026-08-14):**
- 30 min: PostgreSQL installation
- 5 min: Database creation
- 5 min: Alembic migrations
- 3 min: Seed data
- 10 min: Backend verification
- 10 min: Phase 1 requirements check
- **Total: ~1 hour**

**Result: Phase 1 = 100% complete with PostgreSQL ✅**

**Then:**
- Phase 2: 2-3 weeks (19h backend, 48h frontend, 15h testing)
- Phase 3: 4-6 weeks (Thunder loop, AI agent, interviews, offers)
- Go-live: 4.5 months total timeline maintained

---

## SUPPORT

**If stuck at any step:**

1. Refer to `POSTGRESQL_SETUP_WINDOWS.md` for detailed instructions
2. Check "COMMON ISSUES & FIXES" section at end of setup guide
3. Verify PostgreSQL running: `psql --version`
4. Test connection: `psql -U postgres -d wros_dev -h localhost`
5. Check .env.local has correct DATABASE_URL

---

## READY TO BEGIN?

**Next Step:** 
1. Download PostgreSQL 15 from https://www.postgresql.org/download/windows/
2. Follow `POSTGRESQL_SETUP_WINDOWS.md` for installation
3. Return here after "Step 8: Verify Phase 1 Setup" is complete

**Estimated time to Phase 1 completion: 1 hour**

**Then Phase 2 can begin immediately with 42-table data model + hard rules enforcement**
