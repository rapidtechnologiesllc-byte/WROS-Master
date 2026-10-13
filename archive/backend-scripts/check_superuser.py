#!/usr/bin/env python3
from app.core.database import SessionLocal
from app.models.user import Users

db = SessionLocal()
superuser = db.query(Users).filter(Users.UserEmail == 'superuser@blitzenx.com').first()
if superuser:
    role_template_id = getattr(superuser, 'role_template_id', 'MISSING')
    tenant_id = getattr(superuser, 'tenant_id', 'MISSING')
    print(f'Superuser found: role_template_id={role_template_id}, tenant_id={tenant_id}')
else:
    print('Superuser NOT found in database')
db.close()
