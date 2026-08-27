---
name: Organizational Hierarchy Enforcement
description: How the system prevents invalid reporting structures
metadata:
  type: Architecture Documentation
  status: ACTIVE - 2026-08-27
  scope: User Creation, Role Assignment, Reporting Structure
---

# Organizational Hierarchy Enforcement

## The Problem

In an autonomous organism, you can't have random reporting structures. A **Consultant cannot report directly to CEO**. They must follow the chain defined in the hierarchy.

**Invalid (REJECTED):**
```
Consultant → CEO ❌ (skips levels)
Hiring Manager → CEO ❌ (skips levels)  
BU Head → Partner → CEO (but they're same level) ❌
```

**Valid (ACCEPTED):**
```
Consultant → Hiring Manager → BU Head → Partner → CEO ✅
Hiring Manager → BU Head → Partner → CEO ✅
BU Head → Partner → CEO ✅
```

## How It Works

When **adding a new employee** or **assigning a role**, the system validates:

1. **Role exists** - Is "Consultant" a valid role?
2. **Parent is valid** - Can this role report to the assigned parent?
3. **Hierarchy level** - Is parent at higher authority level than employee?
4. **Same business unit** - Unless parent is org-wide (CFO, CWP)
5. **No circular chains** - No "A reports to B reports to A" loops

## Hierarchy Rules

```
LEVEL 5: Individual Contributors (cannot supervise anyone)
  └─ Consultant → Hiring Manager
  └─ Engineer → VP Engineering or Engineering Lead
  └─ Recruiter → Hiring Manager or Workforce Ops Manager

LEVEL 4: Team Leads (supervise individuals)
  └─ Hiring Manager → Workforce Ops Manager or BU Head
  └─ (others manage individuals)

LEVEL 3: Department Managers (supervise teams)
  └─ Delivery Manager → BU Head
  └─ Finance Manager → BU Head
  └─ Workforce Ops Manager → BU Head
  └─ Account Manager → Partner or BU Head

LEVEL 2: Senior Leadership (supervise departments)
  └─ VP Engineering → Partner (not CEO)
  └─ BU Head → Partner (not CEO)

LEVEL 1: Executive / Org-Wide (report to CEO only)
  └─ Partner → CEO
  └─ CFO → CEO (org-wide)
  └─ CWP → CEO (org-wide)

LEVEL 0: C-Suite
  └─ CEO (reports to nobody)
```

**Key Rule:** Parent must be at LOWER hierarchy_level number (higher authority).

## Implementation

### 1. Validation Service

**File:** `backend/app/services/org_hierarchy_validator.py`

```python
from app.services.org_hierarchy_validator import validate_before_employee_creation

# Before creating a user with role:
is_valid, error_msg = validate_before_employee_creation(
    db,
    role="Consultant",
    parent_node_id="hiring-manager-node-uuid",  # Valid ✅
    business_unit_id="bu-1"
)

if not is_valid:
    raise HTTPException(400, f"Invalid reporting: {error_msg}")
```

### 2. User Creation Endpoint

**File:** `backend/app/api/v1/endpoints/users.py`

When creating a user with `POST /hr/users/create-with-roles`:

```json
{
  "user_name": "John Doe",
  "user_email": "john@example.com",
  "user_password": "SecurePassword123!",
  "role_template_id": 4,           // Consultant role
  "business_unit_id": "bu-uuid",   // Their BU
  "parent_node_id": "hiring-mgr-uuid"  // Who they report to (VALIDATED)
}
```

**Flow:**
```
1. Validate user doesn't exist
2. Get role from role_template_id (Consultant)
3. Call validate_before_employee_creation()
   ├─ Check role exists: YES
   ├─ Check parent role is valid: Hiring Manager OK
   ├─ Check hierarchy levels: Consultant(5) < Hiring Manager(4) ✅
   ├─ Check BU consistency: Same BU ✅
   └─ Check no circular reporting: No ✅
4. Create user
5. Create OrgNode with validated parent_node_id
```

### 3. Response

**Success (200):**
```json
{
  "user_id": "new-user-uuid",
  "user_name": "John Doe",
  "user_email": "john@example.com",
  "created_at": "2026-08-27T10:30:00Z"
}
```

**Failure (400):**
```json
{
  "detail": "Invalid reporting structure: Consultant cannot report to CEO. Consultants cannot report directly to CEO - they must go through: Hiring Manager → BU Head → Partner → CEO"
}
```

## Validation Examples

### Example 1: Valid Consultant Hire

```
User: Alice (Consultant)
Parent: Bob (Hiring Manager, Level 4)
Validation:
  ✅ Consultant is Level 5
  ✅ Hiring Manager is Level 4 (higher authority)
  ✅ Both in same BU
  ✅ No circular reporting
Result: ACCEPTED
```

### Example 2: Invalid Direct Report to CEO

```
User: Alice (Consultant)
Parent: CEO (Level 0)
Validation:
  ✅ Consultant is Level 5
  ✗ CEO is Level 0 (but skips 4 levels!)
  ✗ Cannot skip Hiring Manager → BU Head → Partner
Result: REJECTED
Error: "Consultant cannot report directly to CEO - they must go through: 
         Hiring Manager → BU Head → Partner → CEO"
```

### Example 3: Invalid Same-Level Report

```
User: Alice (BU Head, Level 2)
Parent: Bob (Partner, Level 1)  
BUT Bob's BU is different!
Validation:
  ✅ BU Head is Level 2
  ✅ Partner is Level 1 (higher)
  ✗ Different business units (BU A vs BU B)
Result: REJECTED
Error: "BU Head is in BU A but reports to someone in BU B"
```

### Example 4: Circular Reporting

```
User: Alice (BU Head, Level 2)
Parent: Bob (Partner, Level 1)
BUT Bob reports to Alice!
Validation:
  ✅ Level check OK
  ✗ Circular reporting detected (A → B → A)
Result: REJECTED
Error: "Circular reporting detected - would create infinite loop"
```

## Role Hierarchy Matrix

| Role | Level | Can Report To | Cannot Report To |
|------|-------|--|--|
| Consultant | 5 | Hiring Manager | Everyone else (esp. not CEO) |
| Engineer | 5 | VP Engineering, Lead | Management above their chain |
| Recruiter | 5 | Hiring Manager, Workforce Ops | Finance, Delivery |
| Hiring Manager | 4 | Workforce Ops, BU Head | Partner, CEO (skip levels) |
| Delivery Manager | 3 | BU Head | Partner (wrong domain) |
| Finance Manager | 3 | BU Head | CFO (unless org-wide) |
| Workforce Ops Manager | 3 | BU Head | CWP (dual-report only) |
| Account Manager | 3 | Partner, BU Head | CEO (skip level) |
| VP Engineering | 2 | Partner | CEO (no direct) |
| BU Head | 2 | Partner | CEO (no direct) |
| Partner | 1 | CEO | Anyone else |
| CFO | 1 | CEO | Anyone else (org-wide) |
| CWP | 1 | CEO | Anyone else (org-wide) |
| CEO | 0 | Nobody | Everyone is their report |

## Enforcement in Task Escalation

When a task/operation fails and escalates:

```
Task fails: Delivery Agent → BU Head
  ✓ Validated: Delivery roles report to BU Head

Task escalates: BU Head → Partner
  ✓ Validated: BU Head reports to Partner

Task escalates: Partner → CEO
  ✓ Validated: Partner reports to CEO

Final escalation: CEO makes decision
  ✓ CEO is top level - no further escalation
```

## Testing Validation

### Test Valid Creation

```bash
curl -X POST http://localhost:8080/hr/users/create-with-roles \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "user_name": "John Smith",
    "user_email": "john@example.com",
    "user_password": "SecurePass123!",
    "role_template_id": 4,
    "business_unit_id": "bu-uuid",
    "parent_node_id": "hiring-manager-uuid"  # Valid parent
  }'

# Returns: 200 OK, user created
```

### Test Invalid Creation (Consultant → CEO)

```bash
curl -X POST http://localhost:8080/hr/users/create-with-roles \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "user_name": "Jane Doe",
    "user_email": "jane@example.com",
    "user_password": "SecurePass123!",
    "role_template_id": 4,  # Consultant
    "business_unit_id": "bu-uuid",
    "parent_node_id": "ceo-uuid"  # INVALID - CEO
  }'

# Returns: 400 Bad Request
# Error: "Invalid reporting structure: Consultant cannot report to CEO..."
```

## Database Schema

### org_nodes table

```sql
CREATE TABLE org_nodes (
  id UUID PRIMARY KEY,
  user_id UUID FK → Users.UserID,
  parent_node_id UUID FK → OrgNode.id,  -- Who they report to
  hierarchy_level INTEGER,  -- 0=CEO, 1=C-level, 2=VP, 3=Manager, 4=Lead, 5=IC
  authority_level VARCHAR(50),  -- INDIVIDUAL, TEAM, DEPARTMENT, DIVISION, EXECUTIVE, BOARD
  business_unit_id UUID FK,
  -- ... other fields
);
```

**Key Constraint:** `hierarchy_level` of child MUST be > parent's `hierarchy_level`.

### Validation Logic

In `org_hierarchy_validator.py`:

```python
# Parent must be at lower level number (higher in org)
if parent.hierarchy_level >= employee_level:
    raise ValueError(
        f"Invalid hierarchy: {employee_role} (level {employee_level}) "
        f"cannot report to someone at level {parent_level}. "
        f"Parent must be at higher level."
    )
```

## Integration with Forecasting

When forecasting detects a gap and needs to escalate:

```python
# System already knows who to contact based on hierarchy
recruitment_gap = forecast_recruitment_needs(db)

# Escalation node is determined by org hierarchy, not hardcoded
escalation_to_node_id = recruitment_gap["escalation_node"]  # VP Engineering node

# Query org hierarchy to find all people at that level
managers = db.query(OrgNode).filter(
    OrgNode.hierarchy_level == 2,  # VP Engineering is Level 2
    OrgNode.user_id == current_user.UserID
).all()
```

## Changing Reporting Structure

To move someone to a different supervisor:

```python
# Update OrgNode.parent_node_id
# But first validate the NEW parent_node_id!

is_valid, error_msg = validate_before_employee_creation(
    db,
    role=employee.role,
    parent_node_id=new_parent_node_id,  # Validated!
    business_unit_id=employee.business_unit_id
)

if is_valid:
    org_node.parent_node_id = new_parent_node_id
    db.commit()
else:
    raise ValueError(error_msg)
```

## Admin Guidance

**You should get this error if:**
- ✗ Trying to make Consultant report to CEO (skip 4 levels)
- ✗ Trying to make BU Head report to CFO (wrong domain)
- ✗ Trying to make anyone report to themselves (circular)
- ✗ Trying to assign someone to parent in different BU (unless org-wide)

**Fix by:**
- ✓ Assign to correct intermediate manager (Hiring Manager → BU Head)
- ✓ Use org-wide roles (CFO, CWP) for cross-BU authority
- ✓ Ensure all users in same BU report through BU's hierarchy
- ✓ Use init script to verify org structure: `python backend/scripts/init_org_hierarchy.py`

## Related Files

- `backend/app/services/org_hierarchy_validator.py` - Validation logic
- `backend/app/models/org_hierarchy.py` - OrgNode schema
- `backend/app/api/v1/endpoints/users.py` - User creation with validation
- `backend/app/schemas/user.py` - CreateUserWithRolesRequest schema
- `backend/scripts/init_org_hierarchy.py` - Initialize hierarchy

## See Also

- [Spartan Architecture](SPARTAN_AUTONOMOUS_FORECASTING_COMPLETE.md)
- [Spartan Init README](backend/scripts/SPARTAN_INIT_README.md)
- [Organization Hierarchy Model](backend/app/models/org_hierarchy.py)
