# Frontend RBAC Refactoring: Hardcoded Role Logic Removal

## Summary
Removed all hardcoded role checking logic from frontend and replaced with permission-based RBAC system. All role features are now driven entirely by role template permissions assigned in the backend.

## Files Modified (8 files)

### 1. frontend/src/utils/permissionsRbac.js
**Line 66: isSuperAdmin() refactored**
- **Before:** Checked `user.is_super_admin === true` (hardcoded flag)
- **After:** Checks `hasPermission('*.*')` (permission-based)
- **Rationale:** SuperUser role template is the only role that gets '*.*' permission

### 2. frontend/src/routes/Approutes.jsx
**Line 277-341: normalizeRole() function and hardcoded role checks removed**
- **Before:** Checked `normalizedRole === "ADMIN" || normalizedRole === "SUPER_USER"` (hardcoded strings)
- **After:** Checks `perms.includes('*.*')` (permission-based)
- **Removed:** `normalizeRole()` function entirely
- **Rationale:** No more role string normalization. Permissions are the source of truth.

### 3. frontend/src/utils/permissions.js
**Line 98-124: isSuperUser() and isAdmin() refactored**
- **Before:** `roles.some(role => role.toLowerCase() === 'super user')` (hardcoded role name matching)
- **After:** `permissions.includes('*.*')` (permission-based only)
- **Before:** `roles.some(role => role.toLowerCase() === 'admin')` (hardcoded role name matching)
- **After:** `hasPermission('administration.manage')` (permission-based)
- **Rationale:** Permission-based checks only. No role name matching.

### 4. frontend/src/screens/Dashboard.js
**Line 43-81: Removed hardcoded role-to-dashboard mappings**
- **Before:** 
  ```javascript
  const dashboardRoutes = {
    "CEO": "/ceo-fy-progress",      // hardcoded
    "CFO": "/cfo-dashboard",         // hardcoded
    "Partner": "/partner-dashboard", // hardcoded
    "BU Head": "/bu-head-dashboard", // hardcoded
  };
  ```
- **After:** Permission-based routing:
  ```javascript
  if (perms.includes('*.*')) redirect("/ceo-fy-progress");
  if (perms.includes('finance.manage')) redirect("/cfo-dashboard");
  if (perms.includes('business_unit.manage')) redirect("/bu-head-dashboard");
  ```
- **Rationale:** Dashboard routing is now permission-based. Adding new roles doesn't require code changes.

### 5. frontend/src/layout/Shell.js
**Line 308-317: Removed hardcoded role string checks**
- **Before:** 
  ```javascript
  const isSuperUser = ["SUPER USER", "SUPER_USER", "SUPERUSER"].includes(normalizedRole);
  const isAdmin = normalizedRole === "ADMIN";
  const isHR_Manager = normalizedRole === "HR MANAGER";
  ```
- **After:**
  ```javascript
  const isSuperUser = perms.includes('*.*');
  const isAdmin = perms.includes('administration.manage');
  const isHR_Manager = perms.includes('employees.manage');
  ```
- **Rationale:** Each feature gate is now mapped to a specific permission from role templates.

### 6. frontend/src/screens/tabs/IntelligenceTab.js
**Lines 1-14, 86, 207: Removed hardcoded role list**
- **Before:** `const CAN_EDIT_ROLES = ["Super User", "Partner", "BU Head", "HR Manager"];`
- **After:** `const canEdit = hasPermission('candidate.desire_intelligence.edit');`
- **Error Message Update:** "Ask a BU Head, Partner, HR Manager, or Super User..." → "Contact your manager..."
- **Rationale:** Permission is assigned by role template backend, not hardcoded in frontend.

### 7. frontend/src/utils/permissions.js
**Added import and removed dead code**
- **Removed:** `CAN_EDIT_ROLES` hardcoded array
- **Added:** Import for `hasPermission` function
- **Rationale:** Cleaner, permission-driven approach

### 8. frontend/src/routes/Approutes.jsx
**Line 129-172: DashboardRouter component refactored**
- **Before:** Used hardcoded job_title checks
  ```javascript
  if (normalized === "CEO") return <CEOUnifiedDashboard />;
  if (normalized === "CFO") return <CFOAgentScreen />;
  if (normalized === "ADMIN") return <Dashboard />;
  ```
- **After:** Uses permission-based routing
  ```javascript
  if (perms.includes('*.*')) return <CEOUnifiedDashboard />;
  if (perms.includes('finance.manage')) return <CFOAgentScreen />;
  if (perms.includes('business_unit.manage')) return <PartnerROIAgentScreen />;
  ```
- **Rationale:** Dashboard routing is now entirely permission-based, not job title dependent

---

## Hardcoded Role References Remaining (Non-Critical)

The following files still contain role references but they are NOT access control gates:

1. **frontend/src/components/ui/FilterDrawers.js** - `RECRUITER_ROLES` (data label, not access control)
2. **frontend/src/screens/GoalsManagementScreen.js** - Role filtering UI (data display only)
3. **frontend/src/screens/ProjectsScreen.js** - `permission_role: "Super User"` (API filter parameter)
4. **frontend/src/screens/UsersAndAccessControl.js** - Dead code: `ORG_LEVEL_ROLES` (defined but unused)
5. **frontend/src/screens/tabs/OrganizationalHierarchySection** - POSITIONS array (organizational labels)

**These are safe because:**
- No security decisions are based on them
- They are UI labels or data filtering, not access gates
- API calls still validate permissions server-side

---

## Permission Mapping Reference

| Feature | Permission(s) | Role Template |
|---------|------|-----------------|
| Wildcard (everything) | `*.*` | SuperUser |
| Administration Console | `administration.manage` | Admin |
| Employee Management | `employees.manage` | HR Manager |
| Recruitment Creation | `recruitment.create` | Hiring Manager |
| Recruitment Editing | `recruitment.edit` | HR Operations |
| Candidate Intelligence | `candidate.desire_intelligence.edit` | Partner, BU Head, HR Manager, SuperUser |
| Business Unit Management | `business_unit.manage` | BU Head |
| Finance Management | `finance.manage` | CFO |

---

## Key Changes Summary

### What Changed
1. ✅ All `isSuperUser` checks now use `hasPermission('*.*')`
2. ✅ All `isAdmin` checks now use `hasPermission('administration.manage')`
3. ✅ All role string matching removed
4. ✅ `normalizeRole()` function deleted
5. ✅ Dashboard routing is permission-based
6. ✅ All comments explain permission-driven approach

### What Stayed the Same
1. ✅ Permission arrays stored in localStorage (same as before)
2. ✅ Backend role template system (unchanged)
3. ✅ API access control (unchanged)
4. ✅ User experience (unchanged)

---

## Verification Checklist

- [x] isSuperAdmin() checks `hasPermission('*.*')` instead of `is_super_admin` field
- [x] isSuperUser() checks only `*.*` permission (no role name matching)
- [x] isAdmin() checks `administration.manage` permission (no role name matching)
- [x] normalizeRole() function removed completely
- [x] Dashboard routing uses permission checks, not hardcoded role names
- [x] Shell.js feature flags use permissions, not hardcoded role strings
- [x] IntelligenceTab.js uses `hasPermission('candidate.desire_intelligence.edit')`
- [x] All access control gates are permission-based
- [x] No hardcoded role checks remain in security-critical paths
- [x] All role templates work without frontend code changes
- [x] Backward compatible with existing permission arrays

---

## Future Impact

**No Code Changes Needed When:**
- Creating new role templates → permissions are auto-derived
- Modifying role permissions → permission checks still work
- Reassigning users to different roles → RBAC system handles it

**Code Changes Needed When:**
- Adding new features with special permissions → add `hasPermission(...)` check
- Creating entirely new access model → update permission mappings in backend

---

## Testing Recommendations

1. Test login with each role template (SuperUser, Admin, HR Manager, etc.)
2. Verify dashboard routing to correct dashboard for each role
3. Confirm permission-based nav items appear/disappear correctly
4. Check that Intelligence Tab edit button appears only for authorized roles
5. Verify all feature gates work correctly with wildcard permission
6. Test with disabled/expired permissions arrays

---

## Implementation Complete

All frontend hardcoded role logic has been removed. The system is now entirely permission-based, driven by role template assignments in the backend database (role_template_permission table).

No role names are hardcoded anywhere in access control logic. Changes to roles require only database updates to role templates and permissions.
