---
name: Org Hierarchy 17-Level + Specialization Integration
description: Complete guide for integrating 17-level hierarchy with specialization into UI, API, and database
metadata:
  type: Integration Guide
  status: CRITICAL - Foundation for org structure
  scope: Complete end-to-end integration
  created: 2026-08-27
---

# Organization Hierarchy Integration Guide (17 Levels + Specializations)

## Overview

The organization now operates with a **proper 17-level hierarchy** with **specialization domains**. Every employee MUST have:

1. **hierarchy_level** (1-17): Their position in the org structure
   - 1: Intern → 17: CEO
   - Defines authority, decision-making power, and reporting structure

2. **specialization**: Their day-to-day expertise domain
   - Recruitment, Development, HR, Finance, Project Management, QA, Business Analysis
   - Ensures people report to managers in the same specialization domain

## What Changed (2026-08-27 Session)

### 1. Database Schema Updates (Migration: 2026_08_27_org_hierarchy_levels)

**OrgNode Table:**
- ✅ Added `specialization` column (VARCHAR(100), NOT NULL)
- ✅ Updated `hierarchy_level` comment from "0-5" to "1-17"

**RoleTemplate Table:**
- ✅ Added `hierarchy_level` column (INT, DEFAULT 5)
- ✅ Added `specialization` column (VARCHAR(100), DEFAULT "General")
- These tie roles to the 17-level system

**Migration File:**
```
backend/alembic/versions/2026_08_27_org_hierarchy_17_levels_and_specialization.py
```

### 2. Backend Model Updates

**OrgNode Model (org_hierarchy.py):**
```python
class OrgNode(Base):
    hierarchy_level = Column(Integer, nullable=False)  # 1-17: Intern → CEO
    specialization = Column(String(100), nullable=False)  # Recruitment, Development, etc.
    parent_node_id = Column(String(36))  # Who they report to
```

**RoleTemplate Model (role_template.py):**
```python
class RoleTemplate(Base):
    hierarchy_level = Column(Integer, nullable=False, default=5)  # 1-17
    specialization = Column(String(100), nullable=False, default="General")  # Domain
```

### 3. Validator Rebuilt (org_hierarchy_validator.py)

**Old System (DELETED):**
- ❌ Simplified 5-level hierarchy
- ❌ Hardcoded role-based mapping
- ❌ No specialization support

**New System (COMPLETE REWRITE):**
- ✅ 17-level hierarchy (Intern → CEO)
- ✅ Specialization validation
- ✅ Dynamic parent level calculation (`get_valid_parent_levels()`)
- ✅ Specialization domain enforcement
- ✅ Circular reporting detection

**New Validator Signature:**
```python
is_valid, error_msg = validate_before_employee_creation(
    session=db,
    hierarchy_level=5,              # MANDATORY: 1-17
    specialization="Recruitment",   # MANDATORY: domain
    parent_node_id="mgr-uuid",      # Optional: who they report to
    business_unit_id="bu-uuid"      # Optional: BU scoping
)
```

### 4. API Schema Updates (schemas/user.py)

**CreateUserWithRolesRequest:**
```python
class CreateUserWithRolesRequest(BaseModel):
    user_name: str  # Required
    user_email: str  # Required
    user_password: str  # Required
    role_template_id: int  # Required
    hierarchy_level: int  # ✅ MANDATORY: 1-17
    specialization: str  # ✅ MANDATORY: domain
    parent_node_id: Optional[str]  # Optional: validated parent
    business_unit_id: Optional[int]  # Optional: BU scoping
    job_title: Optional[str]  # Optional
```

### 5. Endpoint Updates (endpoints/users.py)

**POST /hr/users/create-with-roles - UPDATED:**

✅ **Now Requires:**
- `hierarchy_level` (1-17)
- `specialization` (domain)

✅ **Now Validates:**
- Hierarchy level within valid range
- Specialization from approved list
- Parent reporting relationship (if parent_node_id provided)
- Specialization alignment (non-executive roles must report within same domain)

✅ **Now Creates:**
- OrgNode with validated hierarchy_level + specialization
- Sets node name to `"{UserName} - {Specialization}"`

**Example Request:**
```json
{
  "user_name": "Sarah Chen",
  "user_email": "sarah@example.com",
  "user_password": "SecurePass123!",
  "role_template_id": 3,
  "hierarchy_level": 5,
  "specialization": "Recruitment",
  "parent_node_id": "hiring-manager-uuid",
  "business_unit_id": 1
}
```

## Integration Checklist

### Backend (70% COMPLETE)

- ✅ OrgNode model updated
- ✅ RoleTemplate model updated
- ✅ Validator completely rewritten (17 levels + specialization)
- ✅ CreateUserWithRolesRequest schema updated (hierarchy_level + specialization MANDATORY)
- ✅ create_user_with_roles endpoint updated to validate + create OrgNode
- ✅ Alembic migration created
- ⏳ **PENDING:** Run migration (alembic upgrade head)

### Frontend (0% COMPLETE)

**Priority 1 - User Creation Form:**
- ❌ Add hierarchy_level dropdown (1-17, show level names)
- ❌ Add specialization dropdown (Recruitment, Development, HR, Finance, PM, QA, BA)
- ❌ Make both fields REQUIRED on the form
- ❌ Add validation: show error if user tries to save without selecting both
- ❌ Wire form to POST /hr/users/create-with-roles with new fields

**Priority 2 - Employee Conversion:**
- ❌ Update /employees/convert-from-candidate form
- ❌ Add hierarchy_level selection
- ❌ Add specialization selection
- ❌ Make both MANDATORY before conversion

**Priority 3 - Org Chart Display:**
- ❌ Show "Title - Specialization" format (e.g., "Senior Consultant - Recruitment")
- ❌ Group by specialization domain

**Priority 4 - Parent Node Selector:**
- ❌ When user selects hierarchy_level + specialization, fetch valid supervisors
- ❌ Call GET /hr/valid-supervisors?hierarchy_level=5&specialization=Recruitment
- ❌ Display only valid parents in dropdown

### Database (NEEDS EXECUTION)

- ⏳ Run Alembic migration:
  ```bash
  cd backend
  alembic upgrade head
  ```

### Testing (NEEDS EXECUTION)

**Unit Tests:**
- ❌ Test validator with all 17 levels
- ❌ Test specialization validation
- ❌ Test level-skipping rejection
- ❌ Test specialization domain enforcement
- ❌ Test circular reporting detection

**Integration Tests:**
- ❌ Create user with valid hierarchy_level + specialization
- ❌ Create user with invalid level (0 or 18) → should fail
- ❌ Create user with invalid specialization → should fail
- ❌ Create user with mismatched specializations (Dev reporting to Recruitment) → should fail
- ❌ Create consultant (L4) reporting to CEO (L17) → should fail (skips 13 levels)

## Hierarchy Levels Reference

| Level | Title | Typical Role | Reports To |
|-------|-------|--------------|-----------|
| 1 | Intern | Intern - [Spec] | 2-3 |
| 2 | Associate | Associate - [Spec] | 3-4 |
| 3 | Senior Associate | Senior Associate - [Spec] | 4-5 |
| 4 | Consultant | Consultant - [Spec] | 5-7 |
| 5 | Senior Consultant | Senior Consultant - [Spec] | 6-8 |
| 6 | Lead Consultant | Lead Consultant - [Spec] | 8-9 |
| 7 | Associate Manager | Associate Manager - [Spec] | 9-10 |
| 8 | Manager | Manager - [Spec] | 9-11 |
| 9 | Senior Manager | Senior Manager - [Spec] | 10-12 |
| 10 | Assistant Director | Assistant Director - [Spec] | 11-13 |
| 11 | Director | Director - [Spec] | 12-14 |
| 12 | Senior Director | Senior Director - [Spec] | 13-15 |
| 13 | Assistant VP | AVP - [Spec] | 14-15 |
| 14 | Vice President | VP - [Spec] | 15-16 |
| 15 | Senior VP | SVP - [Spec] | 16-17 |
| 16 | Partner/C-Level | Partner - [Spec] or CFO/CWP | 17 |
| 17 | CEO | Chief Executive | None |

## Specializations Reference

```
Recruitment:
- Sourcer, Coordinator, Recruiter, Manager, Director, VP, SVP, Partner

Development:
- Junior Dev, Developer, Senior Dev, Lead Engineer, Manager, Director, VP, SVP, CTO/Partner

HR:
- HR Coordinator, Administrator, Specialist, Manager, Director, VP, SVP, CWP/Partner

Finance:
- Accountant, Analyst, Senior Analyst, Lead Accountant, Manager, Director, VP, SVP, CFO/Partner

Project Management:
- Coordinator, PM, Senior PM, Lead PM, Manager, Director, VP, SVP, Partner

QA:
- QA Coordinator, QA Engineer, Senior QA, Lead QA, Manager, Director, VP, SVP, Partner

Business Analysis:
- BA Coordinator, BA, Senior BA, Lead BA, Manager, Director, VP, SVP, Partner
```

## API Endpoints

### Already Updated

**POST /hr/users/create-with-roles**
- Now REQUIRES hierarchy_level and specialization
- Now creates OrgNode with validated fields

### Need to Be Created

**GET /hr/valid-supervisors**
```
Parameters:
  - hierarchy_level: int (1-17)
  - specialization: str
  - business_unit_id: optional

Response:
[
  {
    "org_node_id": "uuid",
    "name": "John Manager - Recruitment",
    "hierarchy_level": 8,
    "specialization": "Recruitment",
    "email": "john@example.com"
  },
  ...
]
```

**POST /employees/convert-from-candidate**
- Needs update to require hierarchy_level + specialization
- Should validate reporting relationships

## Error Messages

**When hierarchy_level is missing:**
```
"400 Bad Request: hierarchy_level is required (1-17)"
```

**When specialization is missing:**
```
"400 Bad Request: specialization is required (Recruitment, Development, HR, Finance, Project Management, QA, Business Analysis)"
```

**When hierarchy_level is invalid:**
```
"400 Bad Request: Invalid hierarchy level: 0. Must be 1-17."
```

**When specialization is invalid:**
```
"400 Bad Request: Unknown specialization: Marketing. Valid: Recruitment, Development, HR, Finance, Project Management, QA, Business Analysis"
```

**When reporting relationship violates specialization rule:**
```
"400 Bad Request: Senior Consultant in Development cannot report to Manager in Recruitment. Reporting must stay within same specialization domain."
```

**When reporting relationship skips too many levels:**
```
"400 Bad Request: Consultant (Level 4) cannot report to CEO (Level 17). Valid parent levels: Lead Consultant (6), Associate Manager (7), Manager (8) (levels [6, 7, 8])"
```

## Frontend Integration Examples

### Example 1: Create Recruitment Manager

**Form Inputs:**
- Name: "Alice Johnson"
- Email: "alice@example.com"
- Password: "SecurePass123!"
- Role: "Manager" (role_template_id=8)
- **Hierarchy Level: 8** (Manager)
- **Specialization: Recruitment**
- Parent: Select "Sarah Chen - Recruitment" (Senior Manager)
- Business Unit: "US - NA"

**API Request:**
```json
{
  "user_name": "Alice Johnson",
  "user_email": "alice@example.com",
  "user_password": "SecurePass123!",
  "role_template_id": 8,
  "hierarchy_level": 8,
  "specialization": "Recruitment",
  "parent_node_id": "sarah-chen-uuid",
  "business_unit_id": 1
}
```

**Result:**
- User created
- OrgNode created: "Alice Johnson - Recruitment", L8, reports to Sarah Chen
- Alice can now manage Recruitment team members

### Example 2: Create Developer with Invalid Parent (SHOULD FAIL)

**Form Inputs:**
- Name: "Bob Smith"
- Email: "bob@example.com"
- Role: "Developer"
- **Hierarchy Level: 4** (Consultant level)
- **Specialization: Development**
- Parent: "Sales Manager - Recruitment" (WRONG SPECIALIZATION)

**API Request:**
```json
{
  "user_name": "Bob Smith",
  "user_email": "bob@example.com",
  "user_password": "SecurePass123!",
  "role_template_id": 5,
  "hierarchy_level": 4,
  "specialization": "Development",
  "parent_node_id": "sales-mgr-uuid"
}
```

**Result: ❌ REJECTED**
```
400 Bad Request: Consultant in Development cannot report to Manager in Recruitment. 
Reporting must stay within same specialization domain.
```

### Example 3: Create HR Coordinator

**Form Inputs:**
- Name: "Carol White"
- Email: "carol@example.com"
- Role: "HR Coordinator"
- **Hierarchy Level: 2** (Associate)
- **Specialization: HR**
- Parent: "HR Manager - HR" (Level 8)
- Business Unit: "US - NA"

**API Request:**
```json
{
  "user_name": "Carol White",
  "user_email": "carol@example.com",
  "user_password": "SecurePass123!",
  "role_template_id": 15,
  "hierarchy_level": 2,
  "specialization": "HR",
  "parent_node_id": "hr-mgr-uuid",
  "business_unit_id": 1
}
```

**Result: ✅ ACCEPTED**
- User created
- OrgNode: "Carol White - HR", L2, reports to HR Manager
- Carol has HR Coordinator responsibilities

## FAQ

### Q: Can a Senior Consultant (L5) report to an Associate Manager (L7)?
**A:** Yes. Valid parent levels for L5 are [6, 7, 8], so both Lead Consultant (L6) and Associate Manager (L7) are valid parents.

### Q: Can a Dev report to a Recruitment manager?
**A:** No. Non-executive roles (L < 13) must report within same specialization domain. Dev must report to Dev managers.

### Q: Can a Partner (L16) in Finance report to Partner (L16) in Development?
**A:** No. They're the same level. Must report to someone at higher level (L17 = CEO).

### Q: What if we hire someone without a specialization?
**A:** They must still have a specialization. Use "General" as fallback, but assign to the domain they actually work in.

### Q: Can we change someone's hierarchy_level after creating them?
**A:** Yes, via OrgNode update. But this will re-validate their parent relationship. If new level is incompatible with current parent, the update will be rejected.

## What's Next (After Integration)

1. ✅ Models updated
2. ✅ Validator rebuilt
3. ✅ API schema updated
4. ✅ Endpoint updated
5. ✅ Migration created
6. ⏳ **Run migration** (alembic upgrade head)
7. ⏳ Update frontend forms (add hierarchy_level + specialization dropdowns)
8. ⏳ Update employee conversion flow
9. ⏳ Wire parent supervisor selector
10. ⏳ Add validation tests
11. ⏳ Test end-to-end

## Files Modified

**Backend:**
- ✅ `backend/app/models/org_hierarchy.py` - Added specialization to OrgNode
- ✅ `backend/app/models/role_template.py` - Added hierarchy_level + specialization
- ✅ `backend/app/services/org_hierarchy_validator.py` - Complete rewrite (17 levels)
- ✅ `backend/app/schemas/user.py` - hierarchy_level + specialization MANDATORY
- ✅ `backend/app/api/v1/endpoints/users.py` - Updated create_user_with_roles
- ✅ `backend/alembic/versions/2026_08_27_org_hierarchy_17_levels_and_specialization.py` - Migration

**Frontend:**
- ❌ Not yet started

**Documentation:**
- ✅ `ORG_HIERARCHY_LEVELS.md` - Hierarchy reference
- ✅ `HIERARCHY_ENFORCEMENT.md` - Validation rules
- ✅ `ORG_HIERARCHY_INTEGRATION_GUIDE.md` - This file

## Support

See `ORG_HIERARCHY_LEVELS.md` for complete hierarchy definitions.
See `HIERARCHY_ENFORCEMENT.md` for validation rules and examples.
