import psycopg2
conn = psycopg2.connect('postgresql://postgres:123@localhost:5432/wros_dev')
cur = conn.cursor()

# Count all candidates
cur.execute("SELECT COUNT(*) as total FROM app_schema.candidates")
total = cur.fetchone()[0]
print(f"Total candidates in database: {total}")

# Count by business unit
cur.execute("""
SELECT associated_bu_id, COUNT(*) as count
FROM app_schema.candidates
WHERE associated_bu_id IS NOT NULL
GROUP BY associated_bu_id
ORDER BY count DESC
""")
print("\nCandidates by Business Unit:")
for bu_id, count in cur.fetchall():
    print(f"  BU {bu_id}: {count} candidates")

# Check what BUs exist
cur.execute("SELECT id, name FROM app_schema.business_units ORDER BY id")
print("\nBusiness Units in system:")
for bu_id, bu_name in cur.fetchall():
    print(f"  BU {bu_id}: {bu_name}")

cur.close()
conn.close()
