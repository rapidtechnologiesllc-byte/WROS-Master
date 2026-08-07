import sqlite3

conn = sqlite3.connect('local_dev.sqlite3')
c = conn.cursor()

print("=== RBAC ROLES ===")
c.execute('SELECT id, name FROM rbac_roles')
for row in c.fetchall():
    print(row)

print("\n=== ADMIN USER ===")
c.execute("SELECT UserID, UserRole, UserEmail, role_id FROM users WHERE UserEmail = 'admin@blitzenx.com'")
admin = c.fetchone()
if admin:
    print(f"UserID: {admin[0]}")
    print(f"UserRole: {admin[1]}")
    print(f"UserEmail: {admin[2]}")
    print(f"role_id: {admin[3]}")
else:
    print("Admin not found")

conn.close()
