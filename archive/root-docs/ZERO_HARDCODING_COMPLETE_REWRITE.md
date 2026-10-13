# ZERO-HARDCODING COMPLETE ARCHITECTURAL REWRITE

**Status:** Planning Phase  
**Scope:** Complete system redesign to eliminate all hardcoded roles/permissions  
**Objective:** 100% admin-driven role and permission management with zero code changes for new roles

---

## Current Architecture (BROKEN)

```
Code (Hardcoded - 92 locations)
├─ app/core/dependencies.py → checks hardcoded role names
├─ app/api/v1/endpoints/*.py → hardcoded permission strings in decorators
├─ app/services/*.py → hardcoded role conditionals in queries
└─ src/screens/*.js → hardcoded role checks for dashboards

Database (Unused)
├─ role_templates table → not used
├─ role_template_permissions → not used
└─ user_roles → not used
```

**Problem:** Adding a role requires changes in 30+ locations
**Problem:** Adding a permission requires code deployment
**Problem:** Admins cannot manage roles/permissions

---

## Target Architecture (CORRECT)

```
Database (Admin-Driven - SINGLE SOURCE OF TRUTH)
├─ modules (Recruitment, Finance, Admin, Workforce)
├─ resources (candidates, jobs, invoices, employees, etc.)
├─ role_templates (CEO, CFO, Partner, Recruiter, HR Manager, etc.)
├─ role_template_permissions (matrix of what each role can do)
├─ users (simple user records)
└─ user_roles (link users to role templates)

Code (Zero Hardcoding - Only Logic)
├─ has_permission(user, resource, action) → queries role_template_permissions
├─ get_user_role(user) → queries user_roles → role_templates
├─ dashboard_for_user(user) → queries permissions → determines access
└─ All decorators use permission keys, NOT hardcoded strings
```

**Benefit:** Add role = 1 insert into role_templates + role_template_permissions  
**Benefit:** Add permission = 1 insert into role_template_permissions  
**Benefit:** Admins manage everything through admin UI  

---

## Phase 1: Backend Foundation Rewrite (Days 1-3)

### 1.1 Remove ALL Hardcoded Role/Permission Checks

**Files to rewrite (12 CRITICAL):**

#### app/core/dependencies.py
Current (Broken):
```python
# Line 265
is_super_user = (
    (user.UserRole and user.UserRole.lower() in ("super user", "admin"))
    or (user.role and user.role.name and user.role.name.lower() in ("super user", "admin"))
)
```

Rewritten (Correct):
```python
# Get user's role template
user_role = db.query(UserRole).filter(UserRole.user_id == user.UserID).first()
role_template = user_role.role_template if user_role else None

# Check if role template grants this action via permissions
def is_super_user(role_template):
    # Super user = has universal wildcard permission or admin.* permissions
    if not role_template:
        return False
    permissions = db.query(RoleTemplatePermission).filter(
        RoleTemplatePermission.role_template_id == role_template.id
    ).all()
    # Check if has any admin.* permission or universal permission
    return any(p.can_view or p.can_create or p.can_edit or p.can_delete for p in permissions)
```

#### app/api/v1/endpoints/role_based_dashboard.py
Current (Broken):
```python
# Line 60 - Hardcoded role check
if current_user.UserRole not in ["Super User", "Admin", "CEO"]:
    raise HTTPException(403, "CEO dashboard access denied")

# Line 92 - Hardcoded role check
if current_user.UserRole not in ["Super User", "Admin", "Recruiter"]:
    raise HTTPException(403, "Recruiter dashboard access denied")
```

Rewritten (Correct):
```python
# No hardcoded checks - use permissions
# Get user's permissions from role template
user_permissions = get_user_permissions(current_user.UserID, db)

# Check if user can view revenue data (which CEO/Finance/Partner roles have)
if not user_permissions.includes("revenue.view"):
    raise HTTPException(403, "Revenue dashboard access denied")

# Return appropriate dashboard based on permissions
if user_permissions.includes("revenue.view_pnl"):
    return get_executive_dashboard(current_user, db)
elif user_permissions.includes("recruitment.manage"):
    return get_recruitment_dashboard(current_user, db)
elif user_permissions.includes("hr.manage"):
    return get_hr_dashboard(current_user, db)
else:
    return get_basic_dashboard(current_user, db)
```

#### app/services/role_based_dashboard_service.py
Current (Broken):
```python
# Lines 38-47 - Hardcoded role name routing
def get_dashboard_for_role(role):
    if role in ["Super User", "Admin", "CEO"]:
        return _ceo_dashboard()
    elif role == "Recruiter":
        return _recruiter_dashboard()
    elif role == "HR Manager":
        return _hr_manager_dashboard()
    elif role == "Finance":
        return _finance_dashboard()
    else:
        return _basic_dashboard()
```

Rewritten (Correct):
```python
# No role name checks - purely permission-based
def get_dashboard_for_user(user_id, db):
    # Get user's permissions from their role template
    permissions = get_user_permissions(user_id, db)
    
    # Determine dashboard based on PERMISSIONS, not role names
    # Permissions come from database, never hardcoded
    
    if permissions.includes("revenue.view_pnl"):
        # User is CEO/CFO/Partner - show executive dashboard
        return {
            "type": "executive",
            "components": ["revenue_summary", "bu_metrics", "alerts"]
        }
    elif permissions.includes("recruitment.manage"):
        # User is recruiter/hiring manager - show recruitment dashboard
        return {
            "type": "recruitment",
            "components": ["pipeline", "candidates", "interviews"]
        }
    elif permissions.includes("hr.manage"):
        # User is HR manager - show HR dashboard
        return {
            "type": "hr",
            "components": ["employees", "timesheets", "benefits"]
        }
    else:
        # Default dashboard
        return {
            "type": "basic",
            "components": ["profile", "my_work"]
        }
```

### 1.2 Update Decorators to Use Permission Keys (Not Hardcoded Strings)

Current (Broken):
```python
# All across app/api/v1/endpoints/*.py
@router.get("/cfo/snapshot", dependencies=[Depends(require_permission("revenue.view_pnl"))])
@router.get("/recruiter/pipeline", dependencies=[Depends(require_permission("recruitment.manage"))])
```

**These are still somewhat hardcoded.** Better approach:

Create `app/config/permissions_registry.py`:
```python
# Centralized permission registry - single source of truth
class PERMISSIONS:
    # Revenue module
    REVENUE_VIEW = "revenue.view"
    REVENUE_VIEW_PNL = "revenue.view_pnl"
    
    # Recruitment module
    RECRUITMENT_VIEW = "recruitment.view"
    RECRUITMENT_MANAGE = "recruitment.manage"
    CANDIDATE_CREATE = "candidate.create"
    CANDIDATE_VIEW = "candidate.view"
    
    # HR module
    HR_VIEW = "hr.view"
    HR_MANAGE = "hr.manage"
    EMPLOYEE_VIEW = "employee.view"
    EMPLOYEE_MANAGE = "employee.manage"
    
    # Admin module
    ADMIN_VIEW = "admin.view"
    ADMIN_MANAGE = "admin.manage"
```

Use in decorators:
```python
from app.config.permissions_registry import PERMISSIONS

@router.get("/cfo/snapshot", dependencies=[Depends(require_permission(PERMISSIONS.REVENUE_VIEW_PNL))])
@router.get("/recruiter/pipeline", dependencies=[Depends(require_permission(PERMISSIONS.RECRUITMENT_MANAGE))])
```

**This is still not perfect** but it centralized the strings. The ultimate goal is:
- Admin UI defines what permissions exist
- Code NEVER knows about permission names
- Code only checks: `has_permission(user, "revenue.view_pnl")`

### 1.3 Rewrite Database Query Filters

Current (Broken):
```python
# app/services/partner_incentive_service.py Line 33
db.query(Users).filter(Users.UserRole == "Partner")

# app/services/expense_service.py Line 168
db.query(Users).filter(Users.UserRole == "Finance")

# app/services/cfo_agent_service.py Line 172
db.query(Users).filter(Users.UserRole == "Partner")
```

Rewritten (Correct):
```python
# Get users with specific permission, not hardcoded role name
def get_users_with_permission(db, permission: str):
    """Get all users who have a specific permission via their role template"""
    return db.query(Users).join(
        UserRole, Users.UserID == UserRole.user_id
    ).join(
        RoleTemplate, UserRole.role_template_id == RoleTemplate.id
    ).join(
        RoleTemplatePermission, RoleTemplate.id == RoleTemplatePermission.role_template_id
    ).join(
        Resource, RoleTemplatePermission.resource_id == Resource.id
    ).filter(
        Resource.name == permission.split(".")[0],  # e.g., "partner"
        (RoleTemplatePermission.can_view == True) | 
        (RoleTemplatePermission.can_create == True) |
        (RoleTemplatePermission.can_edit == True) |
        (RoleTemplatePermission.can_delete == True)
    ).distinct().all()

# Usage (no hardcoded role names)
partner_users = get_users_with_permission(db, "partner.manage")
finance_users = get_users_with_permission(db, "finance.manage")
```

---

## Phase 2: Admin UI Rewrite (Days 3-5)

### 2.1 Create Role Template Management Screen

Features:
- [ ] Create new role template (name, description)
- [ ] Assign permissions to role template (matrix: resource × action)
- [ ] View all role templates
- [ ] Edit role template permissions
- [ ] Delete role template (if not assigned to users)

### 2.2 Create User-to-Role Assignment Screen

Features:
- [ ] View all users
- [ ] Assign user to one or more role templates
- [ ] View current role assignments
- [ ] Revoke role assignments
- [ ] Bulk assign roles

### 2.3 Create Permission Registry UI

Features:
- [ ] View all modules (Recruitment, Finance, HR, Admin, Workforce)
- [ ] View all resources per module
- [ ] View all actions per resource (view, create, edit, delete)
- [ ] Create new permissions (if needed beyond standard CRUD)

---

## Phase 3: Frontend Rebuild (Days 5-7)

### 3.1 Dynamic Dashboard Routing

Current (Broken):
```javascript
// src/screens/Dashboard.js Line 72-85
if (roles.includes("CEO")) {
    window.location.replace("/ceo-fy-progress");
}
if (roles.includes("CFO")) {
    window.location.replace("/cfo-dashboard");
}
```

Rewritten (Correct):
```javascript
// No hardcoded role checks - purely permission-based
const checkPermissionsAndRedirect = async () => {
    try {
        const user = await getHrMe();
        const permissions = user?.permissions || [];
        
        // Determine dashboard based on permissions only
        // No role names in this code
        
        if (permissions.includes("revenue.view_pnl")) {
            // User is executive (CEO, CFO, Partner, etc.)
            // Code doesn't care which role - just has the permission
            window.location.replace("/dashboard/executive");
            return;
        }
        
        if (permissions.includes("recruitment.manage")) {
            window.location.replace("/dashboard/recruitment");
            return;
        }
        
        if (permissions.includes("hr.manage")) {
            window.location.replace("/dashboard/hr");
            return;
        }
        
        // Default dashboard
    } catch (err) {
        console.error("Error checking permissions:", err);
    }
};
```

### 3.2 Dynamic Navigation Rendering

Current (Broken):
```javascript
// src/layout/Shell.js
const NAV_PERMISSIONS = {
    "recruitment": "recruitment.view",
    "employees": "employee.view",
    "finance": "revenue.view",
    "admin": "admin.manage"
};

// Still hardcoded role mappings
if (user.role === "CEO" || user.role === "CFO") {
    showFinanceNav = true;
}
```

Rewritten (Correct):
```javascript
// No hardcoded role checks
// Navigation items shown based purely on permissions
const navItems = [
    { label: "Recruitment", path: "/recruitment", permission: "recruitment.view" },
    { label: "Employees", path: "/employees", permission: "employee.view" },
    { label: "Finance", path: "/finance", permission: "revenue.view" },
    { label: "Admin", path: "/admin", permission: "admin.manage" }
];

// Filter nav items based on user's actual permissions
const visibleItems = navItems.filter(item => 
    user.permissions.includes(item.permission)
);
```

---

## Phase 4: Database Cleanup (Days 7-8)

### 4.1 Migrate Existing Data

```sql
-- Migrate existing users to role templates
INSERT INTO user_roles (user_id, role_template_id, tenant_id)
SELECT u.UserID, rt.id, u.tenant_id
FROM users u
LEFT JOIN role_templates rt ON rt.name = u.UserRole AND rt.tenant_id = u.tenant_id
WHERE u.UserRole IS NOT NULL;

-- Verify migration
SELECT COUNT(*) FROM user_roles;  -- Should match count of users with UserRole
```

### 4.2 Remove Old RBAC Tables (Eventually)

These can stay for backwards compatibility, but new code uses ONLY role templates:
- Old `roles` table (can deprecate)
- Old `role_permissions` table (can deprecate)
- Old `UserRole` string field on users (keep for now, migrate gradually)

---

## Success Criteria

✅ **Zero hardcoded role names in code**
✅ **Zero hardcoded permission strings in code** (except permission registry which is metadata)
✅ **All roles managed via admin UI**
✅ **All permissions managed via admin UI**
✅ **New roles can be created without code deployment**
✅ **New permissions can be added without code deployment**
✅ **Permission checking goes through role templates 100% of the time**
✅ **Dashboard routing based on permissions, not role names**
✅ **Navigation based on permissions, not role names**
✅ **All database queries use permission lookups, not role names**

---

## Implementation Steps Summary

| Phase | Duration | Files Changed | Impact |
|-------|----------|----------------|--------|
| **Phase 1** | 3 days | 23 files | Backend zero-hardcoding |
| **Phase 2** | 2 days | 5 new files | Admin UI for management |
| **Phase 3** | 2 days | 8 files | Frontend dynamic routing |
| **Phase 4** | 1 day | Database migration | Cleanup & optimization |
| **Total** | **8 days** | **~40 files** | **Complete rewrite** |

---

## Risks & Mitigation

| Risk | Mitigation |
|------|-----------|
| Permission check performance | Cache permissions at login, invalidate on role change |
| Admin accidentally breaks access | Validation prevents assigning 0 permissions to active users |
| Role template name changes | All code uses IDs, not names (except UI display) |
| Large permission matrices | Index on (role_template_id, resource_id), lazy-load if needed |

---

## Version Control Strategy

This rewrite should be:
1. Done on a new branch: `feat/zero-hardcoding-rewrite`
2. Small, reviewable PRs:
   - PR1: Dependencies.py rewrite
   - PR2: Service layer queries rewrite
   - PR3: Endpoint decorators cleanup
   - PR4: Dashboard service rewrite
   - PR5: Frontend dashboard rewrite
   - PR6: Admin UI implementation
3. Deployed all at once to avoid inconsistency

---

**This is a comprehensive rewrite, not a patch. It's the right approach.**

