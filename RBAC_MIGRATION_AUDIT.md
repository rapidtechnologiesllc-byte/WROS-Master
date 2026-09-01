# RBAC to RoleTemplate Migration Audit Report

**Date:** 2026-08-31  
**Status:** AUDIT COMPLETE - 25 instances of hardcoded role checks identified  
**Scope:** Complete backend codebase (/backend/app)  
**Priority:** CRITICAL - All hardcoded checks must be replaced with database-driven role templates

---

## Executive Summary

**Current Architecture:**
- Role templates exist in database (role_templates, role_template_permissions tables)
- Permission system exists (PermissionHelper service with database-driven checks)
- BUT: 25 instances of hardcoded role name comparisons still scattered throughout codebase
- These hardcoded checks bypass the role template system and create maintenance burden

**Migration Goal:**
Replace ALL hardcoded role checks with database-driven role template queries. Users should never be assigned to hardcoded role names; all permissions should flow from role_template table.

**Impact Radius:**
- 25 hardcoded checks across 10 files
- 3 deprecated RBAC services still in use
- 1 visibility.py file with hardcoded org-level roles
- Multiple services still using legacy UserRole field for access control

---

## Critical Issues Found

### Issue 1: Hardcoded Role Checks Block Role Template Migration
**Severity:** CRITICAL  
**Impact:** Cannot fully migrate to role templates while hardcoded checks exist

When users are assigned a role like "CEO" or "Partner", the system should:
1. ✅ Query role_templates table for role with name="CEO"
2. ✅ Query role_template_permissions for that role's permissions
3. ✅ Grant access based on database permissions

**BUT it currently does:**
1. ❌ Hardcoded check: `if current_user.UserRole == "CEO"`
2. ❌ No database query
3. ❌ If role template doesn't exist, hardcoded check still succeeds (WRONG!)
4. ❌ Maintenance nightmare: adding new roles requires code changes, not just DB changes

---

## Detailed Findings

### CATEGORY A: API Endpoints with Hardcoded Checks (6 files)

#### 1. `/c/dev/WROS-Master/backend/app/api/v1/endpoints/finance_monitoring.py`

**Lines 36, 51, 75, 98, 113:** CEO/Partner/BU_HEAD role checks

```python
# CURRENT (Line 36) - HARDCODED
if user and user.UserRole == "CEO":
    bus = db.query(BusinessUnit).filter(BusinessUnit.tenant_id == tenant_id).all()
    return [bu.id for bu in bus]

# SHOULD BE (using role templates)
from app.services.permission_helper import PermissionHelper
if PermissionHelper.has_permission(user.UserID, "admin.manage", db, tenant_id):
    bus = db.query(BusinessUnit).filter(BusinessUnit.tenant_id == tenant_id).all()
    return [bu.id for bu in bus]
```

**Problems:**
- Line 36: Checks if user.UserRole == "CEO" (hardcoded)
- Line 51: Same hardcoded CEO check
- Line 75: if current_user.UserRole == "CEO" (hardcoded)
- Line 78: Query filter Users.UserRole == "Partner" (hardcoded - returns wrong users!)
- Line 98: elif current_user.UserRole == "Partner" (hardcoded)
- Line 113: elif current_user.UserRole == "BU_HEAD" or current_user.business_unit_id

**Fix Required:**
Replace all 6 instances with PermissionHelper.has_permission() checks:
```python
# Instead of: if user.UserRole == "CEO"
# Use: if PermissionHelper.has_permission(user.UserID, "admin.manage", db, tenant_id)

# Instead of: Users.UserRole == "Partner"
# Use: Query role_template for "Partner" role, then check via RoleTemplate relationship
```

**Impact:** Finance dashboard won't work correctly for users with role templates

---

#### 2. `/c/dev/WROS-Master/backend/app/api/v1/endpoints/users_access_control.py`

**Lines 312, 354, 393, 532, 675, 852:** Super User role checks

```python
# CURRENT (Line 312) - HARDCODED
is_super_user = (current_user.UserRole and current_user.UserRole.lower() == "super user") or \
                PermissionHelper.is_super_admin(current_user.UserID, db, tenant_id)

# SHOULD BE (already partially fixed!)
is_super_user = PermissionHelper.is_super_admin(current_user.UserID, db, tenant_id)
```

**Problems:**
- Lines 312, 354, 393: Checking both hardcoded UserRole AND PermissionHelper (redundant!)
- Lines 532, 675, 852: Same redundant dual-check pattern
- Hardcoded "super user" string appears 6 times

**Fix Required:**
Remove hardcoded checks, keep only PermissionHelper call:
```python
# Remove: is_super_user = (current_user.UserRole and current_user.UserRole.lower() == "super user") or ...
# Keep only: is_super_user = PermissionHelper.is_super_admin(current_user.UserID, db, tenant_id)
```

**Impact:** Users without UserRole set won't be recognized as admins even if they have admin permissions

---

### CATEGORY B: Service Layer Hardcoded Checks (7 files)

#### 3. `/c/dev/WROS-Master/backend/app/services/finance_agent.py`

**Line 194:** Partner role check

```python
# CURRENT - HARDCODED
Users.UserRole == "Partner"

# SHOULD BE
# Query: db.query(RoleTemplate).filter(RoleTemplate.name == "Partner").first()
# Then: check if user has that role via UserRoles junction table
```

**Problems:**
- Hardcoded comparison
- Doesn't check if role template exists
- Query filtering relies on UserRole field (legacy)

---

#### 4. `/c/dev/WROS-Master/backend/app/services/agent_pyramid_reporting.py`

**Lines 460, 473, 483, 777:** Multiple hardcoded checks

```python
# CURRENT (Line 460) - HARDCODED
db.query(Users.UserID).filter(Users.UserRoleID == bu_id)  # WRONG - UserRoleID doesn't exist!

# CURRENT (Line 777) - HARDCODED
Users.UserRole == "Partner"

# SHOULD BE
# Line 460-483: Query via user_roles junction table (many-to-many)
db.query(Users.UserID).join(UserRoles).filter(UserRoles.role_id == partner_role_template.id)

# Line 777: Check via role template
role = db.query(RoleTemplate).filter(RoleTemplate.name == "Partner").first()
users_with_partner_role = db.query(Users).join(UserRoles).filter(UserRoles.role_id == role.id)
```

**Problems:**
- Lines 460, 473, 483: Use non-existent UserRoleID field (BUG!)
- Line 777: Hardcoded role check
- Breaks reporting pipeline when users have multiple roles

---

#### 5. `/c/dev/WROS-Master/backend/app/services/operational_accountability_agents.py`

**Line 154:** Multiple roles in query

```python
# CURRENT - HARDCODED
Users.UserRole.in_(["Partner", "BU Head"])

# SHOULD BE
# Query: Get Partner and BU Head role templates
partner_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Partner").first()
bu_head_role = db.query(RoleTemplate).filter(RoleTemplate.name == "BU Head").first()

# Then join via UserRoles: users with either role
users = db.query(Users).join(UserRoles).filter(
    UserRoles.role_id.in_([partner_role.id, bu_head_role.id])
)
```

**Problems:**
- Hardcoded list of role names
- Won't find users with role templates (only UserRole field)
- Doesn't handle custom roles

---

#### 6. `/c/dev/WROS-Master/backend/app/services/personal_goal_agents.py`

**Line 153:** Recruiter role check

```python
# CURRENT - HARDCODED
Users.UserRole == "Recruiter"

# SHOULD BE
recruiter_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Recruiter").first()
users = db.query(Users).join(UserRoles).filter(UserRoles.role_id == recruiter_role.id)
```

---

#### 7. `/c/dev/WROS-Master/backend/app/services/recruiter_assignment_service.py`

**Lines 18, 36:** HR Manager and Recruiter checks

```python
# CURRENT - HARDCODED (appears twice)
Users.UserRole.in_(["HR Manager", "Recruiter"])

# SHOULD BE
hr_role = db.query(RoleTemplate).filter(RoleTemplate.name == "HR Manager").first()
recruiter_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Recruiter").first()
users = db.query(Users).join(UserRoles).filter(
    UserRoles.role_id.in_([hr_role.id, recruiter_role.id])
)
```

---

#### 8. `/c/dev/WROS-Master/backend/app/services/thunder_autonomous_loop.py`

**Lines 69, 75:** Super User and Admin checks

```python
# CURRENT - HARDCODED (lines 69, 75)
Users.UserRole == "Super User"
Users.UserRole.ilike("%admin%")

# SHOULD BE
super_user_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Super User").first()
admin_roles = db.query(RoleTemplate).filter(RoleTemplate.name.ilike("%admin%")).all()
users = db.query(Users).join(UserRoles).filter(
    UserRoles.role_id.in_([super_user_role.id] + [r.id for r in admin_roles])
)
```

---

### CATEGORY C: Core Infrastructure with Hardcoded Roles (1 file)

#### 9. `/c/dev/WROS-Master/backend/app/core/visibility.py`

**Line 20:** Hardcoded org-level roles set

```python
# CURRENT - HARDCODED
org_level_roles = {"super user", "admin", "ceo", "cfo"}

# Line 23: Check legacy UserRole field
if user.UserRole and user.UserRole.lower() in org_level_roles:
    return True

# Line 27: Also checks role.name (better, but still hardcoded names)
if user.role and user.role.name and user.role.name.lower() in org_level_roles:
    return True

# SHOULD BE
# Query database for which roles have "can_see_global_data" permission
admin_manage_perm = db.query(Resource).filter(Resource.name == "admin").first()
global_roles = db.query(RoleTemplate).join(RoleTemplatePermission).filter(
    RoleTemplatePermission.resource_id == admin_manage_perm.id,
    RoleTemplatePermission.can_edit == True
).all()

# Check if user has any of those roles
user_has_global = db.query(UserRoles).filter(
    UserRoles.user_id == user.UserID,
    UserRoles.role_id.in_([r.id for r in global_roles])
).first() is not None
```

**Problems:**
- Hardcoded set of org-level role names
- Won't automatically include new org-level roles added to database
- Maintains two different hardcoded lists (legacy UserRole and modern role.name)
- Can't be configured without code changes

**Impact:** Adding a new org-level role (like CFO, CISO) requires code change AND database change

---

#### 10. `/c/dev/WROS-Master/backend/app/core/mfa.py`

**Line 11 (comment):** Hardcoded role alias documentation

```python
# CURRENT (comment-only, not blocking but important)
# Super User = full-bypass admin equivalent; BU Head = the...

# SHOULD BE (no code change, just document that roles come from role_templates table)
# All roles defined in role_templates table. Super User grants admin.manage permission.
# BU Head grants business_unit.manage permission scoped to assigned BU.
```

**Impact:** Documentation misleading - implies hardcoded role equivalency

---

### CATEGORY D: Deprecated RBAC Services Still in Use

#### 11. `/c/dev/WROS-Master/backend/app/services/rbac_service_deprecated.py`

**Status:** Deprecated but still imported in 20+ files

**Problems:**
- File named "deprecated" but still actively used
- Contains hardcoded ROLES_SEED and ROLE_ATTRIBUTES_SEED (lines 25-99)
- Has unused old permission model (doesn't use role_templates)
- Creates technical debt and confusion

**Files importing this deprecated service:**
- `/c/dev/WROS-Master/backend/app/api/v1/endpoints/rbac.py`
- `/c/dev/WROS-Master/backend/app/api/v1/endpoints/agents.py`
- `/c/dev/WROS-Master/backend/app/api/v1/endpoints/agent_standups_dashboard.py`
- `/c/dev/WROS-Master/backend/app/services/candidate_isolation_service.py`
- `/c/dev/WROS-Master/backend/app/services/error_log_service.py`
- And 15+ more files

**Fix Required:**
1. Don't import rbac_service_deprecated
2. Use PermissionHelper instead
3. Remove the "_deprecated" file after migration complete

---

## Complete Migration Map

### Table: Hardcoded Role Checks Requiring Replacement

| File Path | Line(s) | Hardcoded Check | Replacement Strategy |
|-----------|---------|-----------------|----------------------|
| finance_monitoring.py | 36, 51 | `UserRole == "CEO"` | `has_permission("admin.manage")` |
| finance_monitoring.py | 75, 98 | `UserRole == "CEO"` / `== "Partner"` | `has_permission()` or role template query |
| finance_monitoring.py | 78 | `Users.UserRole == "Partner"` | Query role_templates, join UserRoles |
| finance_monitoring.py | 113 | `UserRole == "BU_HEAD"` | Query BU Head role template |
| users_access_control.py | 312, 354, 393 | `UserRole == "super user"` (redundant) | Remove hardcoded, keep only PermissionHelper |
| users_access_control.py | 532, 675, 852 | Same redundant pattern | Same fix |
| finance_agent.py | 194 | `Users.UserRole == "Partner"` | Query role_templates + UserRoles join |
| agent_pyramid_reporting.py | 460, 473, 483 | `Users.UserRoleID == bu_id` (WRONG FIELD!) | Fix: Query UserRoles junction table |
| agent_pyramid_reporting.py | 777 | `Users.UserRole == "Partner"` | Query role_templates + UserRoles join |
| operational_accountability_agents.py | 154 | `Users.UserRole.in_(["Partner", "BU Head"])` | Query multiple role_templates, join UserRoles |
| personal_goal_agents.py | 153 | `Users.UserRole == "Recruiter"` | Query role_templates + UserRoles join |
| recruiter_assignment_service.py | 18, 36 | `Users.UserRole.in_(["HR Manager", "Recruiter"])` | Query role_templates, join UserRoles |
| thunder_autonomous_loop.py | 69, 75 | `Users.UserRole == "Super User"` / `ilike("%admin%")` | Query role_templates, join UserRoles |
| visibility.py | 20-30 | `org_level_roles = {"super user", "admin", "ceo", "cfo"}` | Query role_templates for global data permission |

---

## Implementation Priority

### PRIORITY 1: CRITICAL (Blocks role template migration)

1. **finance_monitoring.py** (Lines 36-113)
   - Affects finance dashboard
   - Used in daily operations
   - 6 hardcoded checks
   - Time: 1 hour

2. **visibility.py** (Lines 20-30)
   - Affects data scoping system-wide
   - Blocks adding new org-level roles
   - Affects all users
   - Time: 45 minutes

3. **users_access_control.py** (Lines 312-852)
   - Affects admin operations
   - Redundant dual-checks
   - 6 locations
   - Time: 30 minutes

### PRIORITY 2: HIGH (Affects data queries)

4. **agent_pyramid_reporting.py** (Lines 460-777)
   - BUG: Uses non-existent UserRoleID field
   - Affects reporting pipeline
   - 4 hardcoded checks
   - Time: 1 hour

5. **recruiter_assignment_service.py** (Lines 18, 36)
   - Affects recruiter queries
   - Used in Thunder recruitment flow
   - 2 locations (but same pattern)
   - Time: 30 minutes

6. **operational_accountability_agents.py** (Line 154)
   - Affects accountability reporting
   - Won't find users with role templates
   - Time: 30 minutes

### PRIORITY 3: MEDIUM (Affects specific services)

7. **finance_agent.py** (Line 194)
   - Affects finance service
   - Time: 15 minutes

8. **personal_goal_agents.py** (Line 153)
   - Affects goal tracking
   - Time: 15 minutes

9. **thunder_autonomous_loop.py** (Lines 69, 75)
   - Affects Thunder recruitment automation
   - Time: 30 minutes

### PRIORITY 4: LOW (Clean up, not blocking)

10. **rbac_service_deprecated.py**
    - Remove after all imports eliminated
    - 20+ files to update
    - Time: 2 hours

---

## Database Schema Alignment

### Current Database Structure (Correct - Use This!)

```sql
-- Role Templates (source of truth)
role_templates
  - id (PRIMARY KEY)
  - name (e.g., "CEO", "Partner", "HR Manager")
  - hierarchy_level
  - specialization
  - enabled
  - tenant_id

-- Role Template Permissions (what each role can do)
role_template_permissions
  - id
  - role_template_id (FK)
  - resource_id (FK)
  - can_view, can_create, can_edit, can_delete (BOOLEAN)

-- User Role Assignment (many-to-many)
user_roles
  - id
  - user_id (FK to users)
  - role_id (FK to role_templates)  <-- THIS IS THE KEY!
  - business_unit_id

-- Resources (what users can access)
resources
  - id
  - module_id
  - name (e.g., "candidates", "invoices", "admin")
  - display_name
```

### Current User Model Structure (Legacy - Migrate Away)

```sql
-- users table (LEGACY FIELD - BEING PHASED OUT)
users
  - UserID (PRIMARY KEY)
  - UserRole (TEXT) -- "CEO", "Partner", etc. -- THIS IS HARDCODED, REMOVE IT!
  - role_template_id (FK to role_templates) -- NEW, use this instead
  - business_unit_id
```

**KEY INSIGHT:** Users should have:
- `role_template_id` pointing to their primary role template
- `user_roles` junction table entries for all assigned roles
- NOT `UserRole` text field (legacy, maintenance nightmare)

---

## Query Pattern Changes

### OLD PATTERN (Hardcoded - WRONG)
```python
# DON'T DO THIS:
partners = db.query(Users).filter(Users.UserRole == "Partner").all()
```

### NEW PATTERN (Database-driven - CORRECT)
```python
# DO THIS INSTEAD:
from app.models.role_template import RoleTemplate
from app.models.user import UserRoles

partner_role = db.query(RoleTemplate).filter(
    RoleTemplate.name == "Partner",
    RoleTemplate.tenant_id == tenant_id
).first()

if not partner_role:
    # Role template doesn't exist in database - fail gracefully
    partners = []
else:
    # Query users who have this role
    partners = db.query(Users).join(
        UserRoles
    ).filter(
        UserRoles.role_id == partner_role.id,
        Users.tenant_id == tenant_id
    ).all()
```

### PERMISSION CHECK PATTERN (OLD)
```python
# DON'T DO THIS:
if current_user.UserRole == "CEO":
    # Grant access
```

### PERMISSION CHECK PATTERN (NEW)
```python
# DO THIS INSTEAD:
from app.services.permission_helper import PermissionHelper

if PermissionHelper.has_permission(current_user.UserID, "admin.manage", db, tenant_id):
    # Grant access
# OR for multiple permissions:
if PermissionHelper.has_any_permission(
    current_user.UserID,
    ["admin.manage", "admin.edit"],
    db,
    tenant_id
):
    # Grant access
```

---

## Benefits of This Migration

| Benefit | Current (Hardcoded) | After Migration (Database-Driven) |
|---------|-------------------|----------------------------------|
| Add new role | Code change + deploy | Database change only |
| Add new permission | Code change + deploy | Database change only |
| Change role permissions | Code change + deploy | Database change only |
| Custom roles | Impossible | Supported natively |
| Role templates in UI | Can't edit | Full CRUD UI possible |
| Multi-role users | Hack-y if/else chains | Native support via UserRoles junction |
| Audit trail | Manual logging | Database records everything |
| Testing | Mock role names | Real database roles |

---

## Implementation Checklist

### Phase 1: Prepare (30 min)
- [ ] Create PR for RBAC migration changes
- [ ] Set up test database with role templates
- [ ] Write unit tests for PermissionHelper queries
- [ ] Document all hardcoded role names in code

### Phase 2: Critical Path (4 hours)
- [ ] Fix finance_monitoring.py (1 hour)
- [ ] Fix visibility.py (45 min)
- [ ] Fix users_access_control.py (30 min)
- [ ] Fix agent_pyramid_reporting.py (1 hour)
- [ ] Fix recruiter_assignment_service.py (30 min)
- [ ] Test finance dashboard end-to-end

### Phase 3: High Priority (2 hours)
- [ ] Fix operational_accountability_agents.py (30 min)
- [ ] Fix finance_agent.py (15 min)
- [ ] Fix personal_goal_agents.py (15 min)
- [ ] Fix thunder_autonomous_loop.py (30 min)

### Phase 4: Cleanup (2 hours)
- [ ] Audit all imports of rbac_service_deprecated
- [ ] Update each file to use PermissionHelper instead
- [ ] Delete rbac_service_deprecated.py
- [ ] Run full test suite

### Phase 5: Verification (1 hour)
- [ ] Integration tests: users with role templates work
- [ ] Integration tests: finance dashboard works
- [ ] Integration tests: recruiter queries return correct users
- [ ] Verify no hardcoded role checks remain (grep -r "UserRole.*==" /)

### Phase 6: Deployment (1 hour)
- [ ] Deploy to staging
- [ ] Smoke test all affected endpoints
- [ ] Deploy to production
- [ ] Monitor for errors

---

## Risk Assessment

### High Risk (If Not Done)
1. **New roles can't be added without code changes** - Business blocked
2. **Multi-role users not supported** - Blocks RBAC feature completeness
3. **Tech debt accumulates** - Harder to maintain as codebase grows
4. **Security inconsistency** - Some checks via permissions, some via hardcode

### Mitigation Strategies
1. Add linter rule to catch new hardcoded role checks
2. Require database migration for any role changes
3. Code review checklist: "No UserRole == checks allowed"
4. Automated tests verify role template consistency

---

## Files Requiring Changes

### CRITICAL (Must fix for migration to complete)
1. `/c/dev/WROS-Master/backend/app/api/v1/endpoints/finance_monitoring.py` (6 changes)
2. `/c/dev/WROS-Master/backend/app/core/visibility.py` (10 changes)
3. `/c/dev/WROS-Master/backend/app/api/v1/endpoints/users_access_control.py` (6 changes)

### HIGH (Breaks data queries)
4. `/c/dev/WROS-Master/backend/app/services/agent_pyramid_reporting.py` (4 changes)
5. `/c/dev/WROS-Master/backend/app/services/recruiter_assignment_service.py` (2 changes)
6. `/c/dev/WROS-Master/backend/app/services/operational_accountability_agents.py` (1 change)

### MEDIUM (Affects specific features)
7. `/c/dev/WROS-Master/backend/app/services/finance_agent.py` (1 change)
8. `/c/dev/WROS-Master/backend/app/services/personal_goal_agents.py` (1 change)
9. `/c/dev/WROS-Master/backend/app/services/thunder_autonomous_loop.py` (2 changes)

### LOW (Cleanup)
10. `/c/dev/WROS-Master/backend/app/services/rbac_service_deprecated.py` (deprecate/remove)
11. All files importing rbac_service_deprecated (20+ files)

---

## Code Review Checklist

When reviewing RBAC migration PRs, verify:

- [ ] No new `Users.UserRole == ` checks
- [ ] No new hardcoded role name strings (except in PermissionHelper)
- [ ] All role queries use `db.query(RoleTemplate)`
- [ ] All permission checks use `PermissionHelper.has_permission()`
- [ ] All user role queries use `UserRoles` junction table
- [ ] New roles added to database, not hardcoded
- [ ] Tests verify role template queries work
- [ ] No imports of rbac_service_deprecated (unless in cleanup commit)
- [ ] Comments updated to reference database-driven RBAC

---

## Success Criteria

Migration is complete when:

✅ 0 hardcoded role checks remain in production code  
✅ All role queries use role_templates table  
✅ All permission checks use PermissionHelper  
✅ Users can be assigned multiple roles via UserRoles table  
✅ New roles can be added via database without code changes  
✅ Role permissions can be changed via database without code changes  
✅ rbac_service_deprecated is removed  
✅ All tests pass  
✅ finance_monitoring.py works with role templates  
✅ visibility.py determines org-level roles from database  

---

## Conclusion

The RBAC migration audit is complete. **25 hardcoded role checks** identified across **10 files** must be replaced with database-driven role template queries. The good news: the infrastructure is already in place (role_templates table, PermissionHelper service). This is now a systematic refactoring effort to eliminate technical debt.

**Estimated effort:** 8-10 hours total  
**Business impact:** Unblocks role template management, supports multi-role users, eliminates code-based role maintenance  
**Recommended start:** After current sprint, assign to senior backend engineer  

