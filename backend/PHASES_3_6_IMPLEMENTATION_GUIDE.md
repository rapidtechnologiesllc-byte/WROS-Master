# Phases 3-6: Permission System Implementation Guide

**Status:** Phases 1-2 Complete ✅  
**Next:** Phases 3-6 (Permission Service, Tests, Frontend, E2E)  
**Effort:** ~5-6 hours remaining  
**Start Date:** 2026-08-13  

---

## Phase 3: Permission Service & Decorators (1.5 hours)

### 3.1: Create Permission Service
**File:** `app/services/permission_service.py`

```python
"""Permission system service layer"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models import DetailedPermission, DetailedRolePermission, FieldPermission, DataScopePermission
from app.models.user import Users
from app.models.rbac import Role

class PermissionService:
    @staticmethod
    def has_permission(db: Session, user_id: str, permission: str, tenant_id: int) -> bool:
        """Check if user has permission"""
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            return False
        
        # Super user bypass
        if user.permission_role == "SUPER_USER":
            return True
        
        # Get user's roles
        roles = [ur.role_id for ur in user.user_roles]
        if not roles:
            return False
        
        # Check if any role has the permission
        perm = db.query(DetailedPermission).filter(
            DetailedPermission.name == permission,
            DetailedPermission.tenant_id == tenant_id
        ).first()
        
        if not perm:
            return False
        
        return db.query(DetailedRolePermission).filter(
            and_(
                DetailedRolePermission.role_id.in_(roles),
                DetailedRolePermission.permission_id == perm.id
            )
        ).first() is not None
    
    @staticmethod
    def get_field_access_level(db: Session, user_id: str, table: str, field: str) -> str:
        """Get field access level: hidden, masked, readonly, editable"""
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            return "hidden"
        
        if user.permission_role == "SUPER_USER":
            return "editable"
        
        roles = [ur.role_id for ur in user.user_roles]
        
        # Get highest access level across all user roles
        access = db.query(FieldPermission).filter(
            and_(
                FieldPermission.role_id.in_(roles),
                FieldPermission.table_name == table,
                FieldPermission.field_name == field
            )
        ).first()
        
        return access.access_level if access else "hidden"
    
    @staticmethod
    def get_data_scope(db: Session, user_id: str, module: str) -> dict:
        """Get data scope for module: ORG_WIDE, MULTI_BU, BU_ONLY, TEAM_ONLY"""
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            return {"scope_type": "NONE"}
        
        if user.permission_role == "SUPER_USER":
            return {"scope_type": "ORG_WIDE"}
        
        roles = [ur.role_id for ur in user.user_roles]
        
        scope = db.query(DataScopePermission).filter(
            and_(
                DataScopePermission.role_id.in_(roles),
                DataScopePermission.module == module
            )
        ).first()
        
        if not scope:
            return {"scope_type": "NONE"}
        
        return {
            "scope_type": scope.scope_type,
            "filter_rule": scope.filter_rule,
            "user_bu_id": user.business_unit_id,
            "user_org_node_id": user.org_node_id,
        }
```

### 3.2: Create Permission Decorators
**File:** `app/core/permission_decorators.py`

```python
"""Permission checking decorators"""
from functools import wraps
from fastapi import HTTPException, Depends, Request
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.security import get_current_internal_user
from app.models.user import Users
from app.services.permission_service import PermissionService

def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            db: Session = kwargs.get("db") or Depends(SessionLocal)
            current_user: Users = kwargs.get("current_user") or Depends(get_current_internal_user)
            
            if not PermissionService.has_permission(db, current_user.UserID, permission, current_user.tenant_id):
                raise HTTPException(status_code=403, detail=f"Permission denied: {permission}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def apply_data_scope(module: str):
    """Decorator to apply data scope filter to query"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            db: Session = kwargs.get("db")
            current_user: Users = kwargs.get("current_user")
            
            scope = PermissionService.get_data_scope(db, current_user.UserID, module)
            kwargs["data_scope"] = scope
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

### 3.3: Wire Up to API Endpoints
**File:** `app/api/v1/endpoints/candidates.py`

```python
from app.core.permission_decorators import require_permission, apply_data_scope

@router.get("/")
@require_permission("candidate.view")
@apply_data_scope("candidates")
async def get_candidates(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
    data_scope: dict = None
):
    """Get candidates with permission and scope checks"""
    query = db.query(Candidate).filter(Candidate.tenant_id == current_user.tenant_id)
    
    # Apply data scope filter
    if data_scope["scope_type"] == "BU_ONLY":
        query = query.filter(Candidate.business_unit_id == data_scope["user_bu_id"])
    elif data_scope["scope_type"] == "TEAM_ONLY":
        # Filter by team (requires team relationship)
        query = query.filter(Candidate.assigned_to == current_user.UserID)
    
    return query.all()

@router.delete("/{candidate_id}")
@require_permission("candidate.delete")
async def delete_candidate(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Delete candidate (requires permission)"""
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404)
    
    db.delete(candidate)
    db.commit()
    return {"status": "deleted"}
```

---

## Phase 4: Regression Tests (2 hours)

### 4.1: Backend Permission Tests
**File:** `tests/test_permissions_backend.py`

```python
"""Backend permission system tests"""
import pytest
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.user import Users
from app.models.rbac import Role
from app.services.permission_service import PermissionService

@pytest.fixture
def db():
    return SessionLocal()

@pytest.fixture
def recruiter_user(db):
    """Create a recruiter user with appropriate roles"""
    user = db.query(Users).filter(Users.permission_role == "RECRUITER").first()
    return user

@pytest.fixture
def ceo_user(db):
    """Create a CEO user"""
    user = db.query(Users).filter(Users.permission_role == "SUPER_USER").first()
    return user

def test_recruiter_cannot_see_salary(db, recruiter_user):
    """Recruiter should not see employee salary field"""
    access = PermissionService.get_field_access_level(
        db, recruiter_user.UserID, "employees", "salary"
    )
    assert access == "hidden"

def test_recruiter_can_create_candidate(db, recruiter_user):
    """Recruiter should have candidate.create permission"""
    has_perm = PermissionService.has_permission(
        db, recruiter_user.UserID, "candidate.create", recruiter_user.tenant_id
    )
    assert has_perm is True

def test_recruiter_cannot_delete_candidate(db, recruiter_user):
    """Recruiter should NOT have candidate.delete permission"""
    has_perm = PermissionService.has_permission(
        db, recruiter_user.UserID, "candidate.delete", recruiter_user.tenant_id
    )
    assert has_perm is False

def test_recruiter_bu_scoped(db, recruiter_user):
    """Recruiter should have BU_ONLY scope"""
    scope = PermissionService.get_data_scope(db, recruiter_user.UserID, "candidates")
    assert scope["scope_type"] == "BU_ONLY"
    assert scope["user_bu_id"] == recruiter_user.business_unit_id

def test_ceo_can_do_everything(db, ceo_user):
    """CEO should have all permissions"""
    assert PermissionService.has_permission(db, ceo_user.UserID, "candidate.delete", ceo_user.tenant_id)
    assert PermissionService.has_permission(db, ceo_user.UserID, "user.manage", ceo_user.tenant_id)
    assert PermissionService.has_permission(db, ceo_user.UserID, "system.manage", ceo_user.tenant_id)
```

**Run tests:**
```bash
pytest tests/test_permissions_backend.py -v
```

### 4.2: Frontend Permission Tests
**File:** `tests/test_permissions_frontend.test.js`

```javascript
import { render, screen } from '@testing-library/react';
import { AskUserQuestion } from '@testing-library/user-event';
import UsersAndAccessControl from '../screens/UsersAndAccessControl';

describe('Permission System Frontend Tests', () => {
  it('recruiter should not see delete button', () => {
    localStorage.setItem('permission_role', 'RECRUITER');
    render(<UsersAndAccessControl />);
    expect(screen.queryByRole('button', {name: /delete/i})).not.toBeInTheDocument();
  });

  it('ceo should see all action buttons', () => {
    localStorage.setItem('permission_role', 'SUPER_USER');
    render(<UsersAndAccessControl />);
    expect(screen.getByRole('button', {name: /delete/i})).toBeInTheDocument();
    expect(screen.getByRole('button', {name: /edit/i})).toBeInTheDocument();
  });

  it('recruiter should only see own bu candidates', async () => {
    localStorage.setItem('permission_role', 'RECRUITER');
    localStorage.setItem('business_unit_id', '1');
    render(<UsersAndAccessControl />);
    
    await screen.findByText(/North America/);
    expect(screen.queryByText(/Europe/)).not.toBeInTheDocument();
  });
});
```

**Run tests:**
```bash
npm test -- tests/test_permissions_frontend.test.js
```

---

## Phase 5: Frontend Updates (1 hour)

### 5.1: Update Create User Form
**File:** `src/screens/UsersAndAccessControl.js` (Update existing)

**Changes needed:**
1. Add Business Unit dropdown (MANDATORY) - filters managers to that BU
2. Change to Reporting Manager selector (filtered by selected BU)
3. Add Job Title dropdown (from admin-defined list)
4. Update form submission to pass job_title_id to backend
5. Remove old "Permission Template" dropdown (no longer needed)

**Key code pattern:**
```javascript
const [selectedBU, setSelectedBU] = useState(null);
const [managers, setManagers] = useState([]);

const handleBUChange = async (buId) => {
  setSelectedBU(buId);
  // Fetch managers from that BU
  const res = await fetch(`/api/managers?business_unit_id=${buId}`);
  setManagers(await res.json());
};

const handleCreateUser = async () => {
  const payload = {
    user_name: formData.user_name,
    user_email: formData.user_email,
    user_password: formData.user_password,
    business_unit_id: selectedBU, // MANDATORY
    reporting_manager_id: formData.reporting_manager_id,
    job_title_id: formData.job_title_id,
    role_ids: formData.role_ids
  };
  // Call backend
};
```

### 5.2: Add Job Titles Management UI
**File:** `src/screens/AdminSettingsScreen.js` (Update existing Organization section)

**Add new section:** Admin Settings → Organization → Job Titles

```javascript
const [jobTitles, setJobTitles] = useState([]);
const [showAddJobTitleModal, setShowAddJobTitleModal] = useState(false);

const handleAddJobTitle = async (name, description, roleIds) => {
  const res = await fetch('/api/job-titles', {
    method: 'POST',
    body: JSON.stringify({name, description, role_ids: roleIds})
  });
  setJobTitles([...jobTitles, await res.json()]);
};

const handleDeleteJobTitle = async (jobTitleId) => {
  await fetch(`/api/job-titles/${jobTitleId}`, {method: 'DELETE'});
  setJobTitles(jobTitles.filter(jt => jt.id !== jobTitleId));
};
```

---

## Phase 6: End-to-End Testing (1 hour)

### 6.1: Test Each Role End-to-End

**Test Workflow:**

```
1. CEO LOGIN:
   - Navigate to Candidates → should see all BUs
   - Try to Delete candidate → should succeed
   - Navigate to Users → should see all users
   - Try to Create user → should succeed
   
2. RECRUITER LOGIN:
   - Navigate to Candidates → should see only own BU
   - Try to Delete candidate → should fail (403)
   - Navigate to Employees → should be HIDDEN
   - Try to view salary field → should be HIDDEN
   
3. PARTNER LOGIN:
   - Navigate to Candidates → should see 2-3 BUs (assigned)
   - Try to Delete candidate → should fail (403)
   - Check dashboard → should show multi-BU aggregated data
   
4. MANAGER LOGIN:
   - Navigate to Employees → should see only own team
   - Try to approve timesheet → should succeed
   - Try to create invoice → should fail (403 or hidden)
   
5. HR MANAGER LOGIN:
   - Check employee salary field → should be MASKED
   - Try to approve leave → should succeed
   - Try to manage roles → should fail (403 or hidden)
   
6. FINANCE LOGIN:
   - Navigate to Invoices → should see all BUs
   - Try to delete invoice → should fail (403 or hidden)
   - Navigate to Recruitment → should be HIDDEN
```

### 6.2: Validation Checklist

```
✅ Role-specific navigation (modules hidden/shown correctly)
✅ Data isolation (cross-BU data not accessible)
✅ Field masking (PII hidden/masked by role)
✅ Action permissions (delete/approve/manage buttons only for authorized roles)
✅ Dashboard rendering (role-specific data shown)
✅ API enforcement (403 returned for unauthorized endpoints)
✅ Cross-browser testing (Chrome, Firefox, Safari)
✅ Performance (no N+1 queries, permission checks cached)
```

---

## Execution Order

1. **Phase 3 (1.5h):** Create PermissionService + decorators, wire to endpoints
2. **Phase 4 (2h):** Write and run 127+ regression tests
3. **Phase 5 (1h):** Update frontend forms and admin screens
4. **Phase 6 (1h):** Manual E2E testing for all 8 roles

**Total: ~5.5 hours**

---

## Success Criteria

✅ All 127+ regression tests pass  
✅ CEO can access everything  
✅ Recruiter cannot delete candidates  
✅ Recruiter cannot see employee data  
✅ Finance cannot see recruitment data  
✅ Manager sees only own team  
✅ Partner sees only assigned BUs  
✅ HR Manager sees masked SSN  
✅ No 403 errors in browser console (permissions enforced, not exposed)  
✅ All dashboards render correct role-specific data  

---

## Next Steps After Phase 6

1. **Push to main** once all tests pass
2. **Update CLAUDE.md** with permission system status
3. **Create operational runbook** for admin managing roles/permissions
4. **Monitor production** for any permission-bypass attempts (audit logs)
5. **Schedule quarterly permission audit** to review role assignments

---

## Files to Update (Summary)

| File | Changes |
|------|---------|
| `app/services/permission_service.py` | NEW - Core permission logic |
| `app/core/permission_decorators.py` | NEW - @require_permission, @apply_data_scope |
| `app/api/v1/endpoints/candidates.py` | Update with decorators |
| `app/api/v1/endpoints/employees.py` | Update with decorators |
| `app/api/v1/endpoints/invoices.py` | Update with decorators |
| `app/api/v1/endpoints/users.py` | Update with decorators |
| `src/screens/UsersAndAccessControl.js` | Add BU→Manager→JobTitle flow |
| `src/screens/AdminSettingsScreen.js` | Add Job Titles management |
| `tests/test_permissions_backend.py` | NEW - 127+ backend tests |
| `tests/test_permissions_frontend.test.js` | NEW - Frontend permission tests |

---

## Estimated Timeline

- **Phase 3:** 2026-08-13 afternoon (1.5h)
- **Phase 4:** 2026-08-14 morning (2h)  
- **Phase 5:** 2026-08-14 afternoon (1h)
- **Phase 6:** 2026-08-15 morning (1h)

**Production Ready:** 2026-08-15 EOD

---

**Generated:** 2026-08-13 
**Status:** Ready for Phase 3 implementation
