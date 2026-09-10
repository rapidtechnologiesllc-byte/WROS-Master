# Permission Issue Investigation Guide

**Date:** 2026-09-09  
**Status:** BLOCKER - Admin user cannot see candidates  
**Root Cause:** Role template configuration or permission checks

---

## 🚨 Problem Statement

**Observed:** Admin User logged in, but cannot see 10 candidates that exist in database
- Dashboard shows "Candidates in Pipeline: 0"
- No candidates appear in search
- Navigation error: "Internal server error"

**Expected:** Admin should see all candidates (org-level access)

---

## 📋 Investigation Checklist

### 1. Admin User Configuration in Database

**Query to run:**
```sql
SELECT 
    u.UserID,
    u.UserEmail,
    u.UserName,
    u.role_template_id,
    u.business_unit_id,
    rt.name as role_name,
    rt.org_level_access
FROM users u
LEFT JOIN role_templates rt ON u.role_template_id = rt.id
WHERE u.UserEmail = 'admin@test.com' OR u.UserEmail LIKE '%admin%'
LIMIT 5;
```

**What to check:**
- [ ] Is `role_template_id` set? (Not NULL)
- [ ] Does the role_template exist? (Check `name` column)
- [ ] Is `org_level_access` = TRUE? (Should be for admin)
- [ ] What is `business_unit_id`? (Should be NULL for org-level)

### 2. Role Template Permissions

**Query to run:**
```sql
SELECT 
    rt.id,
    rt.name,
    rt.org_level_access,
    rt.enabled,
    COUNT(rtp.id) as permission_count,
    STRING_AGG(DISTINCT r.name || '.' || 
        CASE 
            WHEN rtp.can_view THEN 'view'
            WHEN rtp.can_create THEN 'create'
            WHEN rtp.can_edit THEN 'edit'
            WHEN rtp.can_delete THEN 'delete'
        END, ',') as permissions
FROM role_templates rt
LEFT JOIN role_template_permissions rtp ON rt.id = rtp.role_template_id
LEFT JOIN resources r ON rtp.resource_id = r.id
WHERE rt.name IN ('Admin', 'Super User', 'CEO')
GROUP BY rt.id, rt.name, rt.org_level_access, rt.enabled
ORDER BY rt.id;
```

**What to check:**
- [ ] Does the role have `recruitment.view` permission?
- [ ] Is `org_level_access` = TRUE?
- [ ] Is `enabled` = TRUE?
- [ ] Are there ANY permissions assigned?

### 3. Candidate Query Endpoint Permissions

**File:** `backend/app/api/v1/endpoints/candidates/crud.py` (line ~214)

**Check:**
```python
@router.get(
    "/all",
    response_model=AllCandidatesResponse,
    dependencies=[Depends(require_resource_permission("recruitment", "view"))]  # ← THIS LINE
)
def get_all_candidates(db: Session = Depends(get_db), user = Depends(get_current_user)):
```

**Issue:** This endpoint requires `recruitment.view` permission!

**Questions:**
- [ ] Does the admin's role_template have this permission?
- [ ] Is the permission check working correctly?
- [ ] Should admin automatically have this permission?

### 4. Backend Permission Service

**File:** `backend/app/core/permission_registry.py`

**Check:**
```python
class Permissions:
    RECRUITMENT_VIEW = ("recruitment", "view")
    # ...
```

**Questions:**
- [ ] Is `RECRUITMENT_VIEW` defined?
- [ ] Is it correctly formatted?

### 5. Current User Dependency

**File:** `backend/app/core/dependencies.py`

**Check:**
- [ ] Is `get_current_user()` returning the admin user correctly?
- [ ] Are user permissions being loaded correctly?
- [ ] Is `role_template` being eager-loaded with the user?

---

## 🔧 Likely Fixes (in priority order)

### Fix 1: Admin Role Template Missing Permissions
**If:** Admin's role_template has no permissions assigned

**Solution:**
```sql
INSERT INTO role_template_permissions (role_template_id, resource_id, can_view, can_create, can_edit, can_delete)
SELECT 
    rt.id,
    r.id,
    TRUE,
    TRUE,
    TRUE,
    TRUE
FROM role_templates rt
CROSS JOIN resources r
WHERE rt.name = 'Super User' OR rt.name = 'Admin'
AND rt.enabled = TRUE
AND NOT EXISTS (
    SELECT 1 FROM role_template_permissions rtp 
    WHERE rtp.role_template_id = rt.id 
    AND rtp.resource_id = r.id
);
```

### Fix 2: Admin User Not Assigned to Correct Role
**If:** Admin user has wrong role_template_id

**Solution:**
```sql
UPDATE users
SET role_template_id = (SELECT id FROM role_templates WHERE name = 'Super User' AND enabled = TRUE)
WHERE UserEmail LIKE '%admin%'
AND role_template_id IS NULL OR role_template_id IN (
    SELECT id FROM role_templates WHERE enabled = FALSE
);
```

### Fix 3: org_level_access Not Set
**If:** Admin role_template exists but org_level_access = FALSE

**Solution:**
```sql
UPDATE role_templates
SET org_level_access = TRUE
WHERE name IN ('Super User', 'Admin', 'CEO')
AND is_system = TRUE;
```

### Fix 4: Remove Permission Dependency
**If:** Permission checks are too strict for now

**Temporary Fix** (for testing):
```python
# Comment out the permission check temporarily
@router.get(
    "/all",
    response_model=AllCandidatesResponse,
    # dependencies=[Depends(require_resource_permission("recruitment", "view"))]  # DISABLED
)
def get_all_candidates(db: Session = Depends(get_db), user = Depends(get_current_user)):
```

---

## ✅ Testing the Fix

After applying a fix:

1. **Restart backend**
   ```bash
   # Kill existing process and restart
   python -m uvicorn app.main:app --port 8000
   ```

2. **Login and test**
   - Navigate to http://localhost:3000
   - Login as admin
   - Check if candidates appear in dashboard

3. **API test**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/candidates/all
   ```

---

## 📊 Debugging Commands

### Check admin user details
```bash
# Using psql if connected to database
SELECT * FROM users WHERE UserEmail LIKE '%admin%';
SELECT * FROM role_templates;
SELECT * FROM role_template_permissions LIMIT 10;
```

### Check backend logs for permission errors
```bash
# Look for "Permission denied" or "recruitment.view" in logs
grep -i "permission\|recruitment" backend.log
```

### Verify permission service is working
```python
# Test in Python shell
from app.core.permission_helper import PermissionHelper
from app.models import Users

user = db.query(Users).filter(Users.UserEmail == 'admin@test.com').first()
permissions = PermissionHelper.get_user_permissions(user)
print(permissions)  # Should show all permissions for org-level user
```

---

## 🎯 Priority Fix Path

1. **IMMEDIATE:** Check if admin has role_template assigned
2. **IMMEDIATE:** Check if role_template has org_level_access=TRUE  
3. **IMMEDIATE:** Check if role_template has recruitment permissions
4. **FALLBACK:** Temporarily remove permission check to verify BU scoping works
5. **THEN:** Re-enable permission checks after confirming role configuration

---

## 📝 Next Steps

1. Run the SQL queries above to investigate
2. Apply appropriate fix based on findings
3. Restart backend
4. Test candidate visibility
5. **Create GitHub issue:** "Fix: Admin user role template permissions not configured"

---

**Related:**
- BU Isolation Fix: d5c6f1fc
- Permission Registry: backend/app/core/permission_registry.py
- Permission Helper: backend/app/core/permission_helper.py
- Permission Dependency: backend/app/core/dependencies.py require_resource_permission()
