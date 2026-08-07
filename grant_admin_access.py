import sqlite3
from datetime import datetime

conn = sqlite3.connect('local_dev.sqlite3')
cursor = conn.cursor()

# Get admin user
cursor.execute("SELECT UserID FROM users WHERE email = 'admin@blitzenx.com' LIMIT 1")
admin = cursor.fetchone()

if admin:
    admin_id = admin[0]
    print(f"Found admin user: {admin_id}")

    # Get Super User role
    cursor.execute("SELECT id FROM rbac_roles WHERE name = 'Super User'")
    role = cursor.fetchone()

    if role:
        role_id = role[0]
        print(f"Found Super User role: {role_id}")

        # Check if already assigned
        cursor.execute("SELECT 1 FROM rbac_user_roles WHERE user_id = ? AND role_id = ?", (admin_id, role_id))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO rbac_user_roles (user_id, role_id, assigned_at) VALUES (?, ?, ?)",
                          (admin_id, role_id, datetime.utcnow().isoformat()))
            conn.commit()
            print("✅ Admin now has Super User role (full access)")
        else:
            print("ℹ️ Admin already has Super User role")
    else:
        print("❌ Super User role not found")
else:
    print("❌ Admin user not found")

conn.close()
