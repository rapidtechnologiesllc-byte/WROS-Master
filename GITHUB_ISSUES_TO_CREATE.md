# GitHub Issues - Create These in Repository

## Issue #1: FEAT - Unified RoleTemplateEditor with Permissions Selection

**Type:** Feature / Bug Fix  
**Labels:** enhancement, rbac, ui, high-priority  
**Assignee:** @AvinashMukund

### Description
Complete the unified RoleTemplateEditor modal to include permissions selection and storage functionality.

### Current State ❌
- Modal displays template name and description only
- NO modules/resources permission selector
- NO permission storage on save
- Button color not appropriate for primary action

### Requirements ✅ NEEDED

#### Create Mode
- [ ] Template name input (required field indicator)
- [ ] Description textarea
- [ ] Modules & Resources permission grid (view/create/edit/delete checkboxes)
- [ ] "Create Template" button (primary blue color)
- [ ] Loading state during creation

#### Edit Mode
- [ ] Pre-populate template name from database (read-only, grayed out)
- [ ] Pre-populate description from database
- [ ] Pre-populate permissions from database in grid
- [ ] "Save Changes" button (primary blue color)
- [ ] Loading state during save

#### Permissions Storage
- [ ] Call backend `POST /admin/role-templates/{id}/grant-permission` for enabled permissions
- [ ] Call backend `POST /admin/role-templates/{id}/revoke-permission` for disabled permissions
- [ ] Refresh template permissions after save
- [ ] Show success toast notification
- [ ] Handle errors gracefully with error toast

#### UI/UX
- [ ] Module headers collapsible (show/hide resources)
- [ ] "Enable All" / "Disable All" buttons per module
- [ ] Permission grid shows: view/create/edit/delete as toggleable buttons
- [ ] Consistent blue button color for primary actions
- [ ] Modal scrollable when content exceeds viewport
- [ ] Close button (X) in top right

### Acceptance Criteria
- [x] Create template with name and description
- [ ] Create template WITH permissions
- [ ] Edit template updates name/description
- [ ] Edit template updates permissions
- [ ] Permissions persist in database
- [ ] UI is consistent and intuitive
- [ ] All edge cases handled (no permissions selected, etc.)
- [ ] Error handling for API failures

### Related Commits
- **f0f54c8e** - feat: Implement unified RoleTemplateEditor modal - create and edit same component
- **74d2ed8a** - fix: Remove old inline permission editing code to fix JSX syntax error
- **2e7272c2** - docs: Update navigation testing document - unified editor complete

### Code Changes Needed
**File:** `frontend/src/components/RoleTemplateEditor.jsx`
- Add permissions grid rendering
- Add handleTogglePermission function
- Add handleSavePermissions function
- Fix button colors and styling
- Add loading states

**File:** `frontend/src/screens/UsersAndAccessControl.js`
- Update handleEditorSuccess to not reload (use state update instead)
- Pass modules data to RoleTemplateEditor

### Blockers
None - This is foundational for RBAC system

### Related Issues
- Relates to: Role-based access control system
- Depends on: Backend permission grant/revoke endpoints

---

## Issue #2: BUG - Dashboard Navigation Links Not Working

**Type:** Bug  
**Labels:** bug, navigation, high-priority  
**Severity:** HIGH

### Description
Dashboard-related navigation items don't navigate when clicked. Links appear in sidebar but clicking them doesn't load the corresponding screen.

### Affected Items
- Dashboard (Executive Dashboards → Dashboard)
- CEO Dashboard (Executive Dashboards → CEO Dashboard)
- (Potentially others in Executive Dashboards module)

### Current State
- Navigation link exists in sidebar
- Icon renders correctly
- Clicking link does NOT navigate
- No error messages shown
- Page stays on previous screen

### Root Cause
Need investigation - likely:
- Missing routes in frontend Approutes.jsx
- Missing components
- Navigation event not firing

### Requirements
- [ ] Identify root cause
- [ ] Create missing routes if needed
- [ ] Create/fix dashboard components
- [ ] Test navigation works for all dashboard items

### Testing Steps
1. Navigate to Executive Dashboards section
2. Click "Dashboard" link
3. Verify page loads at /dashboard route
4. Verify dashboard content displays

### Acceptance Criteria
- [ ] All Dashboard items navigate correctly
- [ ] Routes exist in Approutes.jsx
- [ ] Components exist and load
- [ ] No console errors
- [ ] Data displays correctly

### Related Commits
None yet - needs investigation and fix

---

## Issue #3: Navigation Testing - Comprehensive Audit

**Type:** Testing / QA  
**Labels:** testing, navigation, quality-assurance  
**Scope:** All 53 navigation items

### Description
Systematically test all 53 navigation items (40 resources + 13 sub-pages) to identify which load correctly, which show no data, and which are broken.

### Testing Matrix
- Executive Dashboards: 6 items (2 broken identified)
- Admin: 9 items (4 working, 5 pending)
- Recruitment: 5 items (pending)
- Workforce: 6 items (pending)
- Sales: 5 items (pending)
- Project Management: 5 items (pending)
- Finance: 6 items (pending)
- Reporting: 4 items (pending)
- System: 8 items (pending)
- Engagement & Communications: 5 items (pending)
- Human Resources: 5 items (pending)

### Testing Protocol
For each item:
1. Click navigation link
2. Wait for page load
3. Document: ✅ Loads | ⚠️ No Data | ❌ Broken
4. Take screenshot if broken
5. Note any error messages

### Defects Found So Far
1. Dashboard - broken navigation
2. CEO Dashboard - broken navigation

### Next Steps
- [ ] Test remaining 40+ items
- [ ] Create separate GitHub issues for each defect
- [ ] Prioritize by severity/impact

### Related Commits
- 2e7272c2 - docs: Update navigation testing document - unified editor complete

---

## Issue #4: Bug - Old Unused State Not Cleaned Up

**Type:** Technical Debt  
**Labels:** refactor, cleanup  
**Priority:** LOW

### Description
Some old state variables and functions still present but unused after RoleTemplateEditor unification.

### Issues
- [ ] `moduleStates` state declared but never used
- [ ] Old functions that manipulated `editingTemplateId` directly
- [ ] Unused imports

### Fix
Remove all unused code to keep codebase clean.

### Related Commits
- f0f54c8e - Partial cleanup
- 74d2ed8a - More cleanup

---

## Issue Tracking - Commit to GitHub Links

When creating issues in GitHub, update commit messages with issue links:

```
Format: Closes #123 or Relates to #123

Example:
git commit -m "feat: Add permission selector to RoleTemplateEditor

- Add modules/resources permission grid
- Add permission grant/revoke API calls
- Add loading states and error handling
- Fix button colors to primary blue

Closes #[ISSUE_NUMBER]
Related commits:
- f0f54c8e: Initial unified editor
- 74d2ed8a: Syntax error fix

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

## End-to-End Traceability Example

```
GitHub Issue #123
  ├─ Description: Complete unified RoleTemplateEditor
  ├─ Acceptance Criteria
  │  ├─ [x] Create template with name/desc
  │  └─ [ ] Create with permissions (THIS COMMIT)
  │
  ├─ Related Commits
  │  ├─ f0f54c8e - Initial implementation
  │  ├─ 74d2ed8a - Fix syntax errors
  │  └─ [NEXT] - Add permission selector (closes #123)
  │
  └─ Comments
     └─ "Implemented permission grid in RoleTemplateEditor. 
        Added handleTogglePermission and handleSavePermissions.
        See commit [abc123] for details."
```

