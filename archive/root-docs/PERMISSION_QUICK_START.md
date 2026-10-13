# Permission-Based Access Control - Quick Start Guide

## For Backend Developers

### Add Permission Check to an Endpoint

**Step 1: Import the decorator**
```python
from app.core.permission_enforcement import require_action_permission
```

**Step 2: Add decorator to your endpoint**
```python
@router.get("/candidates")
@require_action_permission("candidates", "view")
async def get_candidates(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get all candidates"""
    # Your code here
```

**Step 3: That's it!**
- Users without `candidates.view` permission will get 403 Forbidden
- Permission is checked automatically before your code runs
- Audit log records the permission check

### Common Permission Patterns

**For CRUD endpoints:**
```python
# READ (List/Get)
@router.get("/users")
@require_action_permission("administration", "view")
def list_users(...): ...

# CREATE
@router.post("/users")
@require_action_permission("administration", "create")
def create_user(...): ...

# UPDATE
@router.put("/users/{id}")
@require_action_permission("administration", "edit")
def update_user(...): ...

# DELETE
@router.delete("/users/{id}")
@require_action_permission("administration", "delete")
def delete_user(...): ...
```

**For complex authorization:**
```python
from app.core.permission_enforcement import require_any_permission, require_all_permissions

# Any of these permissions
@router.post("/reports/approve")
@require_any_permission(["reports.approve", "admin.manage"])
def approve_report(...): ...

# All of these permissions
@router.post("/offers/approve")
@require_all_permissions(["offers.view", "offers.approve"])
def approve_offer(...): ...
```

**For inline checks:**
```python
from app.core.permission_enforcement import check_permission

def update_candidate_salary(candidate_id, salary, db, current_user):
    # Complex logic that requires different permissions
    
    if not check_permission(current_user.UserID, "finance.edit", db):
        raise HTTPException(403, "Cannot modify salary")
    
    # Update salary
    ...
```

### Resources and Their Permissions

Common resources in the system:

| Resource | View | Create | Edit | Delete |
|----------|------|--------|------|--------|
| administration | ✅ | ✅ | ✅ | ✅ |
| candidates | ✅ | ✅ | ✅ | ✅ |
| recruitment | ✅ | ✅ | ✅ | ✅ |
| projects | ✅ | ✅ | ✅ | ✅ |
| finance | ✅ | ✅ | ✅ | ✅ |
| reports | ✅ | ✅ | ✅ | - |
| workforce | ✅ | ✅ | ✅ | ✅ |

## For Frontend Developers

### Import Permission Utilities

```javascript
import {
  hasPermission,
  canViewModule,
  canCreateInModule,
  canEditInModule,
  canDeleteInModule
} from './utils/permissionsRbac';

import { usePermissions } from './context/PermissionContext';
```

### Check Permissions in Component

**Using utility functions:**
```javascript
function CandidateList() {
  if (!canViewModule('candidates')) {
    return <div>You don't have access to this module</div>;
  }

  return (
    <div>
      {canCreateInModule('candidates') && (
        <button onClick={handleCreate}>Add Candidate</button>
      )}
      {canEditInModule('candidates') && (
        <EditCandidateButton />
      )}
      {canDeleteInModule('candidates') && (
        <DeleteCandidateButton />
      )}
    </div>
  );
}
```

**Using React hooks:**
```javascript
function CandidateList() {
  const { canViewModule, hasPermission } = usePermissions();

  if (!canViewModule('candidates')) {
    return <AccessDenied />;
  }

  return (
    <div>
      {hasPermission('candidates.create') && <CreateButton />}
      {hasPermission('candidates.delete') && <DeleteButton />}
    </div>
  );
}
```

### Use Permission Components

```javascript
import {
  PermissionButton,
  IfPermission,
  IfCanAction,
  PermissionInput
} from './components/PermissionButton';

function CandidateForm() {
  return (
    <form>
      <PermissionInput
        permission="candidates.edit"
        value={name}
        onChange={setName}
        placeholder="Candidate name"
      />

      <PermissionButton
        permission="candidates.create"
        onClick={handleSave}
      >
        Save Candidate
      </PermissionButton>

      <IfPermission permission="candidates.delete">
        <button onClick={handleDelete}>Delete</button>
      </IfPermission>
    </form>
  );
}
```

### Filter Navigation Items

```javascript
import { isNavItemVisible, getVisibleModules } from './utils/permissionsRbac';

const ALL_NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'candidates', label: 'Candidates' },
  { key: 'administration', label: 'Admin' },
  { key: 'finance', label: 'Finance' },
];

function NavigationBar() {
  const visibleItems = ALL_NAV_ITEMS.filter(
    item => isNavItemVisible(item.key)
  );

  return (
    <nav>
      {visibleItems.map(item => (
        <a key={item.key} href={`/${item.key}`}>
          {item.label}
        </a>
      ))}
    </nav>
  );
}
```

### Handle Permission Denials

```javascript
function ApiCall() {
  const [error, setError] = useState(null);

  const handleCreate = async () => {
    try {
      const response = await fetch('/api/v1/candidates', {
        method: 'POST',
        body: JSON.stringify(data),
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.status === 403) {
        setError('You don\'t have permission to create candidates');
        return;
      }

      if (!response.ok) throw new Error('Failed to create candidate');
      
      // Success
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      {error && <ErrorAlert message={error} />}
      <button onClick={handleCreate}>Create Candidate</button>
    </div>
  );
}
```

## Integration Steps

### 1. Setup Permission Provider (First Time)

```javascript
// In App.js or root component
import { PermissionProvider } from './context/PermissionContext';

function App() {
  return (
    <PermissionProvider>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/candidates" element={<CandidateList />} />
        {/* ... other routes ... */}
      </Routes>
    </PermissionProvider>
  );
}
```

### 2. Fetch Permissions After Login

```javascript
// In login handler
function handleLogin(email, password) {
  const response = await loginApi(email, password);
  const { access_token, user } = response.data;

  // Store token
  localStorage.setItem('access_token', access_token);

  // Fetch and cache permissions
  const permsResponse = await fetch('/api/v1/users/me/permissions', {
    headers: { 'Authorization': `Bearer ${access_token}` }
  });
  const permissions = await permsResponse.json();

  // Cache user with permissions
  localStorage.setItem('user', JSON.stringify({
    ...user,
    ...permissions
  }));

  // Navigate to dashboard
  navigate('/dashboard');
}
```

### 3. Clear Permissions on Logout

```javascript
// In logout handler
function handleLogout() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('user');
  
  // Clear context
  const { fetchPermissions } = usePermissions();
  fetchPermissions(); // Will clear permissions since no token
  
  navigate('/login');
}
```

## Examples

### Example 1: Admin Panel with Permission Checks

```javascript
function AdminPanel() {
  const { canViewModule, hasPermission } = usePermissions();

  if (!canViewModule('administration')) {
    return <AccessDenied module="administration" />;
  }

  return (
    <div className="admin-panel">
      <h1>Administration</h1>

      <section>
        <h2>User Management</h2>
        {hasPermission('administration.view') && (
          <UserList />
        )}
        {hasPermission('administration.create') && (
          <PermissionButton
            permission="administration.create"
            onClick={openCreateUserForm}
          >
            Add User
          </PermissionButton>
        )}
      </section>

      <section>
        <h2>Business Units</h2>
        {hasPermission('administration.view') && (
          <BusinessUnitList />
        )}
        {hasPermission('administration.edit') && (
          <EditBusinessUnitButton />
        )}
      </section>

      <section>
        <h2>Role Templates</h2>
        {hasPermission('administration.view') && (
          <RoleTemplateList />
        )}
        {hasPermission('administration.delete') && (
          <DeleteRoleButton />
        )}
      </section>
    </div>
  );
}
```

### Example 2: Candidate List with Conditional Actions

```javascript
function CandidateList() {
  const { hasPermission } = usePermissions();
  const [candidates, setCandidates] = useState([]);

  useEffect(() => {
    if (!hasPermission('candidates.view')) {
      return;
    }
    // Fetch candidates
  }, [hasPermission]);

  return (
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Email</th>
          {hasPermission('candidates.edit') && <th>Edit</th>}
          {hasPermission('candidates.delete') && <th>Delete</th>}
        </tr>
      </thead>
      <tbody>
        {candidates.map(candidate => (
          <tr key={candidate.id}>
            <td>{candidate.name}</td>
            <td>{candidate.email}</td>
            {hasPermission('candidates.edit') && (
              <td>
                <EditButton candidateId={candidate.id} />
              </td>
            )}
            {hasPermission('candidates.delete') && (
              <td>
                <DeleteButton candidateId={candidate.id} />
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

### Example 3: Form with Permission-Based Fields

```javascript
function OfferLetterForm({ offerId }) {
  const { hasPermission } = usePermissions();
  const [offer, setOffer] = useState(null);

  return (
    <form>
      <div>
        <label>Candidate Name</label>
        <PermissionInput
          permission="offers.edit"
          value={offer.candidate_name}
          onChange={e => setOffer({...offer, candidate_name: e.target.value})}
        />
      </div>

      <div>
        <label>Salary</label>
        <PermissionInput
          permission="finance.edit"
          value={offer.salary}
          onChange={e => setOffer({...offer, salary: e.target.value})}
        />
      </div>

      <div>
        <label>Start Date</label>
        <PermissionInput
          permission="offers.edit"
          type="date"
          value={offer.start_date}
          onChange={e => setOffer({...offer, start_date: e.target.value})}
        />
      </div>

      <PermissionButton
        permission="offers.edit"
        onClick={handleSave}
      >
        Save Offer
      </PermissionButton>

      <IfPermission permission="offers.approve">
        <button onClick={handleApprove}>Approve Offer</button>
      </IfPermission>

      <IfPermission permission="offers.delete">
        <button onClick={handleDelete} style={{color: 'red'}}>
          Cancel Offer
        </button>
      </IfPermission>
    </form>
  );
}
```

## Debugging

### Check User's Permissions in Browser Console

```javascript
// Get cached permissions
const user = JSON.parse(localStorage.getItem('user'));
console.log(user.permissions);

// Check specific permission
import { hasPermission } from './utils/permissionsRbac';
console.log(hasPermission('candidates.create')); // true/false

// Refresh permissions from backend
import { usePermissions } from './context/PermissionContext';
const { fetchPermissions } = usePermissions();
fetchPermissions().then(() => console.log('Permissions refreshed'));
```

### Check Backend Audit Logs

```bash
# Get all permission denials for a user
curl -X GET "http://localhost:8000/api/v1/audit/permission-denials?user_id=user123" \
  -H "Authorization: Bearer $TOKEN"

# Get permission denial summary
curl -X GET "http://localhost:8000/api/v1/audit/permission-denial-summary?user_id=user123" \
  -H "Authorization: Bearer $TOKEN"
```

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Button always shows | Check permissions cached in localStorage |
| Permission denied error | Verify role has required permission in database |
| No buttons showing | Check if user has any module permissions |
| 403 on all requests | Check if user role is assigned (UserRole table) |
| Permissions not refreshing | Call `fetchPermissions()` after role changes |
| Wrong permission string | Use lowercase with dot: "administration.view" not "Administration View" |

## Resources

- Full documentation: `PERMISSION_ENFORCEMENT_IMPLEMENTATION.md`
- Backend decorators: `app/core/permission_enforcement.py`
- Frontend utilities: `src/utils/permissionsRbac.js`
- React context: `src/context/PermissionContext.js`
- Components: `src/components/PermissionButton.js`
- Audit service: `app/services/permission_audit_service.py`
