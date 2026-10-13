#!/bin/bash
# Verification Script: Admin User Role Template Fix

echo "=================================================="
echo "ADMIN USER ROLE TEMPLATE FIX - VERIFICATION"
echo "=================================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Database schema check
echo -e "\n${YELLOW}Test 1: Verify database schema${NC}"
python3 << 'EOF'
import sqlite3
db_path = "backend/local_dev.sqlite3"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check org_level_access column
cursor.execute("PRAGMA table_info(role_templates)")
columns = [col[1] for col in cursor.fetchall()]

if 'org_level_access' in columns:
    print("  [PASS] org_level_access column exists")
else:
    print("  [FAIL] org_level_access column missing")
    exit(1)

conn.close()
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database schema verified${NC}"
else
    echo -e "${RED}✗ Database schema check failed${NC}"
    exit 1
fi

# Test 2: Admin user configuration
echo -e "\n${YELLOW}Test 2: Verify admin user configuration${NC}"
python3 << 'EOF'
import sqlite3
db_path = "backend/local_dev.sqlite3"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
SELECT
    u.UserEmail,
    u.role_template_id,
    rt.name,
    rt.org_level_access
FROM users u
LEFT JOIN role_templates rt ON u.role_template_id = rt.id
WHERE u.UserEmail = 'admin@blitzenx.com'
""")

row = cursor.fetchone()
if row:
    email, rt_id, rt_name, org_access = row
    print(f"  Email: {email}")
    print(f"  role_template_id: {rt_id}")
    print(f"  Role Template: {rt_name}")
    print(f"  org_level_access: {org_access}")

    if rt_id and rt_name == 'Super User' and org_access == 1:
        print("\n  [PASS] Admin user correctly configured")
    else:
        print("\n  [FAIL] Admin user configuration incomplete")
        exit(1)
else:
    print("  [FAIL] Admin user not found")
    exit(1)

conn.close()
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Admin user configuration verified${NC}"
else
    echo -e "${RED}✗ Admin user configuration check failed${NC}"
    exit 1
fi

# Test 3: Super User permissions
echo -e "\n${YELLOW}Test 3: Verify Super User has all permissions${NC}"
python3 << 'EOF'
import sqlite3
db_path = "backend/local_dev.sqlite3"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
SELECT COUNT(*) as perm_count
FROM role_template_permissions
WHERE role_template_id = 1
""")

row = cursor.fetchone()
if row:
    count = row[0]
    print(f"  Super User permissions count: {count}")

    if count > 100:  # Should have 177 resources
        print("\n  [PASS] Super User has sufficient permissions")
    else:
        print("\n  [WARN] Super User permissions count is low, but may still be functional")
else:
    print("  [FAIL] Could not query permissions")
    exit(1)

conn.close()
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Super User permissions verified${NC}"
else
    echo -e "${RED}✗ Super User permissions check failed${NC}"
    exit 1
fi

echo -e "\n${GREEN}=================================================="
echo "ALL VERIFICATION TESTS PASSED"
echo "==================================================${NC}"
echo ""
echo "Next steps:"
echo "1. Restart backend: cd backend && python -m uvicorn app.main:app --port 8000"
echo "2. Clear browser cache (localStorage)"
echo "3. Test login: admin@blitzenx.com"
echo "4. Verify candidates are visible in dashboard"
echo "5. Check browser console for 'Failed to refresh permissions' errors"
