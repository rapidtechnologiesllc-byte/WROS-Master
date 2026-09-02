import logging
import psycopg2

conn = psycopg2.connect(
    host="localhost", port=5432, user="app_user",
    password="P7kQmR9xL2wJnV5sT8pM", database="onboarding_prod"
)
conn.set_isolation_level(0)
c = conn.cursor()
c.execute("SET search_path TO app_schema")

print("CLEANING UP SUPER USER ROLE TEMPLATES")
print("=" * 70)

# Get all Super User role templates
c.execute("""
SELECT id, name FROM role_templates
WHERE name ILIKE 'super user'
ORDER BY id
""")

super_users = c.fetchall()
print(f"Found {len(super_users)} Super User role templates:")
for su_id, name in super_users:
    c.execute("SELECT COUNT(*) FROM role_template_permissions WHERE role_template_id = %s", (su_id,))
    count = c.fetchone()[0]
    print(f"  ID {su_id}: {name} ({count} permissions)")

# Keep the first one (ID 10) with most permissions
keep_id = super_users[0][0]

if len(super_users) > 1:
    delete_ids = [su_id for su_id, _ in super_users[1:]]

    print(f"\nKeeping Super User ID {keep_id}, deleting {len(delete_ids)} duplicates...")

    for delete_id in delete_ids:
        # Delete permissions for duplicate Super User
        c.execute("DELETE FROM role_template_permissions WHERE role_template_id = %s", (delete_id,))
        # Delete the duplicate role template
        c.execute("DELETE FROM role_templates WHERE id = %s", (delete_id,))
        print(f"  Deleted Super User ID {delete_id}")
else:
    print(f"\nOnly 1 Super User role template found (ID {keep_id})")

# Now ensure the remaining Super User has permissions for ALL resources
print(f"Ensuring Super User ID {keep_id} has permissions for all resources...")
c.execute("""
SELECT COUNT(*) FROM resources WHERE tenant_id = 1 AND enabled = true
""")
total_resources = c.fetchone()[0]

c.execute("""
SELECT COUNT(*) FROM role_template_permissions
WHERE role_template_id = %s
""", (keep_id,))
current_perms = c.fetchone()[0]

print(f"  Total resources: {total_resources}")
print(f"  Super User current permissions: {current_perms}")

if current_perms < total_resources:
    print(f"  Adding missing permissions...")
    c.execute("""
    INSERT INTO role_template_permissions
    (role_template_id, resource_id, can_view, can_create, can_edit, can_delete)
    SELECT %s, id, true, true, true, true
    FROM resources
    WHERE tenant_id = 1 AND enabled = true
    AND id NOT IN (
      SELECT resource_id FROM role_template_permissions
      WHERE role_template_id = %s
    )
    """, (keep_id, keep_id))

    c.execute("""
    SELECT COUNT(*) FROM role_template_permissions
    WHERE role_template_id = %s
    """, (keep_id,))
    new_count = c.fetchone()[0]
    print(f"  Super User now has {new_count} permissions")

print("\n" + "=" * 70)
print("CLEANUP COMPLETE!")
print("=" * 70)

conn.close()
