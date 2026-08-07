import sqlite3

conn = sqlite3.connect('local_dev.sqlite3')
cursor = conn.cursor()

cursor.execute("SELECT UserEmail, UserRole FROM users ORDER BY UserEmail")
rows = cursor.fetchall()
print(f"Total users: {len(rows)}\n")
for email, role in rows:
    print(f"  {email} → {role}")

conn.close()
