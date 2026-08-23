from app.core.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        # Add partner_id column if it doesn't exist
        conn.execute(text('ALTER TABLE users ADD COLUMN partner_id INTEGER REFERENCES partners(id)'))
        print("Added partner_id column")
    except Exception as e:
        print(f"partner_id: {e}")

    try:
        # Add delivery_center_id column if it doesn't exist
        conn.execute(text('ALTER TABLE users ADD COLUMN delivery_center_id INTEGER'))
        print("Added delivery_center_id column")
    except Exception as e:
        print(f"delivery_center_id: {e}")

    conn.commit()
    print("Done")
