import sqlite3

conn = sqlite3.connect('local_dev.sqlite3')
cursor = conn.cursor()

# Get the Super User role ID
cursor.execute("SELECT id FROM roles WHERE name = 'Super User'")
role_row = cursor.fetchone()
if not role_row:
    print("✗ Super User role not found")
    conn.close()
    exit(1)

super_user_role_id = role_row[0]

# Update admin user to have the role_id relationship
cursor.execute("""
    UPDATE users
    SET role_id = ?
    WHERE UserEmail = 'admin@blitzenx.com'
""", (super_user_role_id,))

conn.commit()

# Verify
cursor.execute("SELECT UserEmail, UserRole, role_id FROM users WHERE UserEmail = 'admin@blitzenx.com'")
row = cursor.fetchone()
if row:
    print(f"✓ Updated admin@blitzenx.com:")
    print(f"  UserRole: {row[1]}")
    print(f"  role_id: {row[2]}")
else:
    print("✗ User not found")

conn.close()
