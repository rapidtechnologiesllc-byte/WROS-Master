# BlitzenX WROS Production Deployment Guide

## Database Setup for Production SQL Server

### Prerequisites
- SQL Server 2019+ instance
- ODBC Driver 17 for SQL Server installed
- Network access to SQL Server from application server
- Administrative credentials to create database and user

### Step 1: Create Production Database

Connect to SQL Server with admin credentials:

```sql
-- Create database
CREATE DATABASE BlitzenX_WROS;
GO

-- Create database user (SQL Authentication)
USE BlitzenX_WROS;
CREATE LOGIN wros_app WITH PASSWORD = 'YourComplexPassword123!@#';
CREATE USER wros_app FOR LOGIN wros_app;
ALTER ROLE db_owner ADD MEMBER wros_app;
GO

-- Enable required SQL Server features for connections
-- (Run on master database)
EXEC sp_configure 'allow updates', 1;
RECONFIGURE;
GO
```

### Step 2: Configure Production Environment

Copy and configure environment file:

```bash
cp .env.production.template .env.production
# Edit .env.production with actual production values
```

**Required values to update:**

```
DATABASE_URL=mssql+pyodbc://wros_app:YourComplexPassword123!@#@prod-sqlserver.blitzenx.com/BlitzenX_WROS?driver=ODBC+Driver+17+for+SQL+Server

# Update all Azure/Microsoft authentication credentials
TENANT_ID=...
CLIENT_ID=...
CLIENT_SECRET=...

# Update JWT keys from Azure Key Vault
JWT_PRIVATE_KEY=...
JWT_PUBLIC_KEY=...

# Update Gemini API key
GEMINI_API_KEY=...

# Update production URLs
PRODUCTION_BACKEND_URL=https://hrms-backend.blitzenx.com/
PRODUCTION_FRONTEND_URL=https://hrms.blitzenx.com/
```

### Step 3: Initialize Database Schema

Run the initialization script to create all tables:

```bash
# From application root directory
export DATABASE_URL="mssql+pyodbc://wros_app:Password@server/BlitzenX_WROS?driver=ODBC+Driver+17+for+SQL+Server"

python scripts/init_production_db.py
```

Expected output:
```
Initializing database: mssql+pyodbc://wros_app:***@prod-sqlserver.blitzenx.com/BlitzenX_WROS...
Creating tables...
✓ Database initialized successfully
✓ 180+ tables created

✅ Database initialization complete!
```

### Step 4: Run Database Migrations (If Adding Schema Changes)

After initial setup, for any schema updates use Alembic:

```bash
# Set production DATABASE_URL
export DATABASE_URL="mssql+pyodbc://wros_app:Password@server/BlitzenX_WROS?driver=ODBC+Driver+17+for+SQL+Server"

# View pending migrations
alembic current
alembic history

# Run all pending migrations
alembic upgrade head

# Or run specific migration
alembic upgrade <revision_id>
```

### Step 5: Verify Database Connectivity

Create a simple test script:

```python
# test_db_connection.py
from sqlalchemy import create_engine, text
import os

database_url = os.getenv("DATABASE_URL")
engine = create_engine(database_url, pool_pre_ping=True)

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) as table_count FROM information_schema.tables"))
        row = result.fetchone()
        print(f"✓ Database connected! {row[0]} tables found")
except Exception as e:
    print(f"✗ Connection failed: {e}")
```

Run the test:
```bash
export DATABASE_URL="your_production_url"
python test_db_connection.py
```

### Step 6: Seed Initial Data (If Needed)

For production, you may need to seed:

```bash
# Seed tenants, users, business units, departments, etc.
python scripts/seed_production_data.py
```

### Step 7: Start Application

```bash
# Development (for testing)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production (with Gunicorn)
gunicorn -w 4 -b 0.0.0.0:8000 "app.main:app" --access-logfile - --error-logfile -
```

---

## Troubleshooting

### Connection String Issues

**Error: "No ODBC driver found"**
- Install: `ODBC Driver 17 for SQL Server`
- Verify: `python -c "import pyodbc; print(pyodbc.drivers())"`

**Error: "Cannot open database"**
- Verify database name exists
- Check user permissions: `SELECT * FROM sys.database_principals`
- Verify network access to SQL Server host

**Error: "Login failed for user"**
- Verify username and password in connection string
- Test with SQL Server Management Studio first
- Check user account is not locked

### Table Creation Issues

**Error: "Permission denied"**
- User must have `CREATE TABLE` and `ALTER SCHEMA` permissions
- Grant with: `ALTER ROLE db_owner ADD MEMBER wros_app`

**Error: "Constraint violation"**
- Run initialization on empty database only
- If re-running, first drop all tables: `DROP TABLE IF EXISTS table_name`

### Application Won't Start

**Check logs:**
```bash
# View application logs
tail -f logs/app.log

# Test database in Python
python -c "from app.core.database import engine; print(engine.execute('SELECT 1'))"
```

---

## Database Backup Strategy

Production SQL Server should have automated backups:

```sql
-- Daily backup to shared drive
BACKUP DATABASE [BlitzenX_WROS]
TO DISK = N'\\\\backupserver\\backups\\BlitzenX_WROS_daily.bak'
WITH NOFORMAT, NOINIT, NAME = 'BlitzenX_WROS_daily', SKIP, NOREWIND, NOUNLOAD, STATS = 10;

-- Transaction log backup (hourly)
BACKUP LOG [BlitzenX_WROS]
TO DISK = N'\\\\backupserver\\backups\\BlitzenX_WROS_tlog.trn'
WITH NOFORMAT, NOINIT, SKIP, NOREWIND, NOUNLOAD, STATS = 10;
```

---

## Performance Tuning

### Indexes

BlitzenX models define indexes in `__table_args__`. Verify they're created:

```sql
-- Check indexes on key tables
SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_NAME IN ('candidates', 'employees', 'jobs', 'opportunities')
ORDER BY TABLE_NAME, INDEX_NAME;
```

### Connection Pooling

Default pool settings in `app/core/database.py`:
```python
pool_size=20  # Connections to maintain
max_overflow=40  # Additional connections under load
pool_recycle=3600  # Recycle connections every hour
```

Adjust based on expected concurrent connections.

### Query Optimization

Monitor slow queries in SQL Server:
```sql
-- Find slowest queries
SELECT TOP 20 execution_count, total_elapsed_time/1000 AS total_time_ms, 
       total_elapsed_time/execution_count/1000 AS avg_time_ms, 
       query_plan, SUBSTRING(st.text, 1, 100) AS query_text
FROM sys.dm_exec_query_stats qs
CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st
ORDER BY total_elapsed_time DESC;
```

---

## Monitoring

### Health Checks

Application exposes health check endpoint:
```bash
curl https://hrms-backend.blitzenx.com/health
# Response: {"status": "healthy", "database": "connected", "timestamp": "..."}
```

### Database Monitoring

Monitor connection count and disk usage:

```sql
-- Current connections
SELECT COUNT(*) as active_connections FROM sys.dm_exec_sessions WHERE database_id = DB_ID();

-- Database size
EXEC sp_spaceused;

-- Long-running transactions
SELECT * FROM sys.dm_exec_requests WHERE status = 'running';
```

---

## Rollback Procedure

If deployment fails, rollback with Alembic:

```bash
# See migration history
alembic history

# Downgrade to previous version
alembic downgrade -1

# Or specific version
alembic downgrade <revision_id>
```

---

## Next Steps After Deployment

1. **Verify API endpoints** — Test all major endpoints with production data
2. **Monitor logs** — Watch for errors in first 24 hours
3. **Run integration tests** — Verify end-to-end workflows
4. **Set up alerts** — Configure monitoring for database and application
5. **Load testing** — Verify performance under expected load
6. **Backup verification** — Test restore procedures

---

## Support

For database issues, check:
- SQL Server error log: `C:\Program Files\Microsoft SQL Server\MSSQL15.MSSQLSERVER\MSSQL\Log\ERRORLOG`
- Application logs: Check configured logging directory
- Alembic status: `alembic current`
