import sqlite3
from app.core.security import verify_password, get_password_hash

conn = sqlite3.connect('local_dev.sqlite3')
cursor = conn.cursor()

# Get the CEO user
cursor.execute("SELECT UserEmail, UserPassword FROM users WHERE UserEmail = 'am@blitzenx.com'")
row = cursor.fetchone()
if row:
    email, stored_hash = row
    print(f"User: {email}")
    print(f"Stored hash: {stored_hash[:50]}...")

    # Test the password
    test_password = "LocalDev!2026"
    is_valid = verify_password(test_password, stored_hash)
    print(f"Password verification: {is_valid}")

    if not is_valid:
        # Try to re-hash and compare
        print("\nDebug: Creating new hash and comparing...")
        new_hash = get_password_hash(test_password)
        print(f"New hash: {new_hash[:50]}...")
        print(f"Match: {new_hash == stored_hash}")
else:
    print("User not found!")

conn.close()
