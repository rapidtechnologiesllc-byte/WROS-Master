from app.core.database import SessionLocal
from app.models.user import Users
from app.models.role_template import RoleTemplate

db = SessionLocal()
try:
    # Get Super Admin role
    super_admin = db.query(RoleTemplate).filter(RoleTemplate.name == "Super Admin").first()
    if super_admin:
        print(f"Super Admin role found: id={super_admin.id}")
    else:
        print("Super Admin role not found!")

    # Get superuser
    superuser = db.query(Users).filter(Users.UserEmail == "superuser@blitzenx.com").first()
    if superuser:
        print(f"Superuser found: tenant_id={superuser.tenant_id}, role_template_id={superuser.role_template_id}")

        # Update with correct values
        if not superuser.tenant_id or superuser.tenant_id != 1:
            superuser.tenant_id = 1
            print("Updated tenant_id to 1")

        if super_admin and (not superuser.role_template_id or superuser.role_template_id != super_admin.id):
            superuser.role_template_id = super_admin.id
            print(f"Updated role_template_id to {super_admin.id}")

        db.commit()
        print("Superuser updated successfully")
    else:
        print("Superuser not found!")

finally:
    db.close()
