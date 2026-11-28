"""Dry run of the job kinds classification (docs/RECRUITMENT_VS_WORKFORCE_DESIGN.md section 4 step 1): what each
existing job would be recorded as, and which go to the manual review list, without writing anything.

Run it against the masked production copy before releasing (backend/.env.local pointing at wros_prodcopy):
    python scripts/job_kinds_report.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.services.job_kind_service import classify  # noqa: E402

db = SessionLocal()
try:
    report = classify(db, dry_run=True)
    db.rollback()
finally:
    db.close()
print(f"jobs to classify: {report['classified']}")
for key, count in report["by_tenant_and_kind"].items():
    print(f"  tenant {key}: {count}")
print(f"manual review: {len(report['review'])}")
for item in report["review"]:
    print(f"  {item['job_id']} (tenant {item['tenant_id']}) {item['title']!r}: {item['reason']}")
