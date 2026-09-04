#!/usr/bin/env python3
"""Grant Recruiter role to a user to enable candidate creation"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal
from app.models.user import Users
from app.models.role_template import RoleTemplate

db = SessionLocal()

# Get the Super User (you're logged in as this)
user = db.query(Users).filter(Users.UserEmail == "superuser@blitzenx.com").first()

if not user:
    print("Super User not found. Check your login email.")
    sys.exit(1)

# Get Recruiter role template
recruiter_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Recruiter").first()

if not recruiter_role:
    print("Recruiter role not found. Run init_role_permissions_proper.py first.")
    sys.exit(1)

# Assign Recruiter role to user
user.role_template_id = recruiter_role.id
db.commit()

print(f"[OK] Granted Recruiter role to {user.UserEmail}")
print(f"[OK] You can now create candidates!")
print(f"\nRestart the frontend and the 'Add New Candidate' button will appear.")
