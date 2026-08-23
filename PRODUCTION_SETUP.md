# Production Setup & "Failed to Fetch" Login Fix

## Quick Fix: "Failed to Fetch" Error

If users are seeing "Failed to fetch" on login, the database is likely not initialized.

### Immediate Fix (5 minutes)

**Windows:**
```batch
scripts\quick_fix_failed_to_fetch.bat
```

**Linux/Mac:**
```bash
bash scripts/quick_fix_failed_to_fetch.sh
```

This will:
1. ✅ Initialize database schema (creates all tables from models)
2. ✅ Run pending Alembic migrations
3. ✅ Verify database connectivity
4. ✅ Provide next steps

### If Using Production SQL Server

Before running the quick fix, set your production database:

**Windows Command Prompt:**
```batch
set DATABASE_URL=mssql+pyodbc://username:password@server.domain.com/BlitzenX_WROS?driver=ODBC+Driver+17+for+SQL+Server
scripts\quick_fix_failed_to_fetch.bat
```

**PowerShell:**
```powershell
$env:DATABASE_URL = "mssql+pyodbc://username:password@server/BlitzenX_WROS?driver=ODBC+Driver+17+for+SQL+Server"
python scripts/init_production_db.py
alembic upgrade head
```

**Linux/Mac:**
```bash
export DATABASE_URL="mssql+pyodbc://username:password@server/BlitzenX_WROS?driver=ODBC+Driver+17+for+SQL+Server"
bash scripts/quick_fix_failed_to_fetch.sh
```

---

## Full Production Setup

For complete production deployment instructions, see:
- **DEPLOYMENT_GUIDE.md** — Comprehensive production deployment
- **.env.production.template** — Production environment configuration

### Key Steps:

1. **Create SQL Server Database** (run as DBA)
```sql
CREATE DATABASE BlitzenX_WROS;
GO
USE BlitzenX_WROS;
CREATE LOGIN wros_app WITH PASSWORD = 'ComplexPassword123!@#';
CREATE USER wros_app FOR LOGIN wros_app;
ALTER ROLE db_owner ADD MEMBER wros_app;
GO
```

2. **Configure Environment**
```bash
cp .env.production.template .env.production
# Edit .env.production with your SQL Server connection string and credentials
```

3. **Initialize Database Schema**
```bash
export DATABASE_URL="mssql+pyodbc://wros_app:Password@server/BlitzenX_WROS?driver=ODBC+Driver+17+for+SQL+Server"
python scripts/init_production_db.py
```

4. **Run Migrations**
```bash
alembic upgrade head
```

5. **Start Application**
```bash
# With Gunicorn (production recommended)
gunicorn -w 4 -b 0.0.0.0:8000 "app.main:app"

# Or with Uvicorn (development)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Database Connection Strings

### SQL Server (Windows Authentication)
```
mssql+pyodbc://server_hostname/database_name?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes
```

### SQL Server (SQL Authentication)
```
mssql+pyodbc://username:password@server_hostname/database_name?driver=ODBC+Driver+17+for+SQL+Server
```

### PostgreSQL
```
postgresql://username:password@host:5432/database_name
```

### SQLite (Development Only)
```
sqlite:///./local_dev.sqlite3
```

---

## Troubleshooting

### "Cannot open database" Error
- Database doesn't exist
- Connection string is incorrect
- User doesn't have permissions

**Fix:**
```sql
-- Verify database exists
SELECT name FROM sys.databases WHERE name = 'BlitzenX_WROS';

-- Verify user permissions
USE BlitzenX_WROS;
SELECT * FROM sys.database_role_members WHERE role_principal_id = 
  (SELECT principal_id FROM sys.database_principals WHERE name = 'db_owner');
```

### "No ODBC Driver Found" Error
Install ODBC Driver 17 for SQL Server:
- Windows: https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server
- Linux: `apt-get install odbc-mdbtools`
- Mac: `brew install unixodbc`

### "Login Failed" Error
- Verify username and password in connection string
- Check account is not locked: `EXEC sp_who` in SQL Server
- Test connection with SQL Server Management Studio first

### "Permission Denied" Creating Tables
User needs `ALTER SCHEMA` and `CREATE TABLE` permissions:

```sql
USE BlitzenX_WROS;
GRANT ALTER ON SCHEMA::dbo TO wros_app;
GRANT CREATE TABLE TO wros_app;
```

---

## Database Tables

The application creates 180+ tables across these categories:

**Core Entities:**
- Tenants, Users, Candidates, Employees
- Jobs, Opportunities, Projects
- Business Units, Departments

**Workflow:**
- Interviews, Offers, Onboarding
- Tasks, Activities, Timesheets
- Allocations, Deployments

**Financial:**
- Invoices, Expenses, Payments
- Rates, Costs, Revenue Tracking

**AI/Agents:**
- Agent Execution Logs
- Agent Maturity, Performance Metrics
- AI Configuration, Prompts

**Audit & Compliance:**
- Audit Logs, Event Logs
- Consent Records, Activity Feeds

All tables include `tenant_id` for multi-tenant isolation.

---

## Performance Tuning

### Connection Pool Configuration

Edit `app/core/database.py` for your expected load:

```python
create_engine(
    database_url,
    pool_size=20,  # Maintain 20 connections
    max_overflow=40,  # Allow up to 60 during peaks
    pool_recycle=3600,  # Recycle connections hourly
    pool_pre_ping=True,  # Test connections before use
)
```

### Recommended for Production:
- `pool_size=50` — Supports 50+ concurrent users
- `max_overflow=100` — Handle traffic spikes
- `pool_pre_ping=True` — Verify connections still alive

### Monitor Connection Usage:

```sql
-- Active connections to database
SELECT COUNT(*) as active_connections FROM sys.dm_exec_sessions 
WHERE database_id = DB_ID('BlitzenX_WROS');

-- Connection pool statistics
SELECT * FROM sys.dm_exec_connections WHERE session_id > 50;
```

---

## Backups

### Automated SQL Server Backups

Schedule daily and transaction log backups:

```sql
-- Daily backup (11 PM)
BACKUP DATABASE [BlitzenX_WROS]
TO DISK = N'\\\\backup-server\\database\\BlitzenX_WROS_daily.bak'
WITH NOFORMAT, NOINIT, NAME = 'BlitzenX_WROS_daily', SKIP, NOREWIND, STATS = 10;

-- Hourly transaction log backups (for point-in-time recovery)
BACKUP LOG [BlitzenX_WROS]
TO DISK = N'\\\\backup-server\\database\\BlitzenX_WROS.trn'
WITH NOFORMAT, NOINIT, SKIP, NOREWIND, STATS = 10;
```

---

## Next Steps

After database is initialized and application starts:

1. **Verify API Health**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Test Login**
   - Navigate to https://hrms.blitzenx.com
   - Try test credentials

3. **Monitor Logs**
   ```bash
   tail -f logs/app.log
   tail -f logs/database.log
   ```

4. **Run Integration Tests**
   ```bash
   pytest tests/ -v
   ```

5. **Load Test** (optional but recommended)
   ```bash
   locust -f tests/load/locustfile.py
   ```

---

## Support & Documentation

- **DEPLOYMENT_GUIDE.md** — Full production deployment walkthrough
- **CLAUDE.md** — Project development notes
- **BLITZENX_OPERATING_MODEL.md** — Institutional architecture

For questions or issues, check logs and refer to DEPLOYMENT_GUIDE.md troubleshooting section.
