# ZERO-HARDCODING REMEDIATION PLAN

**Status:** In Progress  
**Total Occurrences Found:** 486 hardcoded permission references  
**Files Affected:** 69 (22 frontend, 47 backend)  
**Scope:** Complete removal of hardcoded permission strings and dynamic loading from role templates

---

## 🎯 CRITICAL PATH (FIX FIRST)

### PRIORITY 1: Admin Screens (Users Can't Assign Permissions)

**Files:**
- `src/screens/UsersAndAccessControl.js` (7 occurrences)
- `app/api/v1/endpoints/rbac.py` (32 occurrences)
- `app/api/v1/endpoints/users.py` (11 occurrences)
- `app/services/rbac_service.py` (23 occurrences)

**Issue:** Admin can't assign permissions to users because:
- Permission checks are hardcoded
- Role templates can't be created with permissions
- User-role-template assignments fail

**Fix Required:**
1. Remove hardcoded permission validation
2. Allow admins to select from available permissions (loaded from DB)
3. Wire role template creation to accept permission array
4. Enable permission assignment to users via role templates

---

### PRIORITY 2: Job Create Screen (Currently Broken)

**Files:**
- `src/screens/JobCreate.js` (7 occurrences)
- `app/api/v1/endpoints/create_job.py` (5 occurrences)

**Issue:** Users can't create jobs because:
- Hardcoded check: `if !permissions.includes('job.create')`
- No way to grant 'job.create' permission through role templates

**Fix Required:**
1. Remove hardcoded 'job.create' permission check
2. Load permissions from user's assigned role template
3. Check: `if user.roleTemplate.permissions.includes('job.create')`

---

### PRIORITY 3: Navigation & Route Guards

**Files:**
- `src/layout/Shell.js` (1 occurrence)
- `src/routes/Approutes.jsx` (6 occurrences)
- `app/core/dependencies.py` (1 occurrence)

**Issue:** Permission-based navigation uses hardcoded strings

**Fix Required:**
1. Replace hardcoded NAV_PERMISSIONS mappings
2. Load screen permissions from role template
3. Hide screens user doesn't have access to

---

## 📋 REMOVAL STRATEGY

### Phase 1: Admin & RBAC System (Hours 1-2)
```
UsersAndAccessControl.js
rbac.py endpoint
rbac_service.py
role_templates.py
role_template_service.py
```

**Remove:**
- Hardcoded permission string lists
- Permission validation against hardcoded array
- Permission assignment logic using strings

**Replace With:**
- Load permissions from `RoleTemplate` model
- Allow selecting from permission pool
- Dynamic permission assignment

---

### Phase 2: Core Endpoints (Hours 2-4)
```
create_job.py
users.py
candidates endpoint
employees endpoint
interviews endpoint
```

**Remove:**
- Check for hardcoded permission strings
- Hardcoded "job.create", "candidate.view", etc.

**Replace With:**
- Check `user.roleTemplate.permissions`
- Dynamic permission validation

---

### Phase 3: Frontend Navigation & Guards (Hours 4-5)
```
Shell.js (Nav filtering)
Approutes.jsx (Route guards)
All screen components (permission checks)
```

**Remove:**
- NAV_PERMISSIONS hardcoded mappings
- Permission string checks in components
- Role-based visibility logic

**Replace With:**
- Load from user's role template
- Check at render time: `user.roleTemplate.permissions`

---

### Phase 4: Services & Utils (Hours 5-6)
```
permission_service.py
rbac_expanded_permissions.py
permissions.js
permission_decorators.py
```

**Remove:**
- Permission string definitions
- Hardcoded role-permission mappings
- String-based permission checks

**Replace With:**
- Helper functions that query `user.roleTemplate.permissions`
- Dynamic permission loading

---

## 🔧 IMPLEMENTATION PATTERN

### BEFORE (Hardcoded)
```python
# Backend
if not current_user.permissions.includes('job.create'):
    raise HTTPException(403, "Permission denied")

# Frontend
const canCreateJob = user.permissions?.includes('job.create')
```

### AFTER (Dynamic)
```python
# Backend
def has_permission(current_user: Users, permission: str) -> bool:
    # Get user's assigned role template
    user_role = db.query(UserRole).filter_by(user_id=current_user.id).first()
    if not user_role or not user_role.role_template:
        return False
    # Check if permission in template's permission array
    return permission in user_role.role_template.permissions

# Frontend
const hasPermission = (user, permission) => {
  if (!user?.roleTemplate?.permissions) return false;
  return user.roleTemplate.permissions.includes(permission);
};
const canCreateJob = hasPermission(user, 'job.create');
```

---

## ✅ VERIFICATION CHECKLIST

After removing hardcoding:
- [ ] Admin can create role templates with custom permissions
- [ ] Admin can assign role template to users
- [ ] User gets permissions from their assigned role template
- [ ] Job Create works for users with 'job.create' permission
- [ ] Navigation shows only screens user has access to
- [ ] No hardcoded permission strings remain in codebase
- [ ] All 17 regression tests pass
- [ ] SuperUser can access everything
- [ ] Other roles limited to their permissions

---

## 📊 FILE REMOVAL MANIFEST

### Will Be Modified/Cleaned
- 22 frontend files (58 occurrences)
- 47 backend files (428 occurrences)

### Critical Dependencies
- `models/rbac.py` - Role and Permission models
- `models/user.py` - User and UserRole models
- `services/rbac_service.py` - RBAC service
- `schemas/rbac.py` - RBAC schemas

---

## ⏰ ESTIMATED TIME

- Phase 1 (Admin/RBAC): 2 hours
- Phase 2 (Core Endpoints): 2 hours
- Phase 3 (Frontend Navigation): 1.5 hours
- Phase 4 (Services/Utils): 1.5 hours
- Testing & Regression Verification: 1 hour
- **Total: ~8 hours**

---

**Status:** Ready to begin Phase 1  
**Priority:** CRITICAL - Blocks all other work  
**Next:** Start with Admin screens remediation

