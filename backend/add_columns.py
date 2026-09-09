#!/usr/bin/env python3
import os
os.environ['DATABASE_URL'] = 'postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/wros_dev'

from sqlalchemy import create_engine, text

engine = create_engine(os.environ['DATABASE_URL'])

columns = {
    'status_changed_at': 'TIMESTAMP',
    'previous_status': 'VARCHAR(100)',
    'status_change_reason': 'VARCHAR(500)',
    'upload_status': "VARCHAR(50) DEFAULT 'uploading'",
    'expected_document_count': 'INTEGER DEFAULT 0',
    'actual_document_count': 'INTEGER DEFAULT 0',
    'upload_started_at': 'TIMESTAMP',
    'last_document_uploaded_at': 'TIMESTAMP',
    'queued_at': 'TIMESTAMP',
    'processing_started_at': 'TIMESTAMP',
    'processing_completed_at': 'TIMESTAMP',
    'upload_error': 'TEXT',
    'celery_task_id': 'VARCHAR(512)'
}

for col_name, col_type in columns.items():
    with engine.connect() as conn:
        try:
            sql = f"ALTER TABLE app_schema.candidates ADD COLUMN {col_name} {col_type}"
            conn.execute(text(sql))
            conn.commit()
            print(f"[OK] {col_name}")
        except Exception as e:
            err_str = str(e).lower()
            if "already exists" in err_str or "duplicate" in err_str:
                print(f"[OK] {col_name} (exists)")
            else:
                print(f"[SKIP] {col_name}: {str(e)[:40]}")

print("\n[OK] Schema updated!")
