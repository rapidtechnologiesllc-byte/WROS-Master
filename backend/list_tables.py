import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/wros_dev')

try:
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)

    tables = inspector.get_table_names()
    print(f"=== Tables in wros_dev database ({len(tables)} total) ===")

    if tables:
        for table in sorted(tables):
            print(f"  - {table}")
    else:
        print("  No tables found!")

    print("\n=== Checking for 'Users' or 'users' table ===")
    if 'users' in tables:
        print("  ✓ Found lowercase 'users' table")
    elif 'Users' in tables:
        print("  ✓ Found capitalized 'Users' table")
    else:
        print("  ✗ 'users' table NOT FOUND")
        print("  ✗ 'Users' table NOT FOUND")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
