import psycopg2
conn = psycopg2.connect('postgresql://postgres:123@localhost:5432/wros_dev')
cur = conn.cursor()

# Check superuser and admin users
cur.execute("SELECT \"UserID\", \"UserEmail\", role_template_id, tenant_id FROM app_schema.users WHERE \"UserEmail\" IN ('superuser@blitzenx.com', 'admin@blitzenx.com')")

rows = cur.fetchall()
for row in rows:
    print(f"User: {row[1]}, role_template_id={row[2]}, tenant_id={row[3]}")

cur.close()
conn.close()
