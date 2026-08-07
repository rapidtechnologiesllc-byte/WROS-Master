import sqlite3
from app.core.security import get_password_hash
import uuid

conn = sqlite3.connect('local_dev.sqlite3')
cursor = conn.cursor()

# Create super user directly
user_id = f"U-ADMIN-{uuid.uuid4().hex[:8].upper()}"
email = "admin@blitzenx.com"
password = "Admin!2026"
name = "Admin User"
hashed_password = get_password_hash(password)

try:
    cursor.execute("""
        INSERT INTO users (UserID, UserEmail, UserPassword, UserName, UserRole, tenant_id, mfa_enabled)
        VALUES (?, ?, ?, ?, ?, 1, 0)
    """, (user_id, email, hashed_password, name, "Super User"))

    conn.commit()
    print(f"✓ Super User created: {email}")
    print(f"  Password: {password}")
    print(f"  User ID: {user_id}")
except Exception as e:
    print(f"✗ Error: {e}")
finally:
    conn.close()
