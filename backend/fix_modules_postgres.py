import psycopg2

# PostgreSQL connection
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    user="app_user",
    password="P7kQmR9xL2wJnV5sT8pM",
    database="onboarding_prod"
)
conn.set_isolation_level(0)  # Autocommit mode
c = conn.cursor()

# Set search path to app_schema
c.execute("SET search_path TO app_schema")

# Update module display names
print("Updating module names in PostgreSQL...")
c.execute("UPDATE modules SET display_name = 'Recruitment' WHERE display_name = 'Recruitment Management'")
print(f"  Updated Recruitment: {c.rowcount} rows")

c.execute("UPDATE modules SET display_name = 'Finance' WHERE display_name = 'Finance & Revenue'")
print(f"  Updated Finance: {c.rowcount} rows")

c.execute("UPDATE modules SET display_name = 'Workforce' WHERE display_name = 'Workforce & Employees'")
print(f"  Updated Workforce: {c.rowcount} rows")

# Verify
print("\nMODULES AFTER CORRECTION:")
c.execute('SELECT id, display_name FROM modules ORDER BY id')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}')

conn.close()
print("\nDone!")
