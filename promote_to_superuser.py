import sqlite3

conn = sqlite3.connect('local_dev.sqlite3')
cursor = conn.cursor()

# Update the admin user to Super User role
cursor.execute("""
  UPDATE users
  SET UserRole = 'Super User'
  WHERE UserEmail = 'admin@blitzenx.com'
""")

conn.commit()

# Verify the update
cursor.execute("SELECT UserEmail, UserRole FROM users WHERE UserEmail = 'admin@blitzenx.com'")
row = cursor.fetchone()
if row:
    print(f"✓ Updated: {row[0]} → {row[1]}")
else:
    print("✗ User not found")

conn.close()
