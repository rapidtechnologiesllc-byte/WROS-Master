# Deploy Navigation Fix - BX-HRMS-NAV-006

**Issue:** `/users` navigation item routes to non-existent route  
**Status:** Backend fix applied - Commit 15bdf20b  
**Required Action:** Run database seed to update resources

---

## The Problem

❌ **Current (Broken):**
```
Backend navigation.py returns:
  - "users" resource with route_path="/users"
Frontend has:
  - No route for /users
Result:
  - Clicking "Users" in Admin menu → Blank page (404)
```

✅ **Fixed:**
```
Backend navigation.py returns:
  - "users-access-control" resource with route_path="/admin/users-access-control"
Frontend has:
  - Route at /admin/users-access-control
Result:
  - Clicking "Users & Access Control" → Loads Users & Access Control screen
```

---

## Fix Applied

**File Changed:** `backend/app/seeds/init_resources.py`
- Line 18: `"users"` → `"users-access-control"`
- Line 51: Added `"users-access-control": "admin/users-access-control"`

**Commit:** 15bdf20b

---

## HOW TO DEPLOY

### Step 1: Stop Backend
```bash
# Stop the running backend (Ctrl+C in terminal or kill port 8080)
```

### Step 2: Run Database Seed
```bash
cd backend
python -m app.seeds.init_resources
```

**Expected Output:**
```
Creating modules and resources for tenant_id=1...
  ✓ Module: Admin already exists
    + Resource: users-access-control → admin/users-access-control
    ✓ Resource: roles-permissions
    ✓ Resource: organization
    ✓ Resource: admin-settings
    [removing old 'users' resource]
...
SUCCESS: Resource Initialization Complete!
```

### Step 3: Start Backend Again
```bash
# In backend directory, run uvicorn or your start command
python -m uvicorn app.main:app --reload --port 8080
```

### Step 4: Clear Browser Cache & Refresh
```bash
# In browser:
1. Press Ctrl+Shift+Delete (Windows) or Cmd+Shift+Delete (Mac)
2. Clear browsing data / cache
3. Refresh page (Ctrl+R or Cmd+R)
```

### Step 5: Test the Fix
```
1. Navigate to http://localhost:3000
2. Expand "Admin" module
3. Click "Users & Access Control" (no longer shows separate "Users" item)
4. Should load successfully at /admin/users-access-control
```

---

## Verification Checklist

After deployment:

- [ ] Backend is running on port 8080
- [ ] Seed script executed successfully
- [ ] Browser cache cleared
- [ ] Can access http://localhost:3000
- [ ] Admin module expands
- [ ] No "Users" item showing (it's been consolidated)
- [ ] "Users & Access Control" item appears
- [ ] Clicking "Users & Access Control" loads the screen
- [ ] No blank page or 404 error

---

## Troubleshooting

**Issue: Still seeing "Users" in Admin menu**
- Solution: Clear database and re-run seed
- Command: `python -m app.seeds.init_resources`
- Then restart backend and refresh browser

**Issue: "users-access-control" doesn't load**
- Check: Is route at `/admin/users-access-control` in Approutes.jsx?
- Check: Does UsersAndAccessControl component exist?
- Check: Any console errors in browser developer tools?

**Issue: Seed script fails**
- Check: Is backend running? (It shouldn't be, stop it first)
- Check: Is database connection string set correctly?
- Check: Are you in the `backend` directory?

---

## Related Issues Fixed

- ✅ BX-HRMS-NAV-006: Hardcoded Users Routes to /users
- 🔄 BX-HRMS-NAV-007: Admin Sub-Items Consolidation (partial - resources updated, UI needs verification)

---

## What Changed in Database

**Before Seed Run:**
```
resources table:
  id=10, name='users', route_path='/users', module_id=X
```

**After Seed Run:**
```
resources table:
  id=??, name='users_access_control', route_path='admin/users-access-control', module_id=X
```

---

## Next Steps

1. ✅ **Backend Fix Applied** (Commit 15bdf20b)
2. ⏳ **Run Database Seed** (You need to do this)
3. ⏳ **Verify Fix Works** (Click Users & Access Control in Admin)
4. ⏳ **Test All Admin Tabs** (Users, Business Units, Role Templates, etc.)
5. ⏳ **Update Testing Checklist** (Mark as ✅ Working)
6. ⏳ **Create GitHub Issue** (Mark BX-HRMS-NAV-006 as RESOLVED)

---

## Questions?

If the fix doesn't work:
1. Check browser console for errors (F12 → Console tab)
2. Check backend logs for errors
3. Verify seed script ran successfully
4. Clear browser cache again and refresh
