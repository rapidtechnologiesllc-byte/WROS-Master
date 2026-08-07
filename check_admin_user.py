import sqlite3

conn = sqlite3.connect('local_dev.sqlite3')
cursor = conn.cursor()

cursor.execute("""
  SELECT UserID, UserEmail, UserRole, UserName, role_id
  FROM users
  WHERE UserEmail = 'admin@blitzenx.com'
""")

row = cursor.fetchone()
if row:
    print(f"Admin user in database:")
    print(f"  UserID: {row[0]}")
    print(f"  UserEmail: {row[1]}")
    print(f"  UserRole: {row[2]}")
    print(f"  UserName: {row[3]}")
    print(f"  role_id: {row[4]}")
else:
    print("Admin user not found in database")

conn.close()
