import sqlite3

conn = sqlite3.connect('local_dev.sqlite3')
cursor = conn.cursor()

cursor.execute("""
  SELECT UserID, UserEmail, UserRole
  FROM users
  WHERE UserEmail = 'admin@blitzenx.com'
  ORDER BY UserID
""")

rows = cursor.fetchall()
print(f"Found {len(rows)} user(s) with email admin@blitzenx.com:\n")
for row in rows:
    print(f"  UserID: {row[0]}, Email: {row[1]}, Role: {row[2]}")

conn.close()
