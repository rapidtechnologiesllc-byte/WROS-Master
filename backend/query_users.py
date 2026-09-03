import os
from sqlalchemy import create_engine, text
import logging
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/wros_dev')

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        # Query for the 3 users
        result = conn.execute(text("""
            SELECT UserID, UserName, UserEmail, role_template_id
            FROM Users
            WHERE UserEmail IN ('superuser@blitzenx.com', 'formtest@example.com', 'integration.suite@example.com')
            ORDER BY UserName
        """))

        print("=== Users in Database ===")
        rows = result.fetchall()
        if rows:
            print(f"Found {len(rows)} users:")
            for row in rows:
                print(f"  UserID: {row[0]}, Name: {row[1]}, Email: {row[2]}, RoleTemplateID: {row[3]}")
        else:
            print("No users found!")

        # Query for role templates
        result2 = conn.execute(text("SELECT id, name FROM RoleTemplates WHERE name = 'Testing 3'"))
        print("\n=== Role Template 'Testing 3' ===")
        rows2 = result2.fetchall()
        if rows2:
            for row in rows2:
                print(f"  ID: {row[0]}, Name: {row[1]}")
        else:
            print("Role template 'Testing 3' not found!")

except Exception as e:
    logger.error(f"Error: {str(e)}", exc_info=True)
    logger.error(f"Error: {str(e)}", exc_info=True)
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
