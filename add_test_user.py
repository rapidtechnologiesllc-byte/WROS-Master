#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.user import Users
from app.core.security import get_password_hash

db = SessionLocal()

# Check existing users
users = db.query(Users).all()
print(f'Existing users: {len(users)}')
for u in users[:10]:
    print(f'  - {u.UserEmail} ({u.UserRole})')

# Add test admin user if not exists
email = "Admin@blitzenx.com"
existing = db.query(Users).filter(Users.UserEmail == email).first()

if existing:
    print(f'\nUser {email} already exists')
else:
    print(f'\nCreating test user {email}...')
    test_user = Users(
        UserID="admin_test_001",
        UserName="Admin Test",
        UserEmail=email,
        UserPassword=get_password_hash("Admin!123"),
        UserRole="Super User",
    )
    db.add(test_user)
    db.commit()
    print(f'✅ Created user {email} with password Admin!123')

db.close()
