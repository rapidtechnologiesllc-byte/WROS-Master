# PostgreSQL Setup for Windows Development (2026-08-14)

**Status:** PostgreSQL migration ready for local development setup  
**Timeline:** 15-30 minutes setup + 5 minutes Alembic migration  
**OS:** Windows 11 Pro  

---

## Step 1: Download and Install PostgreSQL

### Option A: PostgreSQL Standalone Installer (Recommended for Windows)

1. **Download PostgreSQL 15 (latest LTS):**
   - Go to: https://www.postgresql.org/download/windows/
   - Download: PostgreSQL 15 Windows Installer
   - File: `postgresql-15.x-x64.exe`

2. **Run the Installer:**
   - Double-click the .exe file
   - Accept license agreement
   - Select installation directory (default is fine): `C:\Program Files\PostgreSQL\15`
   - Select components (defaults are fine):
     - PostgreSQL Server ✓
     - pgAdmin 4 ✓
     - Stack Builder ✓
   - Choose data directory (default: `C:\Program Files\PostgreSQL\15\data`)
   - Set superuser password: **`postgres`** (or your preferred password)
   - Port: **`5432`** (default)
   - Locale: **English, United States**
   - Click "Next" and "Finish"

3. **Post-Installation:**
   - PostgreSQL service will start automatically
   - Add PostgreSQL bin directory to PATH:
     - Control Panel → System → Environment Variables
     - Add to PATH: `C:\Program Files\PostgreSQL\15\bin`

### Option B: Docker (If you install Docker Desktop later)

```bash
docker run -d \
  --name postgres_wros \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=wros_dev \
  -p 5432:5432 \
  postgres:15-alpine
```

---

## Step 2: Verify PostgreSQL Installation

```bash
# Open PowerShell and test connection
psql --version
# Should output: psql (PostgreSQL) 15.x

# Connect to PostgreSQL
psql -U postgres -h localhost
# Should show: postgres=#
```

If `psql` command not found:
- Restart PowerShell/terminal
- Or add `C:\Program Files\PostgreSQL\15\bin` to your PATH manually

---

## Step 3: Create Database and User

### Method A: Using psql (Command Line)

```bash
# Connect to PostgreSQL
psql -U postgres -h localhost

# In psql prompt:
postgres=# CREATE DATABASE wros_dev;
postgres=# CREATE USER app_user WITH PASSWORD 'app_password';
postgres=# ALTER USER app_user CREATEDB;
postgres=# GRANT ALL PRIVILEGES ON DATABASE wros_dev TO app_user;
postgres=# \q
```

### Method B: Using pgAdmin (GUI)

1. **Open pgAdmin 4:**
   - Installed with PostgreSQL
   - URL: http://localhost:5050 (or your computer's IP:5050)
   - Default login: pgadmin4@pgadmin.org / admin (or your email)

2. **Create Database:**
   - Right-click "Databases" in left sidebar
   - Create → Database
   - Name: `wros_dev`
   - Owner: `postgres`
   - Click "Save"

3. **Create User (Optional):**
   - Right-click "Login/Group Roles"
   - Create → Login/Group Role
   - Name: `app_user`
   - Password: `app_password`
   - Privileges: Can create DB? Yes
   - Click "Save"

---

## Step 4: Update Backend Configuration

**File:** `OnboardingModule-Backend/.env.local`

Already created with PostgreSQL settings:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wros_dev
```

**If you created a different user:**
```
DATABASE_URL=postgresql://app_user:app_password@localhost:5432/wros_dev
```

---

## Step 5: Install Python Dependencies

```bash
cd C:\Users\AvinashMukund\Documents\Claude\OnboardingModule-Backend

# Install/upgrade packages
pip install -r requirements.txt

# Verify psycopg2 installed
pip show psycopg2-binary
```

---

## Step 6: Run Alembic Migrations (Apply Phase 1 Schema)

This will create all tables, indexes, and constraints for Phase 1 (RBAC, permissions, audit logging).

```bash
cd C:\Users\AvinashMukund\Documents\Claude\OnboardingModule-Backend

# Show current migration status
alembic current

# Run all pending migrations (this applies Phase 1)
alembic upgrade head

# Verify migrations applied
alembic current
# Should show the latest migration version
```

---

## Step 7: Initialize Database Seed Data

**File:** `init_wros_db.py`

```bash
# Run initialization script to seed default data
python init_wros_db.py
```

This will create:
- Default roles (Super User, Admin, Recruiter, HR Manager, Finance, Partner, BU Head)
- Default permissions (17 core permissions)
- 3 default business units (NA, EU, APAC)
- Default tenant

---

## Step 8: Verify Phase 1 Setup

### Check PostgreSQL Tables Exist

```bash
# Connect to database
psql -U postgres -d wros_dev -h localhost

# List all tables
\dt

# Should see tables:
# - users
# - roles
# - permissions
# - user_roles (junction table)
# - business_units
# - tenants
# - ... (other Phase 1 tables)

# Exit psql
\q
```

### Test Backend Connection

```bash
cd OnboardingModule-Backend

# Start backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# In another terminal, test API
curl http://localhost:8080/health

# Should return: {"status": "ok"}
```

---

## Troubleshooting

### Error: "psql: command not found"
**Solution:** Add PostgreSQL bin to PATH:
```bash
$env:Path += ";C:\Program Files\PostgreSQL\15\bin"
```

### Error: "FATAL: Ident authentication failed for user postgres"
**Solution:** Edit `pg_hba.conf` (Windows):
- Find: `C:\Program Files\PostgreSQL\15\data\pg_hba.conf`
- Change `ident` to `md5` or `scram-sha-256`
- Restart PostgreSQL service
- Or use: `psql -U postgres -h localhost` (forces TCP, not Unix socket)

### Error: "FATAL: role 'postgres' does not exist"
**Solution:** PostgreSQL not started:
```bash
# Start PostgreSQL service (Windows)
net start postgresql-x64-15

# Or via Services: Start → services.msc → postgresql-x64-15 → Start
```

### Error: "Connection refused" or "Failed to connect"
**Causes & Fixes:**
1. PostgreSQL service not running
   - `net start postgresql-x64-15` or Services.msc
2. Port 5432 already in use
   - Change port in installation or .env.local
3. Wrong password
   - Check password matches your setup
4. Firewall blocking localhost:5432
   - Add exception or use `127.0.0.1` instead of `localhost`

---

## Migration Rollback (If Needed)

```bash
# Show all migrations
alembic history

# Downgrade to specific version
alembic downgrade <revision_id>

# Or downgrade one step
alembic downgrade -1

# Verify
alembic current
```

---

## Next Steps After Setup

1. ✅ PostgreSQL installed and running
2. ✅ Database created (`wros_dev`)
3. ✅ Alembic migrations applied (Phase 1 schema)
4. ✅ Seed data initialized
5. **→ Start backend:** `python -m uvicorn app.main:app --reload`
6. **→ Start frontend:** `npm start` (from OnboardingModule-Frontend-main)
7. **→ Verify Phase 1:** Login with seeded users, check RBAC/permissions working

---

## Production PostgreSQL on VPS

When ready to deploy to production VPS (after Phase 2 completion):

**See:** `POSTGRESQL_MIGRATION.md` for step-by-step VPS setup

Key differences:
- Ubuntu/Debian installation (not Windows)
- Strong password (not `postgres`)
- SSL/TLS configuration
- Backup strategy (pg_dump automation)
- Monitoring (pgAdmin or monitoring tools)

---

## Performance Tuning (Optional)

For local development with 200K+ candidates, optimize:

**File:** `C:\Program Files\PostgreSQL\15\data\postgresql.conf`

```ini
# Increase shared_buffers for 8GB+ RAM machines
shared_buffers = 256MB

# Increase work_mem for complex queries
work_mem = 16MB

# Increase effective_cache_size
effective_cache_size = 4GB

# Restart PostgreSQL after changes
```

---

**Status:** PostgreSQL ready for Phase 1 verification + Phase 2 development

**Estimated Time:** 20-30 minutes total setup
