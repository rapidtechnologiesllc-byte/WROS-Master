#!/usr/bin/env python3
import logging
"""Phase 1 Re-seeding: Execute corrected PostgreSQL scripts"""

from app.core.database import SessionLocal
from sqlalchemy import text
import sys

db = SessionLocal()

print('='*70)
print('PHASE 1 RE-SEEDING: COMPLETE EXECUTION')
print('='*70)

# STEP 1: Cleanup
print('\nSTEP 1: Cleanup previous incomplete data')
print('-' * 70)

with open('C:/dev/ROLLBACK_RESOURCES_VALIDATED_POSTGRESQL.sql', 'r') as f:
    rollback_sql = f.read()

statements = [s.strip() for s in rollback_sql.split(';') if s.strip() and not s.strip().startswith('--')]
for statement in statements:
    try:
        db.execute(text(statement))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error: {str(e)}", exc_info=True)
        pass  # Ignore cleanup errors

db.commit()

from app.models.role_template import Resource, RoleTemplatePermission
res_before = db.query(Resource).filter(Resource.tenant_id == 1).count()
perm_before = db.query(RoleTemplatePermission).count()

print(f'Cleanup complete:')
print(f'  Resources: {res_before}')
print(f'  Permissions: {perm_before}')

# STEP 2: Insert 175 resources
print('\nSTEP 2: Insert 175 resources')
print('-' * 70)

with open('C:/dev/INSERT_RESOURCES_VALIDATED_POSTGRESQL.sql', 'r') as f:
    resources_sql = f.read()

statements = [s.strip() for s in resources_sql.split(';') if s.strip() and not s.strip().startswith('--')]
for i, statement in enumerate(statements):
    try:
        db.execute(text(statement))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error: {str(e)}", exc_info=True)
        print(f'Error in statement {i+1}: {str(e)[:150]}')

db.commit()

res_after = db.query(Resource).filter(Resource.tenant_id == 1).count()
print(f'Resources inserted:')
print(f'  Total: {res_after}')
print(f'  Expected: 175')
print(f'  Status: {"CORRECT" if res_after == 175 else "NEEDS REVIEW"}')

# STEP 3: Insert 294 permissions
print('\nSTEP 3: Insert 294 permissions')
print('-' * 70)

with open('C:/dev/INSERT_PERMISSIONS_VALIDATED_POSTGRESQL.sql', 'r') as f:
    perms_sql = f.read()

statements = [s.strip() for s in perms_sql.split(';') if s.strip() and not s.strip().startswith('--')]
for i, statement in enumerate(statements):
    try:
        db.execute(text(statement))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error: {str(e)}", exc_info=True)
        if 'already exists' not in str(e).lower() and 'duplicate' not in str(e).lower():
            print(f'Note: {str(e)[:100]}')

db.commit()

perm_after = db.query(RoleTemplatePermission).count()
print(f'Permissions inserted:')
print(f'  Total: {perm_after}')
print(f'  Expected: 294')
print(f'  Status: {"CORRECT" if perm_after == 294 else "NEEDS REVIEW"}')

# STEP 4: Verification
print('\nSTEP 4: Verification Queries')
print('-' * 70)

# Resources by module
print('\nResources by module:')
result = db.execute(text('''
    SELECT
        CASE
            WHEN name LIKE 'recruitment.%' THEN 'Recruitment'
            WHEN name LIKE 'workforce.%' THEN 'Workforce'
            WHEN name LIKE 'finance.%' THEN 'Finance'
            WHEN name LIKE 'admin.%' THEN 'Admin'
            WHEN name LIKE 'common.%' THEN 'Common'
            WHEN name LIKE 'sales.%' THEN 'Sales'
            WHEN name LIKE 'engagement.%' THEN 'Engagement'
            WHEN name LIKE 'executive.%' THEN 'Executive'
            WHEN name LIKE 'workflow.%' THEN 'Workflow'
            ELSE 'Other'
        END as module,
        COUNT(*) as count
    FROM resources
    WHERE tenant_id = 1
    GROUP BY module
    ORDER BY module
'''))

for row in result:
    print(f'  {row[0].ljust(15)}: {row[1]}')

# Permissions by role
print('\nPermissions by role:')
result = db.execute(text('''
    SELECT rt.name, COUNT(*) as count
    FROM role_template_permissions rtp
    JOIN role_templates rt ON rtp.role_template_id = rt.id
    GROUP BY rt.name
    ORDER BY count DESC
'''))

for row in result:
    print(f'  {row[0].ljust(25)}: {row[1]}')

# Data quality
print('\nData quality checks:')
result = db.execute(text('SELECT COUNT(*) FROM role_template_permissions WHERE resource_id NOT IN (SELECT id FROM resources)'))
orphaned_res = result.scalar() or 0
print(f'  Orphaned resource permissions: {orphaned_res} (Expected: 0)')

result = db.execute(text('SELECT COUNT(*) FROM role_template_permissions WHERE role_template_id NOT IN (SELECT id FROM role_templates)'))
orphaned_role = result.scalar() or 0
print(f'  Orphaned role permissions: {orphaned_role} (Expected: 0)')

result = db.execute(text('SELECT COUNT(*) FROM resources WHERE tenant_id = 1'))
total_res = result.scalar() or 0
result = db.execute(text('SELECT COUNT(DISTINCT name) FROM resources WHERE tenant_id = 1'))
unique_res = result.scalar() or 0
duplicates = total_res - unique_res
print(f'  Duplicate resources: {duplicates} (Expected: 0)')

# Final status
print('\n' + '='*70)
print('PHASE 1 RE-SEEDING STATUS')
print('='*70)

success = (res_after == 175 and perm_after == 294 and duplicates == 0 and
           orphaned_res == 0 and orphaned_role == 0)

if success:
    print('\n[SUCCESS] PHASE 1 RE-SEEDING SUCCESSFUL')
    print('\nAll validation checks passed:')
    print('  [OK] 175 resources seeded')
    print('  [OK] 294 permissions seeded')
    print('  [OK] No duplicates found')
    print('  [OK] No orphaned data')
    print('  [OK] Ready for Phase 2')
else:
    print('\n[NEEDS REVIEW] PHASE 1 NEEDS REVIEW')
    if res_after != 175:
        print(f'  - Resource count: {res_after} (expected 175)')
    if perm_after != 294:
        print(f'  - Permission count: {perm_after} (expected 294)')
    if duplicates > 0:
        print(f'  - Duplicates found: {duplicates}')
    if orphaned_res > 0:
        print(f'  - Orphaned resource perms: {orphaned_res}')
    if orphaned_role > 0:
        print(f'  - Orphaned role perms: {orphaned_role}')

db.close()
sys.exit(0 if success else 1)
