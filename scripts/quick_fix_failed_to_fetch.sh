#!/bin/bash
# QUICK FIX: Database "Failed to Fetch" Login Issue
#
# Root cause: Database not initialized or tables missing
# Solution: Initialize database and run migrations
#
# Usage:
#   bash scripts/quick_fix_failed_to_fetch.sh
#
# For production SQL Server:
#   export DATABASE_URL="mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+17+for+SQL+Server"
#   bash scripts/quick_fix_failed_to_fetch.sh

set -e

echo "🔧 Fixing 'Failed to Fetch' Login Issue..."
echo "==========================================="

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "⚠️  DATABASE_URL not set. Using local SQLite..."
    export DATABASE_URL="sqlite:///./local_dev.sqlite3"
fi

echo "📍 Using database: ${DATABASE_URL%@*}@..."

# 1. Initialize database schema
echo ""
echo "1️⃣  Initializing database schema..."
python scripts/init_production_db.py

# 2. Run pending migrations
echo ""
echo "2️⃣  Running Alembic migrations..."
alembic upgrade head

# 3. Verify database connectivity
echo ""
echo "3️⃣  Verifying database connectivity..."
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

echo ""
echo "✅ Database fix complete!"
echo ""
echo "Next steps:"
echo "1. Restart backend server: cd app && uvicorn main:app --reload"
echo "2. Clear browser cache (Ctrl+Shift+Delete)"
echo "3. Try logging in again"
echo ""
echo "If issue persists:"
echo "- Check backend logs for database errors"
echo "- Verify DATABASE_URL is correct"
echo "- Run: alembic current (to check migration status)"
