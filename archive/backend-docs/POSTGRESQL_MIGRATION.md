# PostgreSQL Migration Guide

**Status:** Ready for deployment
**Timeline:** 15-30 minutes
**Downtime:** < 5 minutes (during data import)
**Risk:** LOW (SQLite file remains as backup)

## Prerequisites

- VPS with Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+)
- Root or sudo access
- ~50GB free disk space (for 200K candidates)
- Backend currently running on SQLite

---

## Step 1: Install PostgreSQL on VPS

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib libpq-dev

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Verify installation
psql --version
```

**Expected output:**
```
psql (PostgreSQL) 12.x or higher
```

---

## Step 2: Create Database and User

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Run these commands in psql:
CREATE DATABASE onboarding_prod;
CREATE USER app_user WITH PASSWORD 'generate_secure_password_here';
ALTER ROLE app_user SET client_encoding TO 'utf8';
ALTER ROLE app_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE app_user SET default_transaction_deferrable TO on;
ALTER ROLE app_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE onboarding_prod TO app_user;
\q
```

**Verify:**
```bash
psql -U app_user -d onboarding_prod -c "SELECT version();"
```

---

## Step 3: Export SQLite Schema & Data

On the VPS (or your dev machine):

```bash
# Install SQLite tools if not present
sudo apt-get install -y sqlite3

# Backup original SQLite
cp local_dev.sqlite3 local_dev.sqlite3.backup

# Export schema and data
sqlite3 local_dev.sqlite3 .dump > sqlite_dump.sql
```

---

## Step 4: Import into PostgreSQL

```bash
# Clean up SQLite-specific syntax (optional but recommended)
sed -i '/^PRAGMA/d' sqlite_dump.sql
sed -i '/^BEGIN TRANSACTION/d' sqlite_dump.sql
sed -i '/^COMMIT/d' sqlite_dump.sql

# Import into PostgreSQL
psql -U app_user -d onboarding_prod -f sqlite_dump.sql
```

**Verify import:**
```bash
psql -U app_user -d onboarding_prod -c "SELECT COUNT(*) FROM candidates;"
```

---

## Step 5: Update Environment Variables

Edit `.env` on VPS:

```bash
# OLD (SQLite)
# DATABASE_URL=sqlite:///./local_dev.sqlite3

# NEW (PostgreSQL)
DATABASE_URL=postgresql://app_user:secure_password@localhost:5432/onboarding_prod
```

---

## Step 6: Update Python Requirements

Add to `requirements.txt`:

```
psycopg2-binary==2.9.9
```

Install:
```bash
pip install -r requirements.txt
```

---

## Step 7: Restart Backend

```bash
# Kill old backend
pkill -f "uvicorn"

# Restart with PostgreSQL
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

**Verify connection:**
```bash
curl http://localhost:8080/candidates/bulk-import/list | head
```

Expected: JSON response with import jobs

---

## Step 8: Verify All Systems

```bash
# Check database connection
psql -U app_user -d onboarding_prod -c "\dt"

# Check candidate count
psql -U app_user -d onboarding_prod -c "SELECT COUNT(*) as total_candidates FROM candidates;"

# Check import jobs
psql -U app_user -d onboarding_prod -c "SELECT COUNT(*) as total_jobs FROM bulk_engagement_jobs;"

# Test backend API
curl -s http://localhost:8080/candidates/bulk-import/list | python -m json.tool | head -20
```

---

## Rollback Plan (if needed)

If anything goes wrong:

```bash
# 1. Stop backend
pkill -f "uvicorn"

# 2. Revert to SQLite in .env
# Set DATABASE_URL=sqlite:///./local_dev.sqlite3

# 3. Restart backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# 4. PostgreSQL can stay installed (just unused)
# Or drop it: sudo systemctl stop postgresql
```

---

## Performance Improvements Expected

After PostgreSQL migration:

| Metric | SQLite | PostgreSQL |
|--------|--------|-----------|
| Concurrent Writes | 1 | Unlimited |
| Thunder Processing | Freezes | Continuous 20/min |
| Bulk Import Lock | Every 2-3K rows | Never |
| 200K Candidate Import Time | Hours (with freezing) | ~3-5 minutes |
| Thunder Time to Process 200K | 7+ days (with lock pauses) | 10,000 min = 7 days (continuous) |

---

## Verification Checklist

- [ ] PostgreSQL installed and running
- [ ] Database `onboarding_prod` created
- [ ] User `app_user` created with correct permissions
- [ ] Data imported successfully (row counts match)
- [ ] `.env` updated with PostgreSQL URL
- [ ] `requirements.txt` updated with psycopg2-binary
- [ ] Backend restarted and responding
- [ ] API endpoints returning data
- [ ] No database lock errors in logs
- [ ] Thunder continues processing during bulk import

---

## Support

If issues arise:

1. Check PostgreSQL logs: `sudo tail -f /var/log/postgresql/postgresql-*.log`
2. Check backend logs: `tail -f app.log` or check stdout
3. Test connection: `psql -U app_user -d onboarding_prod`
4. Verify user permissions: `\du` in psql
