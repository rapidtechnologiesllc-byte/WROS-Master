from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    tables_to_drop = ['queue_doctor_state', 'msgraph_sessions']

    for table in tables_to_drop:
        try:
            db.execute(text(f'DROP TABLE IF EXISTS "app_schema"."{table}" CASCADE'))
            print("Dropped table:", table)
        except Exception as e:
            print(f"Error dropping {table}: {e}")

    db.commit()
    print("Schema cleanup complete")
except Exception as e:
    print(f"Error: {e}")
    db.rollback()
finally:
    db.close()
