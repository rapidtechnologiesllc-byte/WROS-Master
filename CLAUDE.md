# WROS Frontend - Development Notes

## 🚀 CURRENT STATUS (2026-08-23 Session - Navigation Duplicate Groups Fixed)

**STATUS:** ✅ FIXED - Duplicate "Administration" sidebar sections merged into single consolidated group

### Session Work (2026-08-23 - Navigation Deduplication):

**BX-HRMS-[DEFECT-002] - Duplicate Administration Sidebar Sections - FIXED**

#### Problem
User reported seeing TWO "Administration" sections in the left sidebar after login:
- **First Administration:** Users, Business Units
- **Second Administration:** Users, Role Templates, Business Units, Error Log, Certifications, Message Templates

This was confusing and violated the expected single-group navigation structure.

#### Root Cause
The backend `/hr/me/navigation` endpoint returns navigation groups from the user's permissions. Due to how permission groups are structured, it was returning two separate groups both labeled "Administration" instead of combining them into one.

Frontend's `fetchNavigationFromBackend()` function wasn't deduplicating groups with the same label, so both were rendered separately in the sidebar.

#### Solution Implemented
Added group deduplication logic in Shell.js (lines 298-318):
1. Create `groupsByLabel` map to track groups by their label
2. When processing backend response, check if a group with the same label already exists
3. If duplicate found, merge items from the new group into the existing group (avoiding duplicate keys)
4. Continue with existing filtering logic (remove roleTemplates, apply MODULE_CONFIG)

**Before:**
```javascript
const filteredGroups = navGroups.map(group => ({...})).filter(...)
```

**After:**
```javascript
// Deduplicate groups with same label
const groupsByLabel = {};
navGroups.forEach(group => {
  if (!groupsByLabel[group.label]) {
    groupsByLabel[group.label] = { ...group, items: [...(group.items || [])] };
  } else {
    // Merge items from duplicate groups
    const existingKeys = new Set(groupsByLabel[group.label].items.map(i => i.key));
    group.items?.forEach(item => {
      if (!existingKeys.has(item.key)) {
        groupsByLabel[group.label].items.push(item);
        existingKeys.add(item.key);
      }
    });
  }
});
navGroups = Object.values(groupsByLabel);
```

#### Result
✅ Single "Administration" group now appears in sidebar containing all items:
- users
- business_units
- delivery_centers
- organizational_hierarchy
- role_templates (filtered out by MODULE_CONFIG)
- error_log
- certifications
- message_templates

Navigation is now clean and consistent with the expected structure.

**Commit:** 6f82724b

---

## 🚀 PREVIOUS STATUS (2026-08-19 Session - JWT Token Fix Verified - Authentication Working)

**STATUS:** ✅ PRODUCTION READY - End-to-end login flow verified working with backend JWT token fix

### Session Work (2026-08-19 - JWT Token Fix Verification):

**BX-HRMS: JWT Token Claims Fix - VERIFIED WORKING**

#### What Was Fixed (Backend)

Backend JWT token creation was standardized across all endpoints:
- Token "sub" field: Changed from `UserEmail` → `UserID`
- Token "type" field: Changed from `UserRole` → `"user"`
- Added "email" field to token payload

This fixed 401 Unauthorized errors on authenticated requests after login.

#### Frontend Impact

✅ Login flow now works end-to-end:
1. User enters email → clicks Next
2. Password form appears
3. User enters password → clicks Sign In
4. Backend returns valid JWT token with correct claims
5. Frontend stores token in localStorage
6. Dashboard loads with all API requests succeeding (200 OK)

#### Testing Results

**Browser Test Flow:**
- Email entry: recruiter@test.com → ✅
- Email validation: Next button → ✅
- Password entry: TestRecruiter@123 → ✅
- Login submission: Sign In → ✅
- Dashboard access: Full page load → ✅

**API Endpoints Verified:**
```
POST /auth/login - Status: 200 ✅
GET /hr/me - Status: 200 ✅
GET /onboarding/hr/get_all_candidates - Status: 200 ✅
GET /jobs/all - Status: 200 ✅
GET /interviews - Status: 200 ✅
GET /hr/users/all - Status: 200 ✅
GET /status/all - Status: 200 ✅
```

#### No Frontend Code Changes Required

The frontend code correctly:
- Stores JWT token in localStorage
- Sends Authorization header on all requests
- Handles 401 errors appropriately

The issue was 100% backend (JWT claims format), now fixed.

---

## 🚀 CURRENT STATUS (2026-08-12 Session - Permission-Based RBAC Navigation Complete)

**Frontend:** ✅ PRODUCTION READY - Dynamic permission-based navigation, employee conversion screen
**RBAC Integration:** ✅ COMPLETE - Multi-role support, BU scoping, permission-based navigation
**Employee Conversion:** ✅ NEW SCREEN - Full UI for candidate → employee workflow
**Git Status:** ✅ PUSHED - Commit 0a8fade to main, RBAC frontend integration complete

### Session Work (2026-08-12 - RBAC Frontend Integration):
**EPIC: Frontend RBAC Integration - Dynamic Navigation & Employee Conversion - COMPLETED**

#### Key Features Implemented:

**1. Permission-Based Navigation** (Shell.js)
- Replaced role-based nav with permission-based filtering
- NAV_PERMISSIONS mapping for each screen (recruitment.view, employee.manage, etc.)
- Backward compatibility: falls back to role-based nav if permissions not available
- Dynamic filtering: shows only permitted screens based on user's permission union

**2. Multi-Role Support** (Login + Auth)
- AuthPage.js now stores roles[] and permissions[] from backend JWT
- Stores business_unit_id and business_unit_name for BU scoping
- Maintains backward compatibility with legacy permission_role field
- Permissions are UNION of all assigned roles

**3. Employee Conversion Screen** (NEW)
- New EmployeeConversionScreen.js component
- Candidate selection (filters to OFFER status)
- Employee details: name, email, position, joining date
- Business Unit dropdown (BU-scoped)
- Multi-role checkbox selector
- Calls new `/employees/convert-from-candidate` backend endpoint
- Auto-password generation (server-side)

**4. Enhanced User Creation Form** (UsersAndAccessControl.js)
- Business Unit dropdown (optional, new RBAC only)
- Multi-role checkboxes (when BU selected)
- Backward compat: legacy single-role selection still works
- Calls new `/users/create-with-roles` endpoint when BU + roles selected
- Falls back to legacy `createHrUser` if no BU selected

**5. Permission Utilities** (permissionsRbac.js)
- `hasPermission(permission)` - Check specific permission with wildcard support
- `hasAnyPermission(list)` - Check if user has any permission from list
- `hasAllPermissions(list)` - Check if user has all permissions
- `hasRole(roleName)` - Check specific role
- `isSuperUser()` - Check for super user (with wildcard or role)
- `canViewModule(moduleName)` - Shorthand for module.view check
- `canCreateInModule`, `canEditInModule`, etc. - Action-specific checks
- All functions read from localStorage (roles[], permissions[])

#### Files Created:
- `src/utils/permissionsRbac.js` - Permission utility functions (100 LOC)
- `src/screens/EmployeeConversionScreen.js` - Full employee conversion UI (250 LOC)

#### Files Modified:
- `src/pages/AuthPage.js` - Store roles[] and permissions[] from JWT (line 74-126)
- `src/layout/Shell.js` - Permission-based navigation with NAV_PERMISSIONS mapping (line 27-164)
- `src/layout/navItems.js` - Added employeeConversion nav item
- `src/routes/Approutes.jsx` - Added employee-conversion route
- `src/utils/Routes.js` - Added EMPLOYEE_CONVERSION route constant
- `src/screens/UsersAndAccessControl.js` - Multi-role and BU selection in create user form

#### Navigation Permission Mapping:
```javascript
recruitment: recruitment.view
sales (clientManagement): business_unit.manage  
workforce (employees): employee.view, (conversion): employee.manage
projects: project.manage
finance: invoice.view, reports.financial
admin (users): user.manage, (settings): system.manage
```

#### User Flow Examples:

**Creating Multi-Role User:**
1. Navigate to Users & Access Control
2. Click "Add User"
3. Enter name, email, password
4. Select Business Unit
5. Check multiple roles (e.g., Partner + BU Head + Hiring Manager)
6. Click "Create User"
7. User gets combined permissions from all roles

**Converting Candidate to Employee:**
1. Navigate to "Convert to Employee" (Workforce section)
2. Select candidate (from OFFER status)
3. Auto-fills name, email
4. Enter position, joining date
5. Select Business Unit
6. Select roles (one or more)
7. Click "Convert to Employee"
8. Employee account created with roles assigned

#### Backward Compatibility:
- Legacy users without roles[]/permissions[] still work (fallback to role-based nav)
- Old createHrUser endpoint still supported (no BU selection)
- permission_role field still populated for legacy systems
- All permission checks default to allow if no permissions array found

**Commit:** 0a8fade
**Status:** 🟢 LIVE IN PRODUCTION (Frontend ready for user testing)

---

## Previous Session Summary (2026-08-08 - Candidate Profile Rebuild)

### ✅ COMPLETED THIS SESSION - CANDIDATE PROFILE COMPLETE REBUILD

**13 Commits - Full Profile Architecture Redesign**

**Phase 1: Removed Redundant Fields & Reorganized Structure**
- Removed "Review for Submission" UDF field from Submit Job modal
- Moved Gender, Date of Birth, Current Location to Basic Information
- Removed Personal Information section (merged into Basic)
- Moved Source field to Professional Information
- Changed Notice Period from date picker to days input (30, 45, 60)
- Removed Skills (comma-separated) field from Professional section

**Phase 2: Added Resume-Extracted Sections**
- Education Details (Level, University/College, Start/End dates, Degree)
- Experience Details (Company, Title, Start/End dates, Responsibilities)
- Certifications (Name, Organization, Issue/Expiry dates, Credential ID)
- Skills Management Modal (structured data: skill name, years, last used date, primary designation)

**Phase 3: Reorganized Layout for Sleek Design**
- Basic Information: 9 fields (merged from 2 sections)
- Professional Information: 5 fields (streamlined, auto-calc Experience)
- Skills: Modal-based with primary skill designation
- Resume: Always visible, collapsible with preview
- Right Sidebar: Notes (inline textarea + backend sync, no modal)
- Removed UDF popup modal completely from Submit Job flow

**Commits:**
- 0f87bad: Remove Review for Submission UDF
- 2cf700d: Add Education/Experience/Documents sections
- 30f50bc: Add inline Notes section
- 4748dc8: Change Notice Period to days input
- 2768ae9: Add Resume section
- f12bb42: Move Notes to right sidebar
- 77b91a9: Fix joining_date validation
- 59bafa4: Add Skills/Education/Experience/Certifications (resume-parsed)
- 73c5a98: Add Skills management modal
- 5766864: Streamline profile sections
- 444b4d8: Fix Resume display + remove UDF modal
- b5f8df5: Fix syntax error in Resume section
- c2c85da: Fix JSX indentation

---

## Architecture & Patterns

### Profile Section Structure
Each profile section follows this pattern:
- **Editable sections**: Basic Information, Professional Information, Identity & Background, Recruitment Assignment
- **Resume-extracted (read-only)**: Education, Experience, Certifications, Skills
- **Supporting**: Resume (always visible, collapsible), Documents, Notes (right sidebar)

### Skills Modal Pattern
Skills stored as array of objects with fields:
- `name`: Skill name
- `yearsOfExperience`: Years of experience
- `lastUsedDate`: When skill was last used
- `isPrimary`: Boolean flag for primary skill

Validation: minimum 1 skill required, exactly 1 primary skill.

### Resume Data Flow
- Fetched from candidateFullDetails.resume_data
- Always displays (no conditional hide)
- Collapsible preview via chevron button
- File download link for resume document
- Shows "No resume available" fallback message

### Notice Period Input
- Changed from date picker to number input (30, 45, 60 days)
- Field name: candidate_notice_period
- NOT sent as candidate_joining_date (different field with date format)

---

## Current Project State

### Candidate Profile: ✅ COMPLETE THIS SESSION
- 13 commits delivered: Full profile rebuild
- 2 main editable sections (Basic Information, Professional Information)
- 4 resume-extracted read-only sections (Education, Experience, Certifications, Skills)
- Skills: Structured modal with primary skill designation
- Resume: Always visible, collapsible preview with download
- Right Sidebar: Notes with inline textarea (backend sync)
- UDF popup modal: Removed from Submit Job flow
- Status: Production-ready for UAT

### Backlog Priorities (Post-Profile)
See MEMORY.md for full EPIC-04 scope. Next focus:
1. **Thunder autonomous candidate journey** (Phase 3 Part B) - CRITICAL
2. **Interview regrouping** (group by job/round with rehire guards)
3. **Candidate portal strategy** (map to JobDiva integration)

---

## Known Issues & Workarounds

### Port Management
- **CRITICAL:** Kill stray port 8080 processes at session start
- 8080 is MAIN backend port (not remote dummy)
- Use task manager or `netstat -ano | findstr :8080`

### Login Credentials (Testing)
Current test users for local development:
- superuser@blitzenx.com / Superuser!123 (or use auto-assigned bcrypt hash)
- admin@blitzenx.com / Admin@123
- test@blitzenx.com / Test@123

Database path: OnboardingModule-Backend/local_dev.sqlite3 (resolved to absolute path by backend)

### Deferred Features (Backlog)
- **Resume upload/attachment functionality** - UI displays "Upload resume" message, no button/handler built
- **Candidate portal strategy** - JobDiva portal mapping (browse/apply/register-interest/progress) undefined
- **Interview regrouping** - Group interviews by job/round with rehire guards (PRIORITY)

---

## Code Standards (Established 2026-07-23)

- CardBlock pattern for multi-section editable UI
- Modal state management: close guard only prevents races, doesn't prevent close
- All state updates before calling close functions
- No hardcoded values in production-ready stories
- React hooks: useCallback for memoized callbacks, useMemo for derived state
- **Defensive programming**: Use optional chaining (?.) on all external data access
- **Array-to-string conversion**: API validators expect strings, use join(", ") for skill arrays
- **Date format validation**: Only send candidate_joining_date if matches YYYY-MM-DD regex

---

## All Commits This Session (2026-08-08)

```
0f87bad Remove 'Review for Submission' UDF field from CandidateAssignJobModal
2cf700d Add Education/Experience/Documents sections to candidate profile
30f50bc Add inline Notes section to candidate profile (center placement)
4748dc8 Change Notice Period from date picker to days input (30/45/60)
2768ae9 Add Resume section (collapsible, always visible display)
f12bb42 Move Notes section from center to right sidebar
77b91a9 Fix joining_date validation: only send if YYYY-MM-DD format
59bafa4 Add Skills/Education/Experience/Certifications (resume-parsed sections)
73c5a98 Add Skills management modal with primary skill designation
5766864 Streamline profile: merge Personal into Basic, move Source field
444b4d8 Fix Resume display (always show) + remove UDF modal from Submit Job
b5f8df5 Fix JSX syntax error in Resume section (unexpected token)
c2c85da Fix Resume section indentation (final compilation fix)
```

---

## Session Discipline

- Complete ONE task thoroughly before moving to next
- Code pushed to main after each logical milestone
- Test golden path + edge cases in browser before committing
- Defensive programming with optional chaining throughout
- No placeholder fields or hardcoded values in production code
