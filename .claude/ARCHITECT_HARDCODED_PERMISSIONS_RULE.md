# Architect Agent: Hardcoded Permission Detection Rule

## Critical Issue: NO Hardcoded User Permission Dependencies

**Severity:** CRITICAL - Blocks entire endpoints silently

**Rule:** Scan all Python files for hardcoded user permission dependencies and flag as CRITICAL violations.

## Patterns to Flag

### ❌ FORBIDDEN - Hardcoded Permission Functions
```python
# These patterns are DEADLY and must be caught:
Depends(get_current_hr_or_admin)
Depends(get_current_admin)
Depends(get_current_recruiter)  
Depends(get_current_candidate)
Depends(get_current_<specific_role>)
```

### ❌ FORBIDDEN - Hardcoded Role Assumptions
```python
# Any endpoint that assumes a specific role instead of checking permissions
def endpoint(user=Depends(get_current_user)):
    if user.role != "HR":  # ← Hardcoded role check
        raise HTTPException(403)
```

### ✅ CORRECT - Dynamic Role-Based Checks
```python
# Correct approaches:
@router.post("/endpoint", dependencies=[Depends(require_resource_permission("resource", "action"))])

def endpoint(user=Depends(get_current_user)):
    # user is generic, permissions from database
```

## Detection Algorithm

For each Python endpoint file:
1. Check all `Depends()` calls for `get_current_*` patterns
2. Flag if `get_current_*` is NOT `get_current_user`
3. Check imports for hardcoded permission functions
4. Scan for role-specific assumptions in code
5. Verify permission checks use `require_resource_permission()` or `require_role_template_permission()`

## Real-World Impact

**Incident: 2026-09-06**
- 26 instances of `get_current_hr_or_admin` found
- Caused silent 500 errors across API
- Affected: auth endpoints, candidates endpoints, tests
- Debugging: 6+ hours
- Root cause: Dependency resolution hang with no error logging

## Escalation Path

If architect agent finds hardcoded permissions:
1. Flag as CRITICAL
2. List all affected endpoints
3. Block merge until corrected
4. Require replacement with dynamic role template checks

## Prevention

Every endpoint review must check:
- [ ] No hardcoded user permission functions in Depends()
- [ ] Permissions come from database via role templates
- [ ] get_current_user only used as generic auth (not role-specific)
