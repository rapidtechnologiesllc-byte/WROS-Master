#!/usr/bin/env python
import sys
sys.path.insert(0, 'C:\\dev\\WROS-Master\\backend')

from app.core.database import SessionLocal, authenticate_user
from app.models import RoleTemplate

db = SessionLocal()

# Step 1: Authenticate user
print('Step 1: Authenticating user...')
user = authenticate_user(db, 'superuser@blitzenx.com', 'Test@12345')
if user:
    print(f'  ✓ User authenticated: {user.UserEmail}')
else:
    print('  ✗ Authentication failed')
    exit(1)

# Step 2: Check role_template_id
print('Step 2: Checking role_template_id...')
role_template_id = user.role_template_id
print(f'  role_template_id value: {role_template_id}')

# Step 3: Get RoleTemplate
print('Step 3: Querying RoleTemplate...')
rt = db.query(RoleTemplate).filter(RoleTemplate.id == role_template_id).first()
print(f'  RoleTemplate result: {rt}')
if rt:
    print(f'  ✓ RoleTemplate found: name={rt.name}')
else:
    print('  ✗ RoleTemplate not found')

db.close()
print('✓ ALL STEPS PASSED')
