import sqlite3

conn = sqlite3.connect('local_dev.sqlite3')
c = conn.cursor()

print("=== ALL TABLES ===")
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
for row in c.fetchall():
    print(row[0])

print("\n=== ADMIN USER ===")
c.execute("SELECT UserID, UserRole, UserEmail, role_id FROM users WHERE UserEmail = 'admin@blitzenx.com'")
admin = c.fetchone()
if admin:
    print(f"UserID: {admin[0]}")
    print(f"UserRole: {admin[1]}")
    print(f"UserEmail: {admin[2]}")
    print(f"role_id: {admin[3]}")

conn.close()
