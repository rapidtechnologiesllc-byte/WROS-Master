# GitHub Issue Validation Report - Top 20 Priority Issues
**Generated:** 2026-09-02  
**Validation Scope:** Issues #217, #247-249, #235, #309, #174, #315, #311, #274, #282, #284, #147, #187, #191, #277, #352, #349, #102, #326

---

## VALIDATION METHODOLOGY

For each issue, I will:
1. **Read the actual code** - Verify if the problem exists in current state
2. **Check git history** - Identify if already fixed/partially fixed
3. **Look for duplicates** - Cross-reference with other issues
4. **Determine current status** - Real issue vs false positive
5. **Verify with code snippet** - Show proof of issue existence or resolution

---

## ISSUE #217 - role_templates.py: Add RBAC checks to 11 endpoints

**Status:** LIKELY FALSE POSITIVE - Most or all checks appear to be in place

**Current Code State:**
```python
# Line 61-62 - GET /role-templates (list)
@router.get("")
    dependencies=[Depends(require_resource_permission("unknown", "view"))]
def list_role_templates(...)

# Line 105-106 - GET /role-templates/{id} (get)
@router.get("/{template_id}")
    dependencies=[Depends(require_resource_permission("{template_id}", "view"))]

# Similar pattern for POST (create), PUT (update), DELETE (delete)
# All 11+ endpoints have dependencies=[Depends(require_resource_permission(...))]
```

**Problem Identified:** `require_resource_permission` is NOT imported in this file

**Code to verify:**
