# GitHub Issues to Create - Navigation & Route Defects

**Date:** 2026-08-23  
**Sprint:** Navigation Cleanup & Defect Tracking  
**Issue Template:** Use for creating issues in GitHub project dashboard

---

## CRITICAL DEFECTS (Blocking Personal Dashboard)

### BX-HRMS-NAV-001: Dashboard Route Not Working
**Labels:** `bug`, `navigation`, `critical`  
**Priority:** P0 - Critical (Blocks all users)  
**Assignee:** Backend Team

**Description:**
Dashboard at `/` is not loading. The navigation item exists but clicking it or navigating directly to the route returns blank page or error.

**Expected Behavior:**
- Users can navigate to `/` (root dashboard)
- Dashboard displays with quick actions, open jobs count, candidates in pipeline, etc.

**Actual Behavior:**
- Route exists in Approutes.jsx but component not rendering
- Page loads blank
- No error in console

**Steps to Reproduce:**
1. Login to dashboard
2. Click "Dashboard" in navigation
3. Or navigate to http://localhost:3000/

**Root Cause Analysis:**
- Check if Dashboard component is properly exported and imported
- Check if route is correctly mapped in Approutes.jsx line 614
- Verify Dashboard.js component exists and is not broken

**Files to Investigate:**
- `frontend/src/routes/Approutes.jsx` (line 614)
- `frontend/src/screens/Dashboard.js`

---

### BX-HRMS-NAV-002: My Tasks Route Not Working
**Labels:** `bug`, `navigation`, `critical`  
**Priority:** P0 - Critical (Blocks personal features)  
**Assignee:** Backend Team

**Description:**
My Tasks at `/my-tasks` is not loading. The navigation item exists but clicking it returns blank page.

**Expected Behavior:**
- Users can navigate to `/my-tasks`
- My Tasks screen displays with task list

**Actual Behavior:**
- Route returns blank page
- No content renders

**Steps to Reproduce:**
1. Login to dashboard
2. Click "My Tasks" in navigation
3. Or navigate to http://localhost:3000/my-tasks

**Root Cause Analysis:**
- Check if MyTasksScreen component exists
- Check route mapping in Approutes.jsx
- Verify component is properly exported

**Files to Investigate:**
- `frontend/src/routes/Approutes.jsx` (line 652)
- `frontend/src/screens/MyTasksScreen.js`

---

### BX-HRMS-NAV-003: My Timesheet Route Not Working
**Labels:** `bug`, `navigation`, `critical`  
**Priority:** P0 - Critical  
**Assignee:** Backend Team

**Description:**
My Timesheet at `/my-timesheet` is not loading.

**Expected Behavior:**
- Users can navigate to `/my-timesheet`
- My Timesheet screen displays

**Actual Behavior:**
- Route returns blank page

**Steps to Reproduce:**
1. Login to dashboard
2. Click "My Timesheet" in navigation

**Files to Investigate:**
- `frontend/src/routes/Approutes.jsx` (line 653)
- `frontend/src/screens/MyTimesheetScreen.js`

---

### BX-HRMS-NAV-004: My Expenses Route Not Working
**Labels:** `bug`, `navigation`, `critical`  
**Priority:** P0 - Critical  
**Assignee:** Backend Team

**Description:**
My Expenses at `/my-expenses` is not loading.

**Expected Behavior:**
- Users can navigate to `/my-expenses`
- My Expenses screen displays

**Actual Behavior:**
- Route returns blank page

**Steps to Reproduce:**
1. Login to dashboard
2. Click "My Expenses" in navigation

**Files to Investigate:**
- `frontend/src/routes/Approutes.jsx` (line 654)
- `frontend/src/screens/MyExpensesScreen.js`

---

### BX-HRMS-NAV-005: My Referrals Route Not Working
**Labels:** `bug`, `navigation`, `critical`  
**Priority:** P0 - Critical  
**Assignee:** Backend Team

**Description:**
My Referrals at `/my-referrals` is not loading.

**Expected Behavior:**
- Users can navigate to `/my-referrals`
- My Referrals screen displays

**Actual Behavior:**
- Route returns blank page

**Steps to Reproduce:**
1. Login to dashboard
2. Click "My Referrals" in navigation

**Files to Investigate:**
- `frontend/src/routes/Approutes.jsx` (line 655)
- `frontend/src/screens/MyReferralsScreen.js`

---

## HIGH PRIORITY DEFECTS (Navigation Structure)

### BX-HRMS-NAV-006: Hardcoded "Users" Navigation Item Routes to Non-Existent Route
**Labels:** `bug`, `navigation`, `high`  
**Priority:** P1 - High  
**Assignee:** Full Stack  

**Description:**
Backend navigation endpoint is returning a hardcoded "users" navigation item that routes to `/users`, but this route doesn't exist in the frontend. This was supposed to be consolidated into "Users & Access Control" at `/admin/users-access-control`.

**Current State:**
- Backend returns "users" resource with route_path="/users"
- Frontend doesn't have a route for `/users`
- Clicking "Users" in Admin menu loads blank page

**Expected State:**
- Backend should NOT return "users" as separate item
- Should return "users-access-control" instead
- Route should be `/admin/users-access-control`
- All admin sub-tabs accessed via URL params: `/admin/users-access-control/users`, `/admin/users-access-control/business-units`, etc.

**Root Cause:**
- Backend `init_resources.py` line 18 lists "users" as separate Admin resource
- Navigation.py builds nav from database resources without consolidation logic
- Should consolidate Admin sub-items into single resource

**Files to Investigate:**
- `backend/app/seeds/init_resources.py` (line 18)
- `backend/app/api/v1/endpoints/navigation.py`
- Database: Check `resources` table for Admin module

**Fix Required:**
1. Remove "users" from Admin resources in init_resources.py
2. Add "users-access-control" resource with route `/admin/users-access-control`
3. Remove separate "business-units", "role-templates", "certifications" resources (or consolidate)
4. Run seed again to update database

---

### BX-HRMS-NAV-007: Admin Sub-Items Should Be Consolidated Under Single Entry
**Labels:** `bug`, `navigation`, `high`, `architecture`  
**Priority:** P1 - High  
**Assignee:** Full Stack

**Description:**
Admin module shows separate navigation items for:
- Business Units
- Role Templates
- Certifications
- Error Logs
- Admin Settings
- Users (broken - see BX-HRMS-NAV-006)
- Roles Permissions
- Organization

These should all be consolidated under a single "Users & Access Control" entry with sub-tabs.

**Expected Behavior:**
- Single "Users & Access Control" item in Admin module
- Routes to `/admin/users-access-control`
- Sub-tabs accessible via URL: `/admin/users-access-control/{section}`

**Current Behavior:**
- Multiple separate navigation items cluttering Admin menu
- Each item tries to navigate to its own route
- Navigation structure is confusing and breaks user mental model

**Impact:**
- Navigation menu is overcrowded
- Hard to find related functionality
- Multiple broken routes

**Fix Strategy:**
1. Consolidate all Admin sub-items into one "users-access-control" resource in backend
2. Update UsersAndAccessControl.js component to handle all tabs
3. Update navigation backend to return single consolidated item
4. Test all tabs work with URL routing

---

## VERIFICATION CHECKLIST

After fixes are applied:

### Personal Dashboard Items
- [ ] Dashboard loads when clicking "Dashboard" nav item
- [ ] My Tasks loads when clicking "My Tasks" nav item
- [ ] My Timesheet loads when clicking "My Timesheet" nav item
- [ ] My Expenses loads when clicking "My Expenses" nav item
- [ ] My Referrals loads when clicking "My Referrals" nav item

### Navigation Structure
- [ ] "Users" item removed from Admin menu
- [ ] "Users & Access Control" single item appears in Admin
- [ ] Clicking "Users & Access Control" routes to `/admin/users-access-control`
- [ ] Business Units tab accessible at `/admin/users-access-control/business-units`
- [ ] Role Templates tab accessible at `/admin/users-access-control/role-templates`
- [ ] Certifications accessible at `/admin/users-access-control/certifications` or separate menu item
- [ ] Error Logs accessible at `/admin/error-log` (can stay separate)

### Navigation Cleanup
- [ ] No blank pages when clicking nav items
- [ ] No 404 errors in console
- [ ] All nav items route to valid screens
- [ ] No hardcoded routes override backend navigation

---

## Related Issues & PRs

- **Related:** Navigation cleanup commit 3d3b533c (removed NAV_PERMISSIONS hardcoding)
- **Related:** NAVIGATION_REFERENCE.md created as tracking document

---

## Notes

- All top 5 personal nav items need investigation - likely missing screen components
- Admin consolidation is architectural fix for BX-HRMS-[DEFECT-003]
- Backend navigation endpoint should be sole source of truth (no frontend hardcoding)
- Each item should have corresponding route in Approutes.jsx
