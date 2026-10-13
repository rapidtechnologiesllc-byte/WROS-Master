# Modal to Page Refactoring Task

## Summary
Remove all inline Create/Edit modals from container components and replace with dedicated route-based form pages.

## Components to Refactor

### 1. UsersAndAccessControl.js
**Location:** src/screens/UsersAndAccessControl.js
**Action:** 
- Remove: showCreateModal, showEditModal state + all related handlers
- Remove: ~500 lines of JSX for Create/Edit User modals (lines 685-924+)
- Add: Navigate to `/admin/users-access-control/users/create` on "Add User" button
- Add: Navigate to `/admin/users-access-control/users/:userId/edit` on edit link
- Already wired: UserFormPage routes exist in Approutes.jsx

### 2. RoleTemplateManager.js  
**Location:** src/screens/RoleTemplateManager.js
**Action:**
- Remove: inline Create Role Template modal
- Create: RoleTemplateFormPage.jsx (wrap RoleTemplateForm.jsx component)
- Add route: `/admin/role-templates/create` → RoleTemplateFormPage (create mode)
- Add route: `/admin/role-templates/:templateId/edit` → RoleTemplateFormPage (edit mode)
- Wire "Add" button to navigate to create route

### 3. BusinessUnitsAdmin (TBD - Find correct file)
**Action:**
- Create: BusinessUnitFormPage.jsx (wrap BusinessUnitModal.js)
- Add routes for create/edit
- Wire buttons to navigate

### 4. DeliveryCentersAdmin (TBD - Find correct file)
**Action:**
- Create: DeliveryCenterFormPage.jsx (wrap DeliveryCenterModal.js)
- Add routes for create/edit
- Wire buttons to navigate

## Files to DELETE (after refactoring)
- Delete old inline modal code sections
- Verify no orphaned state or handlers

## Routes to ADD
- /admin/users-access-control/users/create ✅ (already exists)
- /admin/users-access-control/users/:userId/edit ✅ (already exists)
- /admin/role-templates/create (new)
- /admin/role-templates/:templateId/edit (new)
- /admin/business-units/create (new)
- /admin/business-units/:buId/edit (new)
- /admin/delivery-centers/create (new)
- /admin/delivery-centers/:centerId/edit (new)

## Status
- [ ] UsersAndAccessControl refactored
- [ ] RoleTemplateFormPage created & routed
- [ ] BusinessUnitFormPage created & routed
- [ ] DeliveryCenterFormPage created & routed
- [ ] All routes added to Approutes.jsx
- [ ] Old modal files cleaned up
- [ ] Testing complete
