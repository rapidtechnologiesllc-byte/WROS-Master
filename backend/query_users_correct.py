import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/wros_dev')

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        # Query from app_schema (not public)
        result = conn.execute(text("""
            SELECT "UserID", "UserName", "UserEmail", "role_template_id"
            FROM app_schema.users
            WHERE "UserEmail" IN ('superuser@blitzenx.com', 'formtest@example.com', 'integration.suite@example.com')
            ORDER BY "UserName"
        """))

        print("=== Users in Database (app_schema) ===")
        rows = result.fetchall()
        if rows:
            print(f"✓ Found {len(rows)} users:")
            for row in rows:
                print(f"  - UserID: {row[0]}, Name: {row[1]}, Email: {row[2]}, RoleTemplateID: {row[3]}")
        else:
            print("✗ No users found!")

        # Query role templates
        result2 = conn.execute(text("""
            SELECT id, name FROM app_schema.role_templates WHERE name = 'Testing 3'
        """))
        print("\n=== Role Template 'Testing 3' ===")
        rows2 = result2.fetchall()
        if rows2:
            for row in rows2:
                print(f"  ✓ ID: {row[0]}, Name: {row[1]}")
        else:
            print("  ✗ Not found!")

        # Check if formtest user's role_template exists
        result3 = conn.execute(text("""
            SELECT rt.id, rt.name
            FROM app_schema.role_templates rt
            WHERE rt.id = (SELECT "role_template_id" FROM app_schema.users WHERE "UserEmail" = 'formtest@example.com')
        """))
        print("\n=== formtest@example.com's Role Template ===")
        rows3 = result3.fetchall()
        if rows3:
            for row in rows3:
                print(f"  ✓ ID: {row[0]}, Name: {row[1]}")
        else:
            print("  ✗ No role template found for formtest user")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
