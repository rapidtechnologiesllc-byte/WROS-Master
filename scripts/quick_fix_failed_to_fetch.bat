@echo off
REM QUICK FIX: Database "Failed to Fetch" Login Issue (Windows)
REM
REM Root cause: Database not initialized or tables missing
REM Solution: Initialize database and run migrations
REM
REM Usage:
REM   scripts\quick_fix_failed_to_fetch.bat
REM
REM For production SQL Server, set DATABASE_URL before running:
REM   set DATABASE_URL=mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+17+for+SQL+Server
REM   scripts\quick_fix_failed_to_fetch.bat

setlocal enabledelayedexpansion

echo.
echo 🔧 Fixing 'Failed to Fetch' Login Issue...
echo ===========================================
echo.

REM Check if DATABASE_URL is set
if not defined DATABASE_URL (
    echo ⚠️  DATABASE_URL not set. Using local SQLite...
    set DATABASE_URL=sqlite:///./local_dev.sqlite3
)

echo 📍 Using database: !DATABASE_URL!
echo.

REM 1. Initialize database schema
echo 1️⃣  Initializing database schema...
python scripts\init_production_db.py
if errorlevel 1 (
    echo ❌ Database initialization failed
    exit /b 1
)
echo.

REM 2. Run pending migrations
echo 2️⃣  Running Alembic migrations...
alembic upgrade head
if errorlevel 1 (
    echo ⚠️  Migration warning (may be expected)
)
echo.

REM 3. Verify database connectivity
echo 3️⃣  Verifying database connectivity...
python -c "
from sqlalchemy import create_engine, text
import os

db_url = os.getenv('DATABASE_URL')
engine = create_engine(db_url) if 'sqlite' not in db_url else create_engine(db_url, connect_args={'check_same_thread': False})

try:
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print('✅ Database connection OK')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    exit(1)
"
if errorlevel 1 (
    echo ❌ Database verification failed
    exit /b 1
)
echo.

echo ✅ Database fix complete!
echo.
echo Next steps:
echo 1. Restart backend server:
echo    cd app
echo    uvicorn main:app --reload
echo 2. Clear browser cache (Ctrl+Shift+Delete)
echo 3. Try logging in again
echo.
echo If issue persists:
echo - Check backend logs for database errors
echo - Verify DATABASE_URL is correct
echo - Run: alembic current (to check migration status)
echo.

endlocal
pause
