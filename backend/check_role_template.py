import os
from sqlalchemy import create_engine, text
import logging
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/wros_dev')

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        # Check role template 8
        result = conn.execute(text("""
            SELECT id, name, enabled, tenant_id
            FROM app_schema.role_templates
            WHERE id = 8
        """))

        print("=== Role Template 8 ===")
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f"  ID: {row[0]}, Name: {row[1]}, Enabled: {row[2]}, TenantID: {row[3]}")
        else:
            print("  Not found!")

        # Check all role templates
        result2 = conn.execute(text("""
            SELECT id, name, enabled, tenant_id
            FROM app_schema.role_templates
            ORDER BY id
        """))
        print("\n=== All Role Templates ===")
        for row in result2:
            print(f"  ID: {row[0]}, Name: {row[1]}, Enabled: {row[2]}, TenantID: {row[3]}")

except Exception as e:
    logger.error(f"Error: {str(e)}", exc_info=True)
    logger.error(f"Error: {str(e)}", exc_info=True)
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
