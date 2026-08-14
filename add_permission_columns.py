"""Add missing permission columns to users table"""
from app.core.database import SessionLocal, engine
import sqlite3

# Connect to SQLite database directly
db_path = "./onboarding.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check if columns exist and add if they don't
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]

    print("Current columns in users table:")
    for col in columns:
        print(f"  - {col}")

    # Add missing columns
    if 'job_title_id' not in columns:
        print("\nAdding job_title_id column...")
        cursor.execute("ALTER TABLE users ADD COLUMN job_title_id INTEGER")
        print("✓ job_title_id added")

    if 'org_position_id' not in columns:
        print("Adding org_position_id column...")
        cursor.execute("ALTER TABLE users ADD COLUMN org_position_id INTEGER")
        print("✓ org_position_id added")

    if 'org_node_id' not in columns:
        print("Adding org_node_id column...")
        cursor.execute("ALTER TABLE users ADD COLUMN org_node_id VARCHAR(36)")
        print("✓ org_node_id added")

    conn.commit()
    print("\n✓ Database schema updated successfully")

except sqlite3.OperationalError as e:
    if "already exists" in str(e):
        print(f"✓ Column already exists: {e}")
    else:
        print(f"Error: {e}")
finally:
    conn.close()
