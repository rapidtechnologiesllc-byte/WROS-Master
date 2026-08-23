# GitHub Issues Mapping

**Project:** https://github.com/users/rapidtechnologiesllc-byte/projects/1

This document maps all open issues from CLAUDE.md to GitHub issues for centralized tracking.

---

## BACKEND DEFECTS (BX-HRMS)

### BX-HRMS-DEFECT-001: User Creation Endpoint JSON Parsing
- **Status:** ✅ FIXED (Commit cb8c0de)
- **GitHub Issue:** (No issue - already fixed)
- **Severity:** Critical
- **Description:** `/hr/users/create-with-roles` endpoint treated parameters as query params instead of JSON body
- **Fix Applied:** Updated endpoints to accept request body with Pydantic schemas
- **Files:** app/schemas/user.py, app/api/v1/endpoints/users.py
- **Tested:** Yes
- **Deployed:** No (pending)

### BX-HRMS-DEFECT-002: Role Template Auto-Creation
- **Status:** ⏳ PENDING FIX
- **GitHub Issue:** #100
- **Severity:** High
- **Description:** Role template created immediately on "New Role Template" button, should only create on Save
- **Impact:** Blank templates require manual deletion
- **Files:** frontend/src/screens/UsersAndAccessControl.js (handleNewRoleTemplate)
- **Effort:** 1-2 hours
- **Labels:** frontend, ux, bug

### BX-HRMS-DEFECT-003: Administration Navigation Structure
- **Status:** ⏳ PENDING IMPLEMENTATION
- **GitHub Issue:** #101
- **Severity:** High
- **Description:** Role Templates shows as standalone sidebar item, should only be accessible via Users & Access Control tabs
- **Impact:** Navigation confusion, wrong URL hierarchy
- **Files:** frontend/src/layout/Shell.js, frontend/src/layout/navItems.js
- **Effort:** 2-3 hours
- **Labels:** frontend, navigation, architecture

### BX-HRMS-DEFECT-004: Create User Form UX Issues
- **Status:** ⏳ PENDING FIX
- **GitHub Issue:** #102
- **Severity:** Medium
- **Description:** Multiple UX issues: Partner field should auto-generate from BU, missing required field indicators (*), wrong field order
- **Impact:** User confusion, form validation unclear
- **Files:** frontend/src/screens/UsersAndAccessControl.js
- **Effort:** 2-3 hours
- **Labels:** frontend, ux, forms

### BX-HRMS-DEFECT-005: Backend Port Configuration
- **Status:** ⏳ NEEDS CLARIFICATION
- **GitHub Issue:** #103
- **Severity:** Medium
- **Description:** Frontend expects port 8080, but preview server auto-assigns different ports causing CORS errors
- **Cause:** Process management issue, not code bug
- **Workaround:** Kill stray processes on 8080 before starting backend
- **Files:** Configuration / Deployment process
- **Labels:** devops, configuration, bug

---

## FLASH ORCHESTRATOR & GOAL CASCADING SYSTEM

### EPIC-FLASH-001: Database Integration for Goals System
- **Status:** ✅ COMPLETED (Agent a3e4009fed85c1a23)
- **GitHub Issue:** #104
- **Severity:** Critical (was blocker)
- **Description:** Wire database queries, implement YTD progress tracking, replace mock data
- **Completed:** 
  - Strategic goals CRUD in database
  - Cascaded goals auto-generation
  - Cumulative tech lead progress queries
  - Audit trail via PyramidReport model
- **Files:** 
  - backend/app/models/strategic_goal.py (NEW)
  - backend/app/api/v1/endpoints/goals_management.py
  - backend/app/api/v1/endpoints/agent_pyramid_reporting.py
- **Commits:** f0e1f28a, ee1cbea4
- **Labels:** backend, database, flash-system

### EPIC-FLASH-002: Frontend API Integration
- **Status:** ✅ COMPLETED (Agent a3e4009fed85c1a23)
- **GitHub Issue:** #105
- **Severity:** Critical (was blocker)
- **Description:** Wire CEOGoalsSettingScreen and GoalsManagementScreen to backend API endpoints
- **Completed:**
  - CEOGoalsSettingScreen fetches /goals/strategic
  - GoalsManagementScreen fetches cascaded goals
  - Loading states and error handling
  - Toast notifications
- **Files:**
  - frontend/src/screens/CEOGoalsSettingScreen.js
  - frontend/src/screens/GoalsManagementScreen.js
- **Commits:** f0e1f28a
- **Labels:** frontend, api-integration, flash-system

### EPIC-FLASH-003: Flash Validation UI Component
- **Status:** ✅ COMPLETED (Agent a3e4009fed85c1a23)
- **GitHub Issue:** #106
- **Severity:** High
- **Description:** Build FlashValidationForm component with status badges, progress bars, coaching feedback
- **Completed:**
  - Component with all 4 statuses (ON_TRACK, SLIGHT_LAG, CRITICAL_LAG, AHEAD)
  - Progress bars for 5 timeframes (Annual → Quarterly → Monthly → Weekly → Daily)
  - Confirmation gates for progress issues
  - Specific coaching + action lists per status
- **Files:** frontend/src/components/FlashValidationForm.js (NEW)
- **Commits:** f0e1f28a
- **Labels:** frontend, components, flash-system

### EPIC-FLASH-004: Role Template Navigation Integration
- **Status:** ✅ COMPLETED (Agent a3e4009fed85c1a23)
- **GitHub Issue:** #107
- **Severity:** High
- **Description:** Wire role template modules to Shell.js navigation for dynamic filtering
- **Completed:**
  - Module-based navigation filtering
  - Users see only permitted modules
  - Fallback mechanisms for reliability
  - Debug logging
- **Files:**
  - frontend/src/utils/permissionsRbac.js
  - frontend/src/layout/Shell.js
- **Commits:** ee1cbea4
- **Labels:** frontend, rbac, navigation

### EPIC-FLASH-005: Dark Mode UI Theme
- **Status:** ✅ COMPLETED (Agent a4aadb828b526f385)
- **GitHub Issue:** #108
- **Severity:** Medium
- **Description:** Add dark mode theme toggle, implement dark styling across all screens
- **Expected Completion:** 30-45 minutes
- **Scope:**
  - Theme toggle button in header (sun/moon icon)
  - Dark mode styles for all screens
  - Preference persistence in localStorage
  - TailwindCSS dark: classes
- **Files:**
  - frontend/src/context/ThemeContext.js (NEW)
  - frontend/src/components/TopBar.js (updated)
  - frontend/tailwind.config.js (darkMode: 'class')
  - All screens: CEOGoalsSettingScreen, GoalsManagementScreen, etc.
- **Labels:** frontend, ui, dark-mode

### EPIC-FLASH-006: End-to-End System Testing
- **Status:** ✅ COMPLETED (Agent a4aadb828b526f385)
- **GitHub Issue:** #109
- **Severity:** High
- **Description:** Comprehensive E2E testing of entire Flash/Goal system
- **Expected Completion:** 60-90 minutes
- **Test Coverage:**
  - Phase 1: Backend/Database setup
  - Phase 2: Frontend connectivity
  - Phase 3: CEO Goals creation & cascading
  - Phase 4: Flash Validation (SLIGHT_LAG)
  - Phase 5: Critical Lag scenario
  - Phase 6: On Track scenario
  - Phase 7: Role-based navigation
  - Phase 8: Dark mode toggle
- **Deliverable:** E2E_TEST_RESULTS.md with all test scenarios documented
- **Labels:** testing, qa, flash-system

---

## HOW TO USE THIS FILE

1. **For New Issues:** When adding work to bx-hrms.md, also create a corresponding entry here
2. **GitHub Issue Reference:** Update GitHub Issue column with actual issue number (e.g., #123)
3. **Status Tracking:** Update Status column as work progresses
4. **Cross-Reference:** Link GitHub issues to this file in issue descriptions

---

## NEXT STEPS

- [ ] Install GitHub CLI (gh) for programmatic issue creation
- [ ] Create all GitHub issues from this mapping
- [ ] Add GitHub issue numbers back to this file
- [ ] Update CLAUDE.md and backend/CLAUDE.md with GitHub issue links
- [ ] Set up automation to sync changes between documentation and GitHub

---

## ISSUE CREATION TEMPLATE

```markdown
## Title: [Category] Issue Title

**Status:** [OPEN / PENDING / IN PROGRESS / COMPLETED]

**Severity:** [Critical / High / Medium / Low]

**Description:**
[Issue description from CLAUDE.md]

**Impact:**
[Business/technical impact]

**Files Affected:**
- [file1.py]
- [file2.js]

**Effort:** [hours]

**Labels:** [comma-separated labels]

**Related Issues:** [#123, #456]

**Notes:**
[Any additional context]
```
