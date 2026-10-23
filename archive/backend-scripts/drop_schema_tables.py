from app.core.database import SessionLocal, engine
from sqlalchemy import text

db = SessionLocal()
try:
    # Drop tables that have schema issues
    for table in ['candidates', 'jobs', 'msgraph_sessions']:
        try:
            db.execute(text(f'DROP TABLE IF EXISTS "app_schema"."{table}" CASCADE'))
            print(f"Dropped table: {table}")
        except Exception as e:
            print(f"Could not drop {table}: {e}")

    db.commit()
    print("Tables dropped successfully")
except Exception as e:
    print(f"Error: {e}")
    db.rollback()
finally:
    db.close()
