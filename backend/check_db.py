import logging
from sqlalchemy import create_engine, text

# Connect to wros_test and check tables
engine = create_engine('postgresql://postgres:123@localhost:5432/wros_test')
with engine.connect() as conn:
    # List all tables
    result = conn.execute(text("""
        SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename
    """)).fetchall()

    tables = [r[0] for r in result]
    print(f"Tables in wros_test ({len(tables)} total):")
    for t in tables:
        print(f"  - {t}")

    # Check job_titles indexes
    if 'job_titles' in tables:
        result2 = conn.execute(text("""
            SELECT indexname FROM pg_indexes WHERE tablename = 'job_titles'
        """)).fetchall()
        print(f"\nIndexes on job_titles:")
        for idx in result2:
            print(f"  - {idx[0]}")
