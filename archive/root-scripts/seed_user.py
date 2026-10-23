from app.core.database import SessionLocal
from app.models.user import Users
from app.core.security_local import get_password_hash
import uuid
from datetime import datetime

db = SessionLocal()
try:
    existing = db.query(Users).filter(Users.UserEmail == "admin@blitzenx.com").first()
    if existing:
        print("User already exists")
    else:
        user = Users(
            UserID=str(uuid.uuid4()),
            UserEmail="admin@blitzenx.com",
            UserPassword=get_password_hash("Admin!123"),
            UserName="Admin User",
            UserRole="Admin",
            job_title="Admin",
            tenant_id=1,
            mfa_enabled=False,
            digest_enabled=True,
            thunder_enabled=True,
            CreatedAt=datetime.utcnow()
        )
        db.add(user)
        db.commit()
        print("SUCCESS: Test user created")
except Exception as e:
    print(f"ERROR: {e}")
    db.rollback()
finally:
    db.close()
