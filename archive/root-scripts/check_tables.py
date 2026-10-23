#!/usr/bin/env python3
from app.core.database import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"))
        tables = result.fetchall()
        if tables:
            print(f"Found {len(tables)} tables in database")
            for (table,) in tables[:10]:
                print(f"   - {table}")
            if len(tables) > 10:
                print(f"   ... and {len(tables)-10} more tables")
        else:
            print("Database is empty - no tables found")
except Exception as e:
    print(f"Error: {e}")
