# RBAC Implementation Plan: Multi-Role + BU Filtering + Employee Conversion

## Overview
Implementing comprehensive RBAC with:
1. **Multi-role support** - Users can have multiple roles simultaneously
2. **Business Unit (BU) filtering** - Data scoped by BU ownership
3. **Employee conversion** - Candidate → Employee with role/BU assignment

---

## Phase 1: Database Schema ✅
- [x] Added `business_unit_id` to `users` table
- [x] Created `user_roles` table (many-to-many role assignment)
- [x] Created `business_unit_access` table (BU permissions)
- [x] Created 3 business units: NA, EU, APAC
- [x] Assigned users to BUs

## Phase 2: Backend Model Updates

### 2.1 Update Users Model
File: `app/models/user.py`

```python
from sqlalchemy.orm import relationship

class Users(Base):
    # ... existing fields ...
    business_unit_id = Column(Integer, ForeignKey('business_units.id'))
    business_unit = relationship("BusinessUnit")
    
    # Many-to-many relationship to roles
    roles = relationship(
        "Role",
        secondary="user_roles",
        foreign_keys="[user_roles.c.user_id, user_roles.c.role_id]"
    )

class UserRole(Base):
    __tablename__ = "user_roles"
    id = Column(String(255), primary_key=True)
    user_id = Column(String(255), ForeignKey('users.UserID'), unique=True)
    role_id = Column(Integer, ForeignKey('roles.id'))
    business_unit_id = Column(Integer, ForeignKey('business_units.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 2.2 Update Login Response
File: `app/schemas/auth.py`

```python
class LoginResponse(BaseModel):
    entity_type: str
    access_token: str
    user_id: str
    user_name: str
    user_email: str
    user_role: str  # Legacy, keep for compatibility
    business_unit_id: Optional[int]
    business_unit_name: Optional[str]
    roles: List[str]  # List of all role names
    permissions: List[str]  # Flattened list of all permissions
    # ... existing fields ...
```

## Phase 3: Backend Endpoints

### 3.1 Updated User Creation - WITH BU and Multi-Roles
File: `app/api/v1/endpoints/users.py`

```python
class UserCreateRequest(BaseModel):
    user_name: str
    user_email: str
    user_password: str
    business_unit_id: int
    role_ids: List[int]  # List of role IDs to assign

@router.post("/users/create")
def create_user_with_roles(
    request: UserCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    # Verify user can only create users in their BU
    if user.business_unit_id != request.business_unit_id:
        raise HTTPException(status_code=403, detail="Cannot create users outside your BU")
    
    # Create user
    new_user = Users(
        UserID=user_id_generator(),
        UserName=request.user_name,
        UserEmail=request.user_email,
        UserPassword=get_password_hash(request.user_password),
        business_unit_id=request.business_unit_id
    )
    db.add(new_user)
    db.flush()
    
    # Assign roles
    for role_id in request.role_ids:
        user_role = UserRole(
            id=f"ur_{new_user.UserID}_{role_id}",
            user_id=new_user.UserID,
            role_id=role_id,
            business_unit_id=request.business_unit_id
        )
        db.add(user_role)
    
    db.commit()
    return new_user
```

### 3.2 Employee Conversion Endpoint
File: `app/api/v1/endpoints/employees.py` (NEW)

```python
class EmployeeConversionRequest(BaseModel):
    candidate_id: str
    employee_name: str
    employee_email: str
    business_unit_id: int
    role_ids: List[int]
    position: str
    joining_date: date

@router.post("/candidates/{candidate_id}/convert-to-employee")
def convert_candidate_to_employee(
    candidate_id: str,
    request: EmployeeConversionRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_hr_or_admin)
):
    # Get candidate
    candidate = db.query(Candidate).filter(Candidate.CandidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404)
    
    # Check BU permissions
    if user.business_unit_id != request.business_unit_id:
        raise HTTPException(status_code=403)
    
    # Create employee user
    employee_user = Users(
        UserID=user_id_generator(),
        UserName=request.employee_name,
        UserEmail=request.employee_email,
        UserPassword=generate_password(),  # Auto-generate
        business_unit_id=request.business_unit_id,
        candidate_id=candidate_id
    )
    db.add(employee_user)
    db.flush()
    
    # Assign roles
    for role_id in request.role_ids:
        user_role = UserRole(
            id=f"ur_{employee_user.UserID}_{role_id}",
            user_id=employee_user.UserID,
            role_id=role_id,
            business_unit_id=request.business_unit_id
        )
        db.add(user_role)
    
    # Update candidate status
    candidate.status = "CONVERTED_TO_EMPLOYEE"
    candidate.candidate_employee_user_id = employee_user.UserID
    
    db.commit()
    return {"status": "success", "employee_user_id": employee_user.UserID}
```

### 3.3 BU-Scoped Queries
Add to all GET endpoints:

```python
# Filter by current user's BU
candidates = db.query(Candidate).filter(
    Candidate.business_unit_id == current_user.business_unit_id
).all()
```

## Phase 4: Frontend Updates

### 4.1 Dynamic Navigation Bar
File: `src/components/Navigation.js`

Show/hide menu items based on user's roles and permissions:

```javascript
const Navigation = ({ user }) => {
  const hasRole = (roleName) => user.roles.includes(roleName);
  const hasPermission = (perm) => user.permissions.includes(perm);
  
  return (
    <>
      {hasPermission('recruitment.view') && (
        <NavItem href="/recruitment">Recruitment</NavItem>
      )}
      {hasRole('Admin') && (
        <NavItem href="/admin">Admin</NavItem>
      )}
      {hasRole('Finance') && (
        <NavItem href="/finance">Finance</NavItem>
      )}
    </>
  );
};
```

### 4.2 Update User Creation Form
File: `src/screens/UsersAndAccessControl.js`

Add BU dropdown and multi-role selection:

```javascript
const [formData, setFormData] = useState({
  user_name: '',
  user_email: '',
  user_password: '',
  business_unit_id: null,
  role_ids: []  // Array of role IDs
});

// Show BU dropdown
<Select 
  label="Business Unit" 
  value={formData.business_unit_id}
  onChange={(value) => setFormData({...formData, business_unit_id: value})}
  options={businessUnits}
/>

// Show multi-select roles
<MultiSelect
  label="Roles"
  value={formData.role_ids}
  onChange={(values) => setFormData({...formData, role_ids: values})}
  options={roles}
/>
```

### 4.3 Employee Conversion Screen (NEW)
File: `src/screens/EmployeeConversion.js`

Screen to convert candidate to employee with:
- BU selection
- Multi-role selection
- Employee details (name, email, position, joining date)
- Auto-generates password

---

## Permission Structure

### Standard Permissions by Role

**Super User**: ALL permissions
- `*.*` (all modules, all actions)

**Admin**: 
- `user.manage`
- `role.manage`
- `candidate.*`
- `employee.*`
- `business_unit.manage`

**Recruiter** (Senior Recruiter):
- `candidates.view`
- `candidate.create`
- `candidate.edit`
- `candidate.delete`
- `recruitment.view`
- `interview.manage`

**HR Manager**:
- `candidates.view`
- `candidate.edit`
- `employee.manage`
- `employee.view`
- `reports.view`

**Finance**:
- `invoices.view`
- `invoices.manage`
- `reports.financial`

**Partner**:
- `business_unit.manage`
- `employee.manage`
- `team.view`

**BU Head**:
- `business_unit.view`
- `employee.manage`
- `recruitment.view`
- `reports.view`

---

## Implementation Order

1. ✅ Database schema updates
2. → Update Users model with relationships
3. → Update login endpoint to return roles + permissions
4. → Create/update user creation endpoint
5. → Create employee conversion endpoint
6. → Implement BU filtering in all queries
7. → Update frontend navigation to be dynamic
8. → Add BU selection to user creation form
9. → Create employee conversion screen

---

## Testing Checklist

- [ ] Create user with BU + multiple roles
- [ ] Verify login returns all roles and permissions
- [ ] Verify navigation shows only permitted modules
- [ ] Convert candidate to employee with role selection
- [ ] Verify BU filtering (Troy sees only his BU data)
- [ ] Verify multi-role permissions combine correctly
- [ ] Test Super User access to everything

