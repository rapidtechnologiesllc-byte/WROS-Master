#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.user import Users
from app.core.security import get_password_hash

db = SessionLocal()

# Get the Admin user
email = "Admin@blitzenx.com"
user = db.query(Users).filter(Users.UserEmail == email).first()

if not user:
    print(f'User {email} not found')
else:
    print(f'Found user: {user.UserEmail} ({user.UserRole})')
    print(f'Old password hash: {user.UserPassword}')

    # Update password
    new_password = "Admin!123"
    user.UserPassword = get_password_hash(new_password)

    print(f'New password hash: {user.UserPassword}')

    db.commit()
    print(f'✅ Password updated for {email}')

    # Verify it works
    from app.core.database import authenticate_user
    result = authenticate_user(db, email, new_password)
    if result:
        print(f'✅ Verification successful - user can login')
    else:
        print(f'❌ Verification failed')

db.close()
