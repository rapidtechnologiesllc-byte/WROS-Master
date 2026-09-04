import logging
import sqlite3

conn = sqlite3.connect('local_dev.sqlite3')
c = conn.cursor()

# Update module names
c.execute("UPDATE modules SET display_name = 'Recruitment' WHERE display_name = 'Recruitment Management'")
c.execute("UPDATE modules SET display_name = 'Finance' WHERE display_name = 'Finance & Revenue'")
c.execute("UPDATE modules SET display_name = 'Workforce' WHERE display_name = 'Workforce & Employees'")

conn.commit()

print("MODULES AFTER CORRECTION:")
c.execute('SELECT id, display_name FROM modules ORDER BY id')
for row in c.fetchall():
    print(f'{row[0]}: {row[1]}')

conn.close()
