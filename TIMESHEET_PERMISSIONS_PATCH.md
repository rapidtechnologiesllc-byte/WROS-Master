# Timesheet Endpoints - Permission Hardening (CYCLE 5)

## Files to Update
`backend/app/api/v1/endpoints/timesheets.py`

## Pattern to Apply
```python
from app.core.dependencies import require_role_template_permission
from app.schemas.permissions import Permissions

# For READ operations (GET):
@router.get(
    "/endpoint",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_VIEW))]
)

# For WRITE operations (POST/PUT/DELETE):
@router.post(
    "/endpoint",
    dependencies=[Depends(require_role_template_permission(*Permissions.TIMESHEETS_EDIT))]
)
```

## Endpoints Needing Update (15 total)

### VIEW (lines 158, 203, 245, 289, 326, 442, 462):
- Lines: 158, 203, 245, 289, 326 (POST endpoints - check if they retrieve or create)
- Lines: 442, 462 (GET endpoints - READ permission)

### EDIT (lines 367, 404, 486, 519, 549, 593, 613, 662):
- All POST/PUT operations creating/updating timesheet records
- Use TIMESHEETS_EDIT permission

## Next Session
Run automated patch script to apply this pattern to all 15 endpoints.
Verify gate passes with zero permission violations.
