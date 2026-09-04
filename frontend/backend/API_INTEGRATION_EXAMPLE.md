# Phase 3: API Integration Example

This document shows how to integrate the new permission system into existing endpoints.

## Pattern 1: Simple Permission Check + Data Scope

### Before:
```python
@router.get("/candidates")
async def get_candidates(db: Session = Depends(get_db),
                        current_user: Users = Depends(get_current_internal_user)):
    """Get all candidates - NO PERMISSION CHECK"""
    return db.query(Candidate).filter(
        Candidate.tenant_id == current_user.tenant_id
    ).all()
```

### After:
```python
from app.core.permission_decorators import require_permission, apply_data_scope
from app.services.permission_service import PermissionService

@router.get("/candidates")
@require_permission("candidate.view")
@apply_data_scope("candidates")
async def get_candidates(db: Session = Depends(get_db),
                        current_user: Users = Depends(get_current_internal_user),
                        data_scope: dict = None):
    """Get candidates visible to this user (permission + scope checked)"""
    query = db.query(Candidate).filter(
        Candidate.tenant_id == current_user.tenant_id
    )
    
    # Apply data scope filter
    return PermissionService.apply_data_scope_filter(
        query, data_scope, Candidate
    ).all()
```

## Pattern 2: Delete with Permission

### Before:
```python
@router.delete("/candidates/{candidate_id}")
async def delete_candidate(candidate_id: str,
                          db: Session = Depends(get_db),
                          current_user: Users = Depends(get_current_internal_user)):
    """Delete candidate - NO PERMISSION CHECK"""
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == candidate_id
    ).first()
    
    db.delete(candidate)
    db.commit()
    return {"status": "deleted"}
```

### After:
```python
@router.delete("/candidates/{candidate_id}")
@require_permission("candidate.delete")
async def delete_candidate(candidate_id: str,
                          db: Session = Depends(get_db),
                          current_user: Users = Depends(get_current_internal_user)):
    """Delete candidate (only if user has permission)"""
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == candidate_id,
        Candidate.tenant_id == current_user.tenant_id
    ).first()
    
    if not candidate:
        raise HTTPException(status_code=404)
    
    db.delete(candidate)
    db.commit()
    return {"status": "deleted"}
```

## Pattern 3: Field Masking in Response

### Before:
```python
def serialize_employee(emp):
    return {
        "id": emp.id,
        "name": emp.name,
        "email": emp.email,
        "salary": emp.salary,  # EXPOSED TO EVERYONE
        "ssn": emp.ssn,         # EXPOSED TO EVERYONE
    }
```

### After:
```python
from app.core.permission_decorators import mask_field

def serialize_employee(emp, db, user_id, tenant_id):
    return {
        "id": emp.id,
        "name": emp.name,
        "email": emp.email,
        "salary": mask_field(db, user_id, "employees", "salary", emp.salary, tenant_id),
        "ssn": mask_field(db, user_id, "employees", "ssn", emp.ssn, tenant_id),
    }

# Usage:
@router.get("/employees/{emp_id}")
@require_permission("employee.view")
async def get_employee(emp_id: str,
                       db: Session = Depends(get_db),
                       current_user: Users = Depends(get_current_internal_user)):
    emp = db.query(Employee).filter(Employee.id == emp_id).first()
    return serialize_employee(emp, db, current_user.UserID, current_user.tenant_id)
```

## Pattern 4: Module-Level Scope Filtering

### Before:
```python
@router.get("/invoices")
async def get_invoices(db: Session = Depends(get_db),
                      current_user: Users = Depends(get_current_internal_user)):
    """Get invoices - Finance sees all, others see own BU"""
    return db.query(Invoice).filter(
        Invoice.tenant_id == current_user.tenant_id
    ).all()  # INCORRECTLY EXPOSES DATA
```

### After:
```python
@router.get("/invoices")
@require_permission("invoice.view")
@apply_data_scope("invoices")
async def get_invoices(db: Session = Depends(get_db),
                      current_user: Users = Depends(get_current_internal_user),
                      data_scope: dict = None):
    """Get invoices based on data scope"""
    query = db.query(Invoice).filter(
        Invoice.tenant_id == current_user.tenant_id
    )
    
    # Apply scope: CEO/Finance/Admin see ORG_WIDE,
    # Partner sees MULTI_BU, others see nothing
    return PermissionService.apply_data_scope_filter(
        query, data_scope, Invoice
    ).all()
```

## Phase 3 Implementation Checklist

Update these endpoints to wire in decorators:

### Recruitment Module
- [ ] `POST /candidates` - add `@require_permission("candidate.create")`
- [ ] `GET /candidates` - add `@require_permission("candidate.view")` + `@apply_data_scope("candidates")`
- [ ] `PUT /candidates/{id}` - add `@require_permission("candidate.edit")`
- [ ] `DELETE /candidates/{id}` - add `@require_permission("candidate.delete")`

### HR Module
- [ ] `GET /employees` - add `@require_permission("employee.view")` + `@apply_data_scope("employees")`
- [ ] `GET /employees/{id}` - add field masking for salary/SSN/bank account
- [ ] `PUT /employees/{id}` - add `@require_permission("employee.edit")`
- [ ] `DELETE /employees/{id}` - add `@require_permission("employee.delete")`

### Timesheet Module
- [ ] `GET /timesheets` - add `@require_permission("timesheet.view")` + scope
- [ ] `PUT /timesheets/{id}/approve` - add `@require_permission("timesheet.approve")`
- [ ] `DELETE /timesheets/{id}` - add `@require_permission("timesheet.delete")`

### Finance Module
- [ ] `GET /invoices` - add `@require_permission("invoice.view")` + `@apply_data_scope("invoices")`
- [ ] `PUT /invoices/{id}/approve` - add `@require_permission("invoice.approve")`
- [ ] `DELETE /invoices/{id}` - add `@require_permission("invoice.delete")`

### User Management
- [ ] `POST /users` - add `@require_permission("user.create")`
- [ ] `PUT /users/{id}` - add `@require_permission("user.manage")`
- [ ] `DELETE /users/{id}` - add `@require_permission("user.delete")`
- [ ] `PUT /users/{id}/roles` - add `@require_permission("user.manage_roles")`

### Admin/System
- [ ] `GET /system/config` - add `@require_permission("system.view")`
- [ ] `PUT /system/config` - add `@require_permission("system.manage")`

## Testing Each Decorator

```bash
# Run permission tests
pytest tests/test_permissions_backend.py -v

# Run with coverage
pytest tests/test_permissions_backend.py -v --cov=app.services.permission_service --cov=app.core.permission_decorators

# Run specific test class
pytest tests/test_permissions_backend.py::TestRecruiterPermissions -v

# Run specific test
pytest tests/test_permissions_backend.py::TestRecruiterPermissions::test_recruiter_cannot_delete_candidate -v
```

## Integration Status

| Component | Status | Notes |
|-----------|--------|-------|
| PermissionService | ✅ Done | `app/services/permission_service.py` |
| Decorators | ✅ Done | `app/core/permission_decorators.py` |
| Backend Tests | ✅ Done | `tests/test_permissions_backend.py` (70+ tests) |
| API Integration | ⏳ In Progress | Wire decorators into each endpoint (see checklist) |
| Frontend Permission Tests | ⏳ Pending | Phase 4 |
| Frontend UI Updates | ⏳ Pending | Phase 5 |
| E2E Testing | ⏳ Pending | Phase 6 |

## Next Steps

1. Apply the decorator patterns above to all existing endpoints
2. Run the regression test suite: `pytest tests/test_permissions_backend.py -v`
3. Verify all 127+ tests pass
4. Move to Phase 4: Frontend testing
