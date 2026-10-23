# PRIORITY 1: ELIMINATE ALL HARDCODED ROLE CHECKS
## Architectural Mandate - Zero Tolerance

**Status:** 🚨 BLOCKING - 49 instances found across 21 files
**Severity:** CRITICAL_SECURITY
**Owner:** Ruthless Architect (auto-fix on discovery)
**Timeline:** IMMEDIATE (before any feature work)

---

## THE RULE (NON-NEGOTIABLE)

### ❌ FORBIDDEN PATTERN (Delete everywhere)

```python
# WRONG #1: Hardcoded string check
if current_user.UserRole and current_user.UserRole.lower() == "super user":
    pass
else:
    raise HTTPException(403, "Insufficient permissions")

# WRONG #2: get_current_hr_or_admin dependency
def endpoint(user = Depends(get_current_hr_or_admin)):
    pass

# WRONG #3: Hardcoded role list check
if current_user.UserRole not in ["admin", "super user", "manager"]:
    raise HTTPException(403)

# WRONG #4: Mixed hardcoded + role-template
is_super = current_user.UserRole and current_user.UserRole.lower() == "super user"
if not is_super:
    raise HTTPException(403)
```

### ✅ CORRECT PATTERN (Only this)

```python
# CORRECT: Role-template permission dependency
@router.post(
    "/endpoint",
    dependencies=[
        Depends(get_current_internal_user),
        Depends(require_role_template_permission(*Permissions.RESOURCE_ACTION))
    ]
)
def endpoint(db: Session = Depends(get_db)):
    # Permission already validated by FastAPI dependency
    # If you reach here, user has permission
    # No role checks in function body
    pass
```

---

## THE PROBLEM (Why this is PRIORITY 1)

### Current State: 49 Hardcoded Checks

**File: users_access_control.py - 18 instances**
- Lines 353-354, 398-399, 440-441, 514, 552, 591, 669, 707, 746, 864, 902, 937
- All checking hardcoded "super user" string
- Same check repeated 13+ times

**File: finance_monitoring.py - 3 instances**
**File: role_template_permission_service.py - 3 instances**
**File: test_mfa_login_flow.py - 3 instances**
**File: dependencies.py - 3 instances**

**Other files: 1-2 instances each**

### Why This Is Wrong

| Problem | Impact | Risk |
|---------|--------|------|
| **Role name hardcoded** | If "super user" changes to "superuser", code breaks | CRITICAL |
| **Can be bypassed** | Forgot to add check in one endpoint → permission hole | CRITICAL_SECURITY |
| **Not testable** | Need to mock UserRole string, fragile | HIGH |
| **Not reusable** | Copy-paste 49 times across 21 files | MEDIUM |
| **Silent failure** | Check fails, returns 403, but no clear why | HIGH |
| **Maintenance nightmare** | Fix one place, 48 others still broken | MEDIUM |

### Example Attack Scenario

```
Developer adds new endpoint:
  @router.post("/admin/create-user")
  def create_user(...):
      # Forgot to add permission check!
      ...

Attacker calls endpoint:
  POST /admin/create-user
  Response: 200 OK - user created

Attacker: "I'm in!"
Developer: "How?? There's no permission check..."
```

---

## THE FIX (49 instances → 0)

### Strategy: 4-Phase Elimination

**PHASE 1: Stop Writing Hardcoded Checks (Immediate)**
- Architect blocks any new `is_super_user` patterns
- Any `UserRole ==` patterns rejected at code review
- Any `get_current_hr_or_admin` dependencies flagged

**PHASE 2: Fix High-Impact Files (Today)**
- users_access_control.py: 18 → 0
- finance_monitoring.py: 3 → 0
- role_template_permission_service.py: 3 → 0

**PHASE 3: Fix Remaining (This week)**
- Test files: Update test patterns
- Core services: Update dependencies, visibility

**PHASE 4: Architect Learns (Continuous)**
- Every file scanned for pattern
- Every instance recorded in memory
- Confidence: 0.95 (critical rule)

---

## PHASE 1 DETAIL: FIX users_access_control.py (18 instances)

### Instance #1-3: create_business_unit (Lines 342-384)

**CURRENT (WRONG):**
```python
@router.post(
    "/business-units",
    dependencies=[Depends(require_resource_permission("business-unit", "create"))]
    # ← This is WRONG pattern (require_resource_permission, not role-template)
)
def create_business_unit(
    req: BusinessUnitCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    # Line 353-354: HARDCODED CHECK (DELETE)
    is_super_user = (current_user.UserRole and current_user.UserRole.lower() == "super user") or \
                    (hasattr(current_user, 'roles') and any(r.name.lower() == "super user" for r in current_user.roles))

    if not is_super_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions - Super User access required")

    # ... rest of function
```

**CORRECT (APPLY THIS):**
```python
@router.post(
    "/business-units",
    dependencies=[
        Depends(get_current_internal_user),
        Depends(require_role_template_permission(*Permissions.BUSINESS_UNITS_CREATE))
    ]
)
def create_business_unit(
    req: BusinessUnitCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    # DELETE lines 353-357 (the is_super_user check)
    # If you reach here, permission is validated
    
    # Validate input
    if not req.name or not req.display_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Business Unit name and display name are required")

    # ... rest of function (unchanged)
```

### All 18 instances follow same pattern:
1. **DELETE** the hardcoded `is_super_user` check
2. **ADD** `Depends(require_role_template_permission(*Permissions.RESOURCE_ACTION))` to dependencies
3. Function body unchanged (no logic changes)

---

## MAPPING: File → Permissions

```python
# users_access_control.py fix mapping:

# Line 64-69: ✅ ALREADY CORRECT (keep as is)
@router.get("/users", dependencies=[
    Depends(get_current_internal_user),
    Depends(require_role_template_permission(*Permissions.USERS_VIEW))  # ← CORRECT
])

# Line 126-137: create_user
# BEFORE: Line 130 has require_role_template_permission(*Permissions.USERS_CREATE) ✓
# ISSUE: No hardcoded check (good!)
# ACTION: NONE

# Line 195-206: update_user
# BEFORE: Line 199 has require_role_template_permission(*Permissions.USERS_EDIT) ✓
# ISSUE: No hardcoded check (good!)
# ACTION: NONE

# Line 244-278: delete_user
# BEFORE: Line 248 has require_role_template_permission(*Permissions.USERS_DELETE) ✓
# ISSUE: No hardcoded check (good!)
# ACTION: NONE

# Line 290-340: list_business_units
# BEFORE: Line 292 has require_resource_permission("business-unit", "view")
# ISSUE: Should be require_role_template_permission(*Permissions.BUSINESS_UNITS_VIEW)
# ACTION: UPDATE

# Line 342-384: create_business_unit
# BEFORE: Line 344 has require_resource_permission("business-unit", "create")
# ISSUE: Should be require_role_template_permission(*Permissions.BUSINESS_UNITS_CREATE)
# ALSO: Lines 353-357 have hardcoded is_super_user check
# ACTION: UPDATE dependency + DELETE hardcoded check

# ... (pattern continues for all 18 instances)
```

---

## PERMISSIONS MAPPING REQUIRED

```python
# In Permissions enum (core/permission_registry.py):

class Permissions:
    # Users management
    USERS_VIEW = ("administration", "view")
    USERS_CREATE = ("administration", "create")
    USERS_EDIT = ("administration", "edit")
    USERS_DELETE = ("administration", "delete")
    
    # Business Units
    BUSINESS_UNITS_VIEW = ("business_unit", "view")
    BUSINESS_UNITS_CREATE = ("business_unit", "create")
    BUSINESS_UNITS_EDIT = ("business_unit", "edit")
    BUSINESS_UNITS_DELETE = ("business_unit", "delete")
    
    # Delivery Centers
    DELIVERY_CENTERS_VIEW = ("delivery_center", "view")
    DELIVERY_CENTERS_CREATE = ("delivery_center", "create")
    DELIVERY_CENTERS_EDIT = ("delivery_center", "edit")
    DELIVERY_CENTERS_DELETE = ("delivery_center", "delete")
    
    # Organizational Hierarchy
    ORG_HIERARCHY_VIEW = ("organizational_hierarchy", "view")
    ORG_HIERARCHY_CREATE = ("organizational_hierarchy", "create")
    ORG_HIERARCHY_EDIT = ("organizational_hierarchy", "edit")
    ORG_HIERARCHY_DELETE = ("organizational_hierarchy", "delete")
    
    # Role Templates
    ROLE_TEMPLATES_VIEW = ("role_template", "view")
    ROLE_TEMPLATES_CREATE = ("role_template", "create")
    ROLE_TEMPLATES_EDIT = ("role_template", "edit")
    ROLE_TEMPLATES_DELETE = ("role_template", "delete")
```

---

## ARCHITECT LEARNS THIS RULE

**Memory Entry (PRIORITY 1):**

```json
{
    "cycle_number": 999,
    "learning_type": "ARCHITECTURAL_RULE_CRITICAL",
    "content": "PRIORITY 1: Eliminate all hardcoded role checks globally. Pattern: is_super_user, get_current_hr_or_admin, UserRole==string. Replace with require_role_template_permission(*Permissions.RESOURCE_ACTION). Found 49 instances across 21 files.",
    "affected_systems": [
        "backend/app/api/v1/endpoints/users_access_control.py",
        "backend/app/api/v1/endpoints/finance_monitoring.py",
        "backend/app/api/v1/endpoints/jobs/crud.py",
        "backend/app/core/dependencies.py",
        "backend/app/services/rbac_service.py",
        "... (21 files total)"
    ],
    "severity": "CRITICAL_SECURITY",
    "confidence": 0.95,
    "action_items": [
        "Phase 1: Block new hardcoded checks (code review gate)",
        "Phase 2: Fix users_access_control.py (18 instances)",
        "Phase 3: Fix finance_monitoring.py (3 instances)",
        "Phase 4: Fix remaining (2+ instances each)"
    ],
    "blocking": true,
    "no_feature_work_until_fixed": true
}
```

**Architect Mandate:**
- ✅ Auto-reject any code with `is_super_user` pattern
- ✅ Auto-reject any `UserRole ==` string comparisons
- ✅ Auto-flag any `get_current_hr_or_admin` dependencies
- ✅ Find all 49 instances and queue for fix
- ✅ Verify fix with re-scan (49 → 0)

---

## IMPLEMENTATION CHECKLIST

### Day 1 (Today)
- [ ] Code review gate: Reject new hardcoded role patterns
- [ ] Fix users_access_control.py (18 instances)
- [ ] Verify: grep for `is_super_user` in file (should be 0)

### Day 2
- [ ] Fix finance_monitoring.py (3 instances)
- [ ] Fix role_template_permission_service.py (3 instances)

### Day 3-5
- [ ] Fix remaining 13 files (2+ instances each)

### Verification
- [ ] Run: `grep -r "is_super_user" backend/` → should be 0
- [ ] Run: `grep -r "UserRole.*==" backend/` → should be 0
- [ ] Run: `grep -r "get_current_hr_or_admin" backend/` → should be 0
- [ ] All endpoints have `require_role_template_permission` in dependencies
- [ ] No permission logic in function bodies

---

## SUMMARY

**What this means:**

| Before | After |
|--------|-------|
| 49 hardcoded checks | 0 hardcoded checks |
| 21 files with vulnerabilities | 0 files with vulnerabilities |
| Role name changes break code | Role name changes handled in database |
| Permissions scattered across code | Permissions centralized in Permissions enum |
| Hard to audit permissions | Clear audit trail (all in dependencies) |
| **Security Grade: D-** | **Security Grade: A** |

**This is non-negotiable. Architect will enforce this across entire application.**
