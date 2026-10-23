#!/usr/bin/env python3
from app.core.database import SessionLocal
from app.models.user import Users

db = SessionLocal()
users = db.query(Users).limit(5).all()
for user in users:
    role_template_id = getattr(user, 'role_template_id', 'MISSING')
    tenant_id = getattr(user, 'tenant_id', 'MISSING')
    print(f'UserID: {user.UserID}, Email: {user.UserEmail}, role_template_id: {role_template_id}, tenant_id: {tenant_id}')
db.close()
