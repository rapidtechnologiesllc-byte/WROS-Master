from app.core.database import engine, SessionLocal
from app.models.user import Users
from app.models.partner import Partner
from app.models.delivery_center import DeliveryCenter
from app.models.base import Base
from app.core.security_local import get_password_hash
import uuid
from datetime import datetime

# Create tables
print("Creating tables...")
Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    # Create test user
    existing = db.query(Users).filter(Users.UserEmail == "admin@blitzenx.com").first()
    if not existing:
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
        print("✓ Test user created: admin@blitzenx.com / Admin!123")
    else:
        print("✓ Test user already exists")

except Exception as e:
    print(f"ERROR creating user: {e}")
    db.rollback()
finally:
    db.close()

print("Database setup complete!")
