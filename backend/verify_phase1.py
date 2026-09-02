#!/usr/bin/env python3
import logging
"""Phase 1 Verification Script"""

from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

print('='*60)
print('PHASE 1 VERIFICATION REPORT')
print('='*60)

# Query 1: Total resources
result = db.execute(text('SELECT COUNT(id) FROM resources WHERE tenant_id = 1'))
total_res = result.scalar()
print(f'\n1. Total resources: {total_res}')

# Query 2: Resources by module prefix
print(f'\n2. Resources by module:')
for prefix in ['recruitment', 'finance', 'admin', 'common', 'workforce', 'engagement', 'executive', 'sales', 'workflow']:
    result = db.execute(text(f"SELECT COUNT(id) FROM resources WHERE name LIKE '{prefix}.%' AND tenant_id = 1"))
    count = result.scalar() or 0
    print(f'   {prefix.ljust(12)}: {count}')

# Query 3: Check for duplicates
result = db.execute(text('SELECT COUNT(id) FROM resources WHERE tenant_id = 1'))
total_rows = result.scalar()
result = db.execute(text('SELECT COUNT(DISTINCT name) FROM resources WHERE tenant_id = 1'))
unique_names = result.scalar()
duplicates = total_rows - unique_names
print(f'\n3. Duplicate check:')
print(f'   Total resource rows: {total_rows}')
print(f'   Unique resource names: {unique_names}')
print(f'   Duplicates found: {duplicates}')

# Query 4: Total permissions
result = db.execute(text('SELECT COUNT(id) FROM role_template_permissions'))
total_perms = result.scalar()
print(f'\n4. Total permissions: {total_perms}')

# Query 5: Permissions by role
print(f'\n5. Permissions by role:')
result = db.execute(text('''
    SELECT rt.name, COUNT(rtp.id) as count
    FROM role_template_permissions rtp
    JOIN role_templates rt ON rtp.role_template_id = rt.id
    GROUP BY rt.name
    ORDER BY count DESC
'''))
for row in result:
    print(f'   {row[0].ljust(25)}: {row[1]}')

# Query 6: Data quality checks
print(f'\n6. Data quality checks:')
result = db.execute(text('SELECT COUNT(*) FROM role_template_permissions WHERE resource_id NOT IN (SELECT id FROM resources)'))
orphaned_res = result.scalar()
print(f'   Orphaned resource perms: {orphaned_res} (Expected: 0)')

result = db.execute(text('SELECT COUNT(*) FROM role_template_permissions WHERE role_template_id NOT IN (SELECT id FROM role_templates)'))
orphaned_role = result.scalar()
print(f'   Orphaned role perms: {orphaned_role} (Expected: 0)')

# Final status
print(f'\n' + '='*60)
print('PHASE 1 STATUS')
print('='*60)
if total_res >= 175 and duplicates == 0 and orphaned_res == 0 and orphaned_role == 0:
    print('✅ SEEDING SUCCESSFUL')
else:
    print('⚠️  NEEDS REVIEW')
    if total_res < 175:
        print(f'   - Resource count low: {total_res} (expected: 175)')
    if duplicates > 0:
        print(f'   - Found duplicates: {duplicates}')
    if orphaned_res > 0:
        print(f'   - Found orphaned resource permissions: {orphaned_res}')
    if orphaned_role > 0:
        print(f'   - Found orphaned role permissions: {orphaned_role}')
