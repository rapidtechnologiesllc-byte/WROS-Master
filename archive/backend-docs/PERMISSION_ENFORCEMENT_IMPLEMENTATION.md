# Permission-Based Access Control Implementation (Step 4)

## Overview

Step 4 implements permission enforcement for all endpoints based on user role templates. This ensures users can only:
- **V (View)**: See/access data in modules they have view permission for
- **C (Create)**: Create new items only with create permission
- **E (Edit)**: Edit existing items only with edit permission  
- **D (Delete)**: Delete items only with delete permission

## Architecture

### Permission Format
All permissions follow the format: `resource.action`

Examples:
- `administration.view` - Can view users/roles/business units
- `administration.create` - Can create new users
- `administration.edit` - Can edit existing users
- `administration.delete` - Can delete users
- `candidates.view` - Can view candidates
- `recruitment.manage` - Can manage recruitment process

### Permission Storage
Permissions come from `RoleTemplate` assignments via `UserRole` junction table:
1. User is assigned a RoleTemplate
2. RoleTemplate has RoleTemplatePermission entries (V, C, E, D)
3. Each RoleTemplatePermission links to a Resource with specific actions

## Backend Implementation

### 1. Permission Enforcement Decorators

**File:** `/app/core/permission_enforcement.py`

Use decorators on all endpoints to enforce permissions:

```python
from app.core.permission_enforcement import require_action_permission

@router.get("/candidates")
@require_action_permission("candidates", "view")
async def get_candidates(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get all candidates - requires candidates.view permission"""
    # endpoint code
```

#### Available Decorators

**`@require_permission(permission: str)`**
- Enforce a specific permission string
- Usage: `@require_permission("candidates.view")`

**`@require_action_permission(resource: str, action: str)`**
- Enforce V, C, E, D permissions
- Usage: `@require_action_permission("administration", "create")`
- Actions: "view", "create", "edit", "delete"

**`@require_any_permission(permissions: List[str])`**
- Enforce that user has ANY of the given permissions
- Usage: `@require_any_permission(["candidates.view", "recruitment.view"])`

**`@require_all_permissions(permissions: List[str])`**
- Enforce that user has ALL of the given permissions
- Usage: `@require_all_permissions(["offers.view", "offers.approve"])`

### 2. Endpoint Permission Mapping

All CRUD endpoints should use the standard permission pattern:

| HTTP Method | Endpoint | Permission | Decorator |
|------------|----------|-----------|-----------|
| GET | `/admin/users` | `administration.view` | `@require_action_permission("administration", "view")` |
| POST | `/admin/users` | `administration.create` | `@require_action_permission("administration", "create")` |
| PUT | `/admin/users/{id}` | `administration.edit` | `@require_action_permission("administration", "edit")` |
| DELETE | `/admin/users/{id}` | `administration.delete` | `@require_action_permission("administration", "delete")` |

This pattern applies to all modules: recruitment, candidates, projects, finance, etc.

### 3. Current Implementation Status

**Endpoints Updated:**
- `/api/admin/users-access-control/users` - GET, POST, PUT, DELETE with permission decorators
- `/api/v1/users/me/permissions` - Returns user's permissions for frontend caching

**Services:**
- `PermissionHelper` - Core permission checking logic
- `PermissionAuditService` - Logs all permission checks for audit trail
- `RoleTemplatePermissionService` - Manages role-permission mappings

### 4. Audit Logging

All permission checks are logged for security and compliance:

**File:** `/app/services/permission_audit_service.py`

Logs include:
- User ID performing the action
- Permission checked
- Whether permission was granted/denied
- Timestamp and context

**Query audit trail:**
```python
from app.services.permission_audit_service import PermissionAuditService

# Get all permission denials for a user
denials = PermissionAuditService.get_denied_permissions_for_user(
    db=db,
    user_id="user123",
    days=7
)

# Get denial summary
summary = PermissionAuditService.get_permission_denial_summary(
    db=db,
    user_id="user123"
)

# Check for suspicious access attempts
is_suspicious = PermissionAuditService.check_for_unauthorized_access_attempts(
    db=db,
    user_id="user123",
    threshold=10,  # 10 denials
    minutes=5      # in 5 minutes
)
```

### 5. Error Handling

Permission denials return HTTP 403 Forbidden with clear error message:

```json
{
  "detail": "Permission denied: administration.create"
}
```

Other potential errors:
- 401 Unauthorized - User not authenticated
- 500 Internal Server Error - Database or system error
- 400 Bad Request - Invalid input

## Frontend Implementation

### 1. Permission Caching

After login, fetch and cache user permissions:

```javascript
// In login handler or App initialization
const response = await fetch('/api/v1/users/me/permissions', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const { permissions, is_super_admin, modules } = await response.json();

// Cache in localStorage
localStorage.setItem('user', JSON.stringify({
  permissions,
  is_super_admin,
  modules
}));
```

### 2. Permission Utility Functions

**File:** `/src/utils/permissionsRbac.js`

Basic functions:
```javascript
import {
  hasPermission,
  hasAnyPermission,
  hasAllPermissions,
  canViewModule,
  canCreateInModule,
  canEditInModule,
  canDeleteInModule,
  isSuperAdmin
} from './utils/permissionsRbac';

// Check permission
if (hasPermission('candidates.create')) {
  // Show create button
}

// Check module access
if (canViewModule('administration')) {
  // Show admin panel
}

// Check action in module
if (canCreateInModule('candidates')) {
  // Show create candidate form
}
```

### 3. Permission Context

**File:** `/src/context/PermissionContext.js`

React hook for permission management:

```javascript
import { usePermissions } from './context/PermissionContext';

export function AdminPanel() {
  const { hasPermission, canViewModule, loading } = usePermissions();

  if (loading) return <div>Loading permissions...</div>;

  if (!canViewModule('administration')) {
    return <div>Access denied</div>;
  }

  return (
    <div>
      {hasPermission('users.create') && <CreateUserButton />}
      {hasPermission('users.edit') && <EditUserButton />}
      {hasPermission('users.delete') && <DeleteUserButton />}
    </div>
  );
}
```

### 4. Permission-Based Components

**File:** `/src/components/PermissionButton.js`

Ready-to-use permission-aware components:

```javascript
import {
  PermissionButton,
  IfPermission,
  IfCanAction,
  PermissionInput
} from './components/PermissionButton';

// Button that automatically disables if no permission
<PermissionButton
  permission="candidates.create"
  onClick={handleCreate}
>
  Create Candidate
</PermissionButton>

// Conditional render - shows nothing if no permission
<IfPermission permission="candidates.delete">
  <DeleteButton />
</IfPermission>

// Action-based conditional
<IfCanAction module="administration" action="create">
  <CreateUserButton />
</IfCanAction>

// Disabled input if no edit permission
<PermissionInput
  permission="candidates.edit"
  value={candidateName}
  onChange={handleChange}
/>
```

### 5. Navigation Filtering

Filter navigation items based on permissions:

```javascript
const NAVIGATION_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', url: '/dashboard' },
  { key: 'administration', label: 'Users & Access', url: '/admin', requiresPermission: 'administration.view' },
  { key: 'recruitment', label: 'Recruitment', url: '/recruitment', requiresPermission: 'recruitment.view' },
  { key: 'candidates', label: 'Candidates', url: '/candidates', requiresPermission: 'candidates.view' },
];

function NavigationBar() {
  const { hasPermission } = usePermissions();

  return (
    <nav>
      {NAVIGATION_ITEMS
        .filter(item => !item.requiresPermission || hasPermission(item.requiresPermission))
        .map(item => (
          <a key={item.key} href={item.url}>{item.label}</a>
        ))
      }
    </nav>
  );
}
```

## Testing Permission-Based Access Control

### 1. Test Different User Roles

Test with these role combinations:

**Super User:**
- ✅ Can view all modules
- ✅ Can create/edit/delete in all modules
- ✅ No permission errors

**Admin:**
- ✅ Can view all modules
- ✅ Can create/edit/delete in most modules
- ✅ May have restrictions on sensitive modules

**Finance Manager:**
- ✅ Can view finance module
- ✅ Can create/edit financial records
- ✅ Cannot access recruitment (403 error)
- ✅ Cannot see recruitment in navigation

**HR Manager:**
- ✅ Can view administration/workforce modules
- ✅ Can create/edit/delete users
- ✅ Cannot delete (if permission not granted)
- ✅ Cannot access finance module

**Recruiter:**
- ✅ Can view recruitment/candidates modules
- ✅ Can create candidates
- ✅ Cannot access administration module
- ✅ Cannot delete candidates (if not in role)

### 2. Test Permission Enforcement

**GET endpoint without view permission:**
```bash
# Request without candidates.view permission
GET /api/v1/candidates
Authorization: Bearer <token_without_view>

# Expected response: 403 Forbidden
{
  "detail": "Permission denied: candidates.view"
}
```

**POST endpoint without create permission:**
```bash
# Request without candidates.create permission
POST /api/v1/candidates
Authorization: Bearer <token_without_create>
Body: { "name": "John", ... }

# Expected response: 403 Forbidden
{
  "detail": "Permission denied: candidates.create"
}
```

**PUT endpoint without edit permission:**
```bash
# Request without candidates.edit permission
PUT /api/v1/candidates/123
Authorization: Bearer <token_without_edit>
Body: { "name": "Jane", ... }

# Expected response: 403 Forbidden
```

**DELETE endpoint without delete permission:**
```bash
# Request without candidates.delete permission
DELETE /api/v1/candidates/123
Authorization: Bearer <token_without_delete>

# Expected response: 403 Forbidden
```

### 3. Test Frontend Permission Checks

**Test navigation filtering:**
- Login as different users
- Verify navigation only shows modules with view permission
- Verify buttons are disabled for actions without permission

**Test error messages:**
- Try to click disabled button
- Verify tooltip explains why button is disabled
- Verify error message in UI matches permission structure

**Test localStorage caching:**
- Login (permissions cached in localStorage)
- Refresh page (permissions still available)
- Offline mode - permissions still work from cache
- Logout - permissions cleared from cache

### 4. Permission Denial Audit

Query audit log for permission denials:

```bash
# Get all permission denials for a user in last 7 days
GET /api/v1/audit/permission-denials?user_id=user123&days=7

# Get permission denial summary
GET /api/v1/audit/permission-denial-summary?user_id=user123&days=7

# Response:
{
  "total_denials": 42,
  "unique_permissions_denied": ["candidates.delete", "projects.create"],
  "most_common_denial": "candidates.delete",
  "denial_count_by_permission": {
    "candidates.delete": 30,
    "projects.create": 12
  }
}
```

## Implementation Checklist

- [ ] Permission enforcement middleware deployed
- [ ] All CRUD endpoints guarded with decorators
- [ ] Backend returns 403 for permission denied
- [ ] Frontend permissions utility functions created
- [ ] Permission context provider set up
- [ ] Navigation bar filters by module permissions
- [ ] Buttons disable when user lacks permission
- [ ] Forms disable inputs for non-editable items
- [ ] Error messages show for permission denials
- [ ] Audit logging working for all permission checks
- [ ] Tests pass for all permission scenarios
- [ ] Documentation complete

## Security Considerations

### 1. Permission Caching
- Permissions cached in localStorage for performance
- Cache includes permissions, modules, and super_admin flag
- Cache cleared on logout
- Cache is read-only on frontend (no manual permission grants)

### 2. API-Side Enforcement
- All permission checks enforced at API layer (backend)
- Frontend checks are for UX only (hiding/disabling UI)
- Bypass frontend checks by:
  - Modifying localStorage
  - Using browser developer console
  - Making API calls directly
- But all requests to API are validated by backend

### 3. Audit Trail
- All permission checks logged to audit_log table
- Permission denials recorded with timestamp, user, context
- Used to detect:
  - Unauthorized access attempts
  - Permission misconfigurations
  - Suspicious user behavior

### 4. Super Admin Bypass
- Super users bypass all permission checks
- Super user status checked before permission validation
- Super users still logged in audit trail

## Migration Guide

### Step 1: Deploy Backend Changes
1. Deploy `/app/core/permission_enforcement.py`
2. Deploy `/app/services/permission_audit_service.py`
3. Update endpoints with decorators
4. Test with Postman/curl to verify 403 responses

### Step 2: Deploy Frontend Changes
1. Deploy `/src/utils/permissionsRbac.js`
2. Deploy `/src/context/PermissionContext.js`
3. Deploy `/src/components/PermissionButton.js`
4. Wrap app with `<PermissionProvider>`
5. Update navigation to filter by permissions
6. Test with different user roles

### Step 3: Update Role Templates
1. Verify all roles have correct permissions
2. Ensure no users left without proper role assignments
3. Test critical user flows with each role

### Step 4: Monitor Audit Logs
1. Set up alerts for excessive permission denials
2. Review daily permission denial reports
3. Adjust permissions based on usage patterns

## Troubleshooting

### User Sees 403 Permission Denied

**Possible causes:**
1. User role doesn't have required permission
2. Permission string mismatch (e.g., "candidate" vs "candidates")
3. Tenant ID mismatch
4. Role template not assigned correctly

**Solution:**
1. Check user's assigned roles: `SELECT * FROM user_roles WHERE user_id = 'xxx'`
2. Check role's permissions: `SELECT * FROM role_template_permissions WHERE role_template_id = X`
3. Check audit log for denial details: `SELECT * FROM audit_logs WHERE user_id = 'xxx' AND action_status = 'DENIED'`
4. Compare permission string in decorator vs resource name in database

### Permission Button Always Enabled

**Possible causes:**
1. Permissions not cached in localStorage
2. Permission utility function reading wrong storage key
3. Permission string format incorrect

**Solution:**
1. Check localStorage: `console.log(localStorage.getItem('user'))`
2. Verify permission format: should be lowercase with dot (e.g., "administration.view")
3. Check browser console for permission utility errors
4. Fetch permissions: `usePermissions().fetchPermissions()`

### Navigation Shows All Modules

**Possible causes:**
1. Permission context not loaded
2. Navigation not using permission check
3. Super admin mode enabled

**Solution:**
1. Verify `<PermissionProvider>` wraps app
2. Check navigation component uses `canViewModule()` or `isNavItemVisible()`
3. Check if user is super admin: `isSuperAdmin()` should return false
4. Force permission refresh: `fetchPermissions()`

## Support

For questions or issues with permission enforcement, refer to:
- `/app/core/permission_enforcement.py` - Backend decorators
- `/app/services/permission_helper.py` - Permission checking logic
- `/src/utils/permissionsRbac.js` - Frontend utilities
- `/src/context/PermissionContext.js` - React context
