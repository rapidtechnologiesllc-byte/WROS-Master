import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/wros_dev')

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        # First check current state
        result = conn.execute(text("""
            SELECT id, name, enabled, tenant_id
            FROM app_schema.role_templates
            WHERE id = 8
        """))
        print("=== Role Template 8 - BEFORE ===")
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f"  ID: {row[0]}, Name: {row[1]}, Enabled: {row[2]}, TenantID: {row[3]}")

        # Fix it: set enabled=true and tenant_id=1
        conn.execute(text("""
            UPDATE app_schema.role_templates
            SET enabled = true, tenant_id = 1
            WHERE id = 8
        """))
        conn.commit()
        print("\n✓ Updated role template 8")

        # Verify the fix
        result2 = conn.execute(text("""
            SELECT id, name, enabled, tenant_id
            FROM app_schema.role_templates
            WHERE id = 8
        """))
        print("\n=== Role Template 8 - AFTER ===")
        rows2 = result2.fetchall()
        if rows2:
            for row in rows2:
                print(f"  ID: {row[0]}, Name: {row[1]}, Enabled: {row[2]}, TenantID: {row[3]}")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
