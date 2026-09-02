import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import logging
from sqlalchemy.orm import sessionmaker

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    result = db.execute(text('SELECT "UserEmail", "UserPassword", "UserRole" FROM app_schema.users WHERE "UserEmail" = :email'),
                       {"email": "recruiter@test.com"}).first()
    if result:
        email, password_hash, role = result
        print(f"✅ Found user: {email}")
        print(f"   Role: {role}")
        print(f"   Password hash: {password_hash}")
        print(f"   Hash length: {len(password_hash)}")
    else:
        print("❌ User not found")
except Exception as e:
   logger.error(f"Error: {str(e)}", exc_info=True)
    logger.error(f"Error: {str(e)}", exc_info=True)
    print(f"❌ Error: {e}")
finally:
    db.close()
