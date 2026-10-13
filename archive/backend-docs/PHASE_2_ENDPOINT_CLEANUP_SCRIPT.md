# Phase 2 Endpoint Cleanup Script

## Overview
This document provides the systematic approach to fix all remaining hardcoded role checks in endpoints.

## Pattern Template

### BEFORE (Hardcoded - Remove This)
```python
from app.core.dependencies import get_current_internal_user

@router.get("/endpoint", dependencies=[Depends(require_permission("admin.view"))])
def endpoint_handler(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    if current_user.UserRole not in ["Super User", "Admin", "CEO"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only CEO/Super User can access this"
        )
    # ... rest of handler
```

### AFTER (Permission-Based - Use This)
```python
from app.core.dependencies import get_current_internal_user
from app.services.rbac_service import RBACService  # ADD THIS IMPORT

@router.get("/endpoint", dependencies=[Depends(require_permission("admin.view"))])
def endpoint_handler(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    # REPLACE hardcoded check with permission check
    if not RBACService.has_any_permission(db, current_user.UserID, ["admin.manage"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    # ... rest of handler
```

## Role to Permission Mapping

```python
# Use this mapping when converting hardcoded role checks:

ROLE_TO_PERMISSIONS = {
    "Super User": ["admin.manage"],
    "Admin": ["admin.manage"],
    "CEO": ["admin.manage", "revenue.manage"],
    "CFO": ["revenue.manage"],
    "Finance": ["revenue.manage"],
    "BU Head": ["business_unit.manage"],
    "Partner": ["business_unit.manage"],
    "HR Manager": ["employee.manage"],
    "Recruiter": ["recruitment.manage"],
}

# When you see:
if current_user.UserRole in ["Super User", "Admin", "CEO"]:
    # Use:
    if RBACService.has_any_permission(db, current_user.UserID, ["admin.manage"]):

if current_user.UserRole in ["Finance", "CFO"]:
    # Use:
    if RBACService.has_permission(db, current_user.UserID, "revenue.manage"):

if current_user.UserRole in ["BU Head", "Partner"]:
    # Use:
    if RBACService.has_permission(db, current_user.UserID, "business_unit.manage"):
```

## Files to Fix (Priority Order)

### CRITICAL (Admin/CEO dashboards)
1. **agent_standups_dashboard.py** - Lines 28, 86
   - Pattern: `["Super User", "Admin", "CEO"]` → `["admin.manage"]`
   - Check for viewer_role references (line 48) - can remove/refactor

2. **agent_state_dashboard.py** - Multiple locations
   - Pattern: CEO/Admin only checks → `admin.manage`

3. **business_metrics.py** - Multiple locations
   - Pattern: CFO/Finance checks → `revenue.manage`

4. **role_based_dashboard.py** - Role-based dashboard rendering
   - Pattern: Render different views based on role → render based on permissions

### HIGH (Core functionality)
5. **rbac.py** - RBAC management endpoints
   - Pattern: Admin-only operations → `admin.manage` + `rbac.manage`

6. **rbac_templates.py** - Role template management
   - Pattern: Admin-only → `admin.manage`

7. **users.py** - User management endpoints
   - Pattern: User creation/deletion → `admin.manage` or `employee.manage`

### MEDIUM (Workflows)
8. **interviews.py** - Interview scheduling
   - Pattern: HR/Recruiter checks → `recruitment.manage`

9. **create_job.py** - Job creation
   - Pattern: HR/Partner/BU Head → `recruitment.manage` or `business_unit.manage`

10. **onboarding.py** - Onboarding workflows
    - Pattern: HR/Manager checks → `employee.manage`

### LOW (Other references)
- auth.py (comment only)
- mfa.py (if has hardcoded checks)
- Others with minimal hardcoding

## Automated Fix Script (Python)

Create this script to apply fixes semi-automatically:

```python
#!/usr/bin/env python3
"""
Semi-automated endpoint cleanup script.
Finds hardcoded role checks and suggests/applies fixes.
"""

import re
import sys
from pathlib import Path

ROLE_MAPPINGS = {
    r'\["Super User"\s*,\s*"Admin"\s*,\s*"CEO"\]': '["admin.manage"]',
    r'\["Super User"\s*,\s*"Admin"\]': '["admin.manage"]',
    r'\["Finance"\s*,\s*"CFO"\]': '["revenue.manage"]',
    r'\["BU Head"\s*,\s*"Partner"\]': '["business_unit.manage"]',
    r'\["HR Manager"\]': '["employee.manage"]',
    r'\["Recruiter"\]': '["recruitment.manage"]',
}

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    original = content
    
    # Fix imports
    if 'RBACService' not in content and 'if current_user.UserRole' in content:
        # Add import after other imports
        content = re.sub(
            r'(from app\.models\.user import Users)',
            r'\1\nfrom app.services.rbac_service import RBACService',
            content
        )
    
    # Fix role checks
    for pattern, replacement in ROLE_MAPPINGS.items():
        content = re.sub(
            rf'if current_user\.UserRole not in {pattern}:',
            f'if not RBACService.has_any_permission(db, current_user.UserID, {replacement}):',
            content
        )
        content = re.sub(
            rf'if current_user\.UserRole in {pattern}:',
            f'if RBACService.has_any_permission(db, current_user.UserID, {replacement}):',
            content
        )
    
    if content != original:
        print(f"Fixing {filepath}")
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False

if __name__ == '__main__':
    endpoints_dir = Path('app/api/v1/endpoints')
    fixed_count = 0
    
    for file in endpoints_dir.glob('*.py'):
        if fix_file(file):
            fixed_count += 1
    
    print(f"\nFixed {fixed_count} files")
```

## Manual Fixes (if automated won't work)

For each file with hardcoded checks:

1. Open the file
2. Find lines with `if current_user.UserRole`
3. Add import: `from app.services.rbac_service import RBACService`
4. Replace the if condition using the mapping above
5. Test locally
6. Commit with clear message: `refactor: Remove hardcoded role checks from {filename}`

## Verification Checklist

After fixing each file:

- [ ] Import RBACService added
- [ ] All `current_user.UserRole` checks replaced
- [ ] Permissions used match decorators (decorator permission ≥ body permission)
- [ ] No references to hardcoded role names in logic
- [ ] File compiles without syntax errors
- [ ] Endpoint still returns 403 for unauthorized users
- [ ] Authorized users still have access

## Completion Criteria

✅ Phase 2 Complete when:
- [ ] All hardcoded role checks removed from endpoints
- [ ] All service files use permission-based logic
- [ ] Database migration applied (candidate isolation columns)
- [ ] Candidate queries integrated with isolation service
- [ ] All tests passing
- [ ] Zero hardcoded role names or permissions in codebase

## Timeline

**Estimated Effort:**
- Automated script approach: 30-45 minutes
- Manual file-by-file approach: 2-3 hours
- Testing + verification: 1-2 hours

**Total to 100% completion: 2-5 hours depending on approach**
