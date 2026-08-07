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
print(f"Super User role ID: {super_user_role_id}\n")

# Get all permissions
cursor.execute("SELECT id, name FROM permissions")
permissions = cursor.fetchall()
print(f"Found {len(permissions)} permissions:")

# Grant each permission to Super User role
granted = 0
for perm_id, perm_name in permissions:
    # Check if already granted
    cursor.execute("""
        SELECT 1 FROM role_permissions
        WHERE role_id = ? AND permission_id = ?
    """, (super_user_role_id, perm_id))

    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES (?, ?)
        """, (super_user_role_id, perm_id))
        granted += 1
        print(f"  ✓ {perm_name}")
    else:
        print(f"  - {perm_name} (already granted)")

conn.commit()
print(f"\n✓ Granted {granted} new permissions to Super User role")
conn.close()
