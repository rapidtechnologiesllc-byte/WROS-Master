import os
from sqlalchemy import create_engine, text, inspect
import logging
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/wros_dev')

print(f"DATABASE_URL: {DATABASE_URL}")

try:
    engine = create_engine(DATABASE_URL)

    # Test connection
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("✓ Database connection successful!")

    # Get inspector
    inspector = inspect(engine)

    # List all schemas
    schemas = inspector.get_schema_names()
    print(f"\n=== Schemas in database ===")
    for schema in schemas:
        print(f"  - {schema}")

    # For each schema, list tables
    print(f"\n=== Tables in each schema ===")
    for schema in schemas:
        tables = inspector.get_table_names(schema=schema)
        print(f"\nSchema '{schema}':")
        if tables:
            for table in sorted(tables):
                print(f"    - {table}")
        else:
            print(f"    (no tables)")

    # Try to get all tables (no schema specified)
    print(f"\n=== All tables (default schema) ===")
    all_tables = inspector.get_table_names()
    if all_tables:
        for table in sorted(all_tables):
            print(f"    - {table}")
    else:
        print("    (no tables)")

except Exception as e:
    logger.error(f"Error: {str(e)}", exc_info=True)
    logger.error(f"Error: {str(e)}", exc_info=True)
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
