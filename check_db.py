import sqlite3

conn = sqlite3.connect('local_dev.sqlite3')
cursor = conn.cursor()

# Check users
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
if cursor.fetchone():
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    print(f'Users table: {count} rows')

    cursor.execute('SELECT UserEmail, UserID, UserRole FROM users LIMIT 10')
    for row in cursor.fetchall():
        print(f'  - {row[0]} ({row[1]}) - {row[2]}')
else:
    print('Users table NOT FOUND')

conn.close()
