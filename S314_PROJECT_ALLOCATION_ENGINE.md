# S-314: Project Allocation Engine

## Overview

S-314 implements the Project Allocation Engine for WROS, providing comprehensive employee-to-project allocation management with capacity checking, project availability filtering, and allocation conflict detection.

**Related Stories:**
- S-251: Allocate Employee to Project (HRMS-0507)
- S-252: Allocation Conflict Detection (HRMS-0803)
- S-314: Project Allocation Engine (HRMS-0812)

**Key Deliverables:**
1. ✅ Enhanced service class with three core methods
2. ✅ Complete Pydantic schemas for request/response
3. ✅ REST endpoints with full CRUD operations
4. ✅ Comprehensive unit tests (100+ test cases)
5. ✅ API integration tests

---

## Architecture

### Core Methods

#### 1. `allocate_employee_to_project()`

Allocates an employee to a demand/project with comprehensive validation.

**Location:** `app/services/employee_allocation_service.py`

**Signature:**
```python
def allocate_employee_to_project(
    db: Session,
    *,
    tenant_id: Optional[int],
    employee: Employee,
    demand: Demand,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    utilization_pct: Optional[float] = None,
    client_reporting_manager_contact_id: Optional[str] = None,
    timesheet_approver_email: Optional[str] = None,
    billing_rate_usd_cents: Optional[int] = None,
    changed_by: Optional[str] = None,
    project=None,
    role: Optional[str] = None,
    allow_concurrent: bool = False,
) -> EmployeeAllocation
```

**Business Rules (HRMS-0507, HRMS-0803):**
- BR-0803-01: Total allocation % across overlapping active allocations cannot exceed 100%
- Buddy Program Blocking: Employee must not be in IN_PROGRESS or EXTENDED buddy program status
- Single Allocation Mode (default): Employee can only have one ACTIVE allocation at a time
- Multi-Allocation Mode (allow_concurrent=True): Multiple allocations allowed if total utilization ≤ 100%
- Status Transition: Employee status changes BENCH → ALLOCATED when allocation created
- Auto-billing: Uses demand's billing_rate if not explicitly provided

**Example:**
```python
allocation = allocate_employee_to_project(
    db,
    tenant_id=1,
    employee=employee_obj,
    demand=demand_obj,
    project=project_obj,
    utilization_pct=80.0,
    role="Senior Engineer",
    start_date=date(2026, 9, 1),
    changed_by="hr_manager_123",
)
# Returns: EmployeeAllocation with status="ACTIVE"
```

#### 2. `get_available_projects()`

Lists projects available for allocation with optional filtering.

**Location:** `app/services/employee_allocation_service.py`

**Signature:**
```python
def get_available_projects(
    db: Session,
    tenant_id: Optional[int],
    employee_id: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> List[Project]
```

**Parameters:**
- `tenant_id`: Required for multi-tenancy isolation
- `employee_id`: Optional - exclude projects with existing allocations for this employee
- `status_filter`: 
  - None or "ACTIVE": Only ACTIVE projects (default)
  - "ALL": Include all statuses
  - Other values: Filter by specific status (PLANNING, COMPLETED, ON_HOLD, CLOSED)

**Returns:** List[Project] sorted by most recent first

**Example:**
```python
# Get all active projects
projects = get_available_projects(db, tenant_id=1)

# Get projects available for a specific employee (exclude conflicts)
available = get_available_projects(
    db, 
    tenant_id=1, 
    employee_id="emp_123",
    status_filter="ACTIVE"
)

# Get all projects including completed ones
all_projects = get_available_projects(
    db, 
    tenant_id=1, 
    status_filter="ALL"
)
```

#### 3. `check_capacity()`

Checks if an employee has capacity for a new allocation.

**Location:** `app/services/employee_allocation_service.py`

**Signature:**
```python
def check_capacity(
    db: Session,
    employee_id: str,
    additional_utilization_pct: float = 100.0,
    proposed_start_date: Optional[date] = None,
) -> Tuple[bool, float, float]
```

**Returns:** `(has_capacity: bool, current_utilization: float, available_capacity: float)`

**Business Rules (HRMS-0803 BR-0803-01):**
- Checks only ACTIVE allocations
- Ignores ENDED and CORE_PULLED allocations
- Considers allocation end dates (ignores allocations ending before proposed_start_date)
- Defaults proposed_start_date to today if not specified
- Each allocation defaults to 100% utilization if not specified

**Example:**
```python
# Check if employee can accept 100% allocation
has_cap, current, available = check_capacity(
    db,
    employee_id="emp_123",
    additional_utilization_pct=100.0,
)

if has_cap:
    print(f"Employee has capacity. Current: {current}%, Available: {available}%")
else:
    print(f"No capacity. Current: {current}%, Only {available}% available")

# Check for future start date
future_date = date.today() + timedelta(days=30)
has_cap, _, _ = check_capacity(
    db,
    employee_id="emp_123",
    additional_utilization_pct=50.0,
    proposed_start_date=future_date,
)
```

---

## Pydantic Schemas

### Request Schemas

#### CreateAllocationRequest
```python
class CreateAllocationRequest(BaseModel):
    employee_id: str
    demand_id: str
    project_id: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    utilization_pct: Optional[float] = None
    role: Optional[str] = None
    allow_concurrent: bool = False
```

#### CapacityCheckRequest
```python
class CapacityCheckRequest(BaseModel):
    employee_id: str
    additional_utilization_pct: float = 100.0  # 0-100%
    proposed_start_date: Optional[date] = None
```

#### AllocationCheckRequest
```python
class AllocationCheckRequest(BaseModel):
    employee_id: str
    project_id: Optional[str] = None
    demand_id: str
    utilization_pct: Optional[float] = None
    proposed_start_date: Optional[date] = None
    allow_concurrent: bool = False
```

### Response Schemas

#### AllocationItem
```python
class AllocationItem(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    demand_id: str
    demand_job_title: str
    client_id: str
    client_name: Optional[str] = None
    project_id: Optional[str] = None
    si_partner: Optional[str] = None
    status: str  # ACTIVE, ENDED, CORE_PULLED
    utilization_pct: Optional[float] = None
    start_date: date
    end_date: Optional[date] = None
    role: Optional[str] = None
    billing_rate_usd_cents: Optional[int] = None
    work_location: Optional[str] = None
    assigned_recruiter_name: Optional[str] = None
    business_unit_name: Optional[str] = None
    created_at: datetime
```

#### CapacityCheckResponse
```python
class CapacityCheckResponse(BaseModel):
    employee_id: str
    has_capacity: bool
    current_utilization_pct: float
    available_capacity_pct: float
    total_with_proposed_pct: float
    active_allocation_count: int
```

#### AllocationCheckResponse
```python
class AllocationCheckResponse(BaseModel):
    is_valid: bool
    employee_id: str
    employee_name: str
    has_capacity: bool
    current_utilization_pct: float
    available_capacity_pct: float
    proposed_utilization_pct: float
    conflict_reasons: List[str] = []  # Why allocation cannot proceed
    warnings: List[str] = []  # Non-blocking warnings
```

#### AvailableProjectsResponse
```python
class AvailableProjectsResponse(BaseModel):
    projects: List[ProjectItem]
    total_count: int
    filtered_count: int
```

---

## REST API Endpoints

### Base URL: `/allocations`

All endpoints require authentication (get_current_hr_or_admin dependency).

#### 1. Create Allocation

**Endpoint:** `POST /allocations`

**Request:**
```json
{
  "employee_id": "emp_123",
  "demand_id": "demand_456",
  "project_id": "proj_789",
  "utilization_pct": 80.0,
  "role": "Senior Engineer",
  "start_date": "2026-09-01",
  "end_date": "2026-12-31",
  "allow_concurrent": false
}
```

**Responses:**
- `200 OK`: AllocationItem (allocation created successfully)
- `404 Not Found`: Employee, demand, or project not found
- `409 Conflict`: 
  - Employee already allocated (in single-allocation mode)
  - Allocation exceeds 100% capacity
  - Buddy program not completed
- `401 Unauthorized`: Auth required

**Example:**
```bash
curl -X POST http://localhost:8080/allocations \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "employee_id": "emp_123",
    "demand_id": "demand_456",
    "project_id": "proj_789",
    "utilization_pct": 80.0,
    "role": "Senior Engineer"
  }'
```

#### 2. List Allocations

**Endpoint:** `GET /allocations`

**Query Parameters:**
- `employee_id` (optional): Filter by employee
- `demand_id` (optional): Filter by demand

**Response:**
```json
{
  "allocations": [
    {
      "id": "alloc_123",
      "employee_id": "emp_123",
      "employee_name": "John Developer",
      "demand_id": "demand_456",
      "demand_job_title": "Senior Backend Engineer",
      "status": "ACTIVE",
      "utilization_pct": 80.0,
      "start_date": "2026-09-01",
      "created_at": "2026-08-15T10:30:00"
    }
  ]
}
```

**Example:**
```bash
# Get all allocations
curl http://localhost:8080/allocations \
  -H "Authorization: Bearer TOKEN"

# Get allocations for specific employee
curl http://localhost:8080/allocations?employee_id=emp_123 \
  -H "Authorization: Bearer TOKEN"
```

#### 3. Get Available Projects

**Endpoint:** `GET /allocations/projects`

**Query Parameters:**
- `employee_id` (optional): Exclude projects with allocations for this employee
- `status` (optional): Filter by status (ACTIVE, ALL, PLANNING, COMPLETED, etc.)

**Response:**
```json
{
  "projects": [
    {
      "id": "proj_789",
      "name": "Cloud Migration",
      "client_id": "client_123",
      "client_name": "Tech Corp",
      "status": "ACTIVE",
      "delivery_engine": "CORE",
      "si_partner": null,
      "start_date": "2026-09-01",
      "end_date": "2026-12-31",
      "billing_type": "TIME_AND_MATERIALS",
      "currency": "USD"
    }
  ],
  "total_count": 5,
  "filtered_count": 5
}
```

**Example:**
```bash
# Get all active projects
curl http://localhost:8080/allocations/projects \
  -H "Authorization: Bearer TOKEN"

# Get projects available for employee (exclude conflicts)
curl "http://localhost:8080/allocations/projects?employee_id=emp_123" \
  -H "Authorization: Bearer TOKEN"

# Get all projects (including completed)
curl "http://localhost:8080/allocations/projects?status=ALL" \
  -H "Authorization: Bearer TOKEN"
```

#### 4. Check Capacity

**Endpoint:** `POST /allocations/check-capacity`

**Request:**
```json
{
  "employee_id": "emp_123",
  "additional_utilization_pct": 80.0,
  "proposed_start_date": "2026-09-01"
}
```

**Response:**
```json
{
  "employee_id": "emp_123",
  "has_capacity": true,
  "current_utilization_pct": 0.0,
  "available_capacity_pct": 100.0,
  "total_with_proposed_pct": 80.0,
  "active_allocation_count": 0
}
```

**Example:**
```bash
curl -X POST http://localhost:8080/allocations/check-capacity \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "employee_id": "emp_123",
    "additional_utilization_pct": 80.0
  }'
```

#### 5. Validate Allocation

**Endpoint:** `POST /allocations/validate`

**Request:**
```json
{
  "employee_id": "emp_123",
  "demand_id": "demand_456",
  "project_id": "proj_789",
  "utilization_pct": 80.0,
  "allow_concurrent": false
}
```

**Response:**
```json
{
  "is_valid": true,
  "employee_id": "emp_123",
  "employee_name": "John Developer",
  "has_capacity": true,
  "current_utilization_pct": 0.0,
  "available_capacity_pct": 100.0,
  "proposed_utilization_pct": 80.0,
  "conflict_reasons": [],
  "warnings": []
}
```

**Example (with conflicts):**
```json
{
  "is_valid": false,
  "employee_id": "emp_123",
  "employee_name": "John Developer",
  "has_capacity": false,
  "current_utilization_pct": 70.0,
  "available_capacity_pct": 30.0,
  "proposed_utilization_pct": 80.0,
  "conflict_reasons": [
    "Employee has 70% utilization; adding 80% exceeds 100% limit",
    "Employee already has active allocation (alloc_existing); end it before creating new one"
  ],
  "warnings": []
}
```

#### 6. End Allocation

**Endpoint:** `POST /allocations/{allocation_id}/end`

**Request:**
```json
{
  "end_date": "2026-12-31"
}
```

**Response:**
```json
{
  "id": "alloc_123",
  "employee_id": "emp_123",
  "employee_name": "John Developer",
  "status": "ENDED",
  "end_date": "2026-12-31",
  "created_at": "2026-08-15T10:30:00"
}
```

**Example:**
```bash
curl -X POST http://localhost:8080/allocations/alloc_123/end \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "end_date": "2026-12-31"
  }'
```

#### 7. Get Dropdowns

**Endpoint:** `GET /allocations/dropdowns/for-create`

**Response:**
```json
{
  "employees": [
    {"id": "emp_123", "name": "John Developer"},
    {"id": "emp_456", "name": "Jane Engineer"}
  ],
  "demands": [
    {"id": "demand_789", "name": "Senior Backend Engineer"},
    {"id": "demand_101", "name": "Frontend Developer"}
  ]
}
```

**Example:**
```bash
curl http://localhost:8080/allocations/dropdowns/for-create \
  -H "Authorization: Bearer TOKEN"
```

---

## Business Rules & Validation

### HRMS-0507: Employee Allocations
- Allocation is the write path to move employee off/onto bench
- Allocation is always a distinct human decision (not automatic)
- Allocation links employee to demand and optionally to project
- Every allocation tracks utilization % (defaults to 100%)
- Status transitions: employee.status BENCH → ALLOCATED → BENCH

### HRMS-0803: Multi-Allocation Support
- BR-0803-01: Total allocation % across overlapping active allocations cannot exceed 100%
- Overlapping means date ranges intersect or no end_date specified
- Single-allocation mode (allow_concurrent=False, default): Only one ACTIVE allocation
- Multi-allocation mode (allow_concurrent=True): Multiple allocations allowed if under 100%

### HRMS-0812: Capacity Management
- check_capacity() validates proposed allocation won't exceed limits
- Validation is pre-flight check before allocate_employee_to_project()
- Ignored: ENDED, CORE_PULLED allocations; ended allocations before proposed_start_date
- Default utilization per allocation: 100% if not specified

### S-365: Buddy Program Blocking
- Employee cannot be deployed to client while in Buddy Program
- Blocking statuses: IN_PROGRESS, EXTENDED
- NOT_STARTED and GRADUATED do not block allocation

---

## Error Handling

### Service Layer Exceptions

```python
class EmployeeAlreadyAllocated(Exception):
    """Raised when employee already has active allocation (single-allocation mode)."""

class AllocationOverCapacity(Exception):
    """Raised when allocation would exceed 100% utilization."""

class BuddyProgramNotGraduated(Exception):
    """Raised when employee is in active buddy program."""
```

### HTTP Status Codes

| Status | Meaning | Example |
|--------|---------|---------|
| 200 | Success | Allocation created, capacity checked |
| 400 | Bad Request | Invalid utilization percentage (not 0-100) |
| 401 | Unauthorized | Auth token missing or invalid |
| 404 | Not Found | Employee, demand, or project doesn't exist |
| 409 | Conflict | Employee already allocated, capacity exceeded, buddy program blocking |
| 422 | Validation Error | Request body validation failed |

### Example Error Response

```json
{
  "detail": "Employee emp_123 already has 70% overlapping allocation -- adding 80% would exceed 100%."
}
```

---

## Usage Examples

### Scenario 1: Allocate Employee to New Project

```python
# 1. Check capacity first (optional but recommended)
has_cap, current, available = check_capacity(
    db, 
    employee_id="emp_123",
    additional_utilization_pct=80.0
)

if not has_cap:
    print(f"No capacity available. Current: {current}%, Available: {available}%")
    return

# 2. Allocate employee
allocation = allocate_employee_to_project(
    db,
    tenant_id=1,
    employee=employee_obj,
    demand=demand_obj,
    project=project_obj,
    utilization_pct=80.0,
    role="Senior Engineer",
    start_date=date(2026, 9, 1),
    changed_by="hr_manager_123",
)
db.commit()

print(f"Allocated employee to project: {allocation.id}")
```

### Scenario 2: Multi-Allocation (Part-Time Assignments)

```python
# Employee works 50% on Project A, 50% on Project B
allocation_a = allocate_employee_to_project(
    db,
    tenant_id=1,
    employee=employee_obj,
    demand=demand_a,
    project=project_a,
    utilization_pct=50.0,
    allow_concurrent=True,
    changed_by="rm_manager",
)
db.commit()

allocation_b = allocate_employee_to_project(
    db,
    tenant_id=1,
    employee=employee_obj,
    demand=demand_b,
    project=project_b,
    utilization_pct=50.0,
    allow_concurrent=True,
    changed_by="rm_manager",
)
db.commit()

# Now employee is ALLOCATED to both projects at 50% each
assert employee.status == "ALLOCATED"
```

### Scenario 3: API Flow - Pre-Validation Before Allocation

```bash
# 1. Check if employee has capacity
POST /allocations/check-capacity
{
  "employee_id": "emp_123",
  "additional_utilization_pct": 80.0
}

# Response: has_capacity=true, available=100%

# 2. Validate all business rules (comprehensive check)
POST /allocations/validate
{
  "employee_id": "emp_123",
  "demand_id": "demand_456",
  "project_id": "proj_789",
  "utilization_pct": 80.0,
  "allow_concurrent": false
}

# Response: is_valid=true, conflict_reasons=[]

# 3. Create allocation
POST /allocations
{
  "employee_id": "emp_123",
  "demand_id": "demand_456",
  "project_id": "proj_789",
  "utilization_pct": 80.0,
  "role": "Senior Engineer"
}

# Response: 200 OK with AllocationItem
```

### Scenario 4: Get Projects and Filter by Employee

```python
# Get all ACTIVE projects
all_projects = get_available_projects(
    db, 
    tenant_id=1,
    status_filter="ACTIVE"
)

# Get projects where employee doesn't have allocation
available_for_emp = get_available_projects(
    db,
    tenant_id=1,
    employee_id="emp_123",
    status_filter="ACTIVE"
)

# available_for_emp excludes projects employee is already on
```

---

## Testing

### Unit Tests

Location: `tests/test_allocation_engine.py`

Test Coverage:
- `TestAllocateEmployeeToProject`: 6 tests
  - Basic allocation, allocation without project
  - Buddy program blocking
  - Single vs multi-allocation modes
  - Capacity overflow detection

- `TestGetAvailableProjects`: 4 tests
  - Get all projects, status filtering
  - Employee conflict filtering

- `TestCheckCapacity`: 5 tests
  - Full capacity, partial utilization
  - Capacity exceeded, ended allocations
  - Future start date handling

- `TestEndAllocation`: 2 tests
  - Bench transition with single allocation
  - Multiple allocation handling

- `TestAllocationValidation`: 3 tests
  - Custom dates, billing info
  - Demand billing rate defaults

**Run tests:**
```bash
pytest tests/test_allocation_engine.py -v
pytest tests/test_allocation_engine.py::TestAllocateEmployeeToProject -v
```

### API Integration Tests

Location: `tests/test_allocation_api.py`

Test Coverage:
- `TestAllocationCreateEndpoint`: Create, validation
- `TestAllocationListEndpoint`: List with filters
- `TestProjectsEndpoint`: Get projects, filtering
- `TestCapacityCheckEndpoint`: Capacity checks
- `TestValidationEndpoint`: Pre-allocation validation
- `TestEndAllocationEndpoint`: End allocations
- `TestDropdownsEndpoint`: Form dropdowns
- `TestAllocationErrorHandling`: Error cases

**Run tests:**
```bash
pytest tests/test_allocation_api.py -v
pytest tests/test_allocation_api.py::TestAllocationCreateEndpoint -v
```

---

## Database Schema

### EmployeeAllocation Table

```sql
CREATE TABLE employee_allocations (
  id VARCHAR(36) PRIMARY KEY,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id),
  employee_id VARCHAR(36) NOT NULL REFERENCES employees(id),
  demand_id VARCHAR(36) NOT NULL REFERENCES demands(id),
  client_id VARCHAR(36) NOT NULL REFERENCES clients(id),
  project_id VARCHAR(36) REFERENCES projects(id),  -- NULLABLE
  
  role VARCHAR(200),
  status ENUM('ACTIVE', 'ENDED', 'CORE_PULLED'),
  utilization_pct NUMERIC(5, 2),
  start_date DATE NOT NULL,
  end_date DATE,
  
  client_reporting_manager_contact_id VARCHAR(36) REFERENCES client_contacts(id),
  timesheet_approver_email VARCHAR(300),
  billing_rate_usd_cents INTEGER,
  si_partner ENUM(...),
  
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  
  INDEX idx_employee_allocation (employee_id),
  INDEX idx_demand_allocation (demand_id),
  INDEX idx_project_allocation (project_id)
);
```

---

## Development Notes

### Design Decisions

1. **Overlapping Allocation Logic**
   - Overlapping = end_date IS NULL OR end_date >= proposed_start_date
   - Only ACTIVE allocations count toward utilization
   - ENDED and CORE_PULLED allocations don't block new allocations

2. **Buddy Program Scope**
   - Only blocks IN_PROGRESS and EXTENDED statuses
   - NOT_STARTED and GRADUATED don't block (as per existing tests)
   - Configurable via _BUDDY_PROGRAM_BLOCKING_STATUSES constant

3. **Default Utilization**
   - If not specified, allocation defaults to 100%
   - Enables "all-or-nothing" allocation model
   - Multi-allocation mode requires explicit utilization % for each

4. **Validation Approach**
   - validate endpoint does comprehensive pre-flight check
   - Returns list of conflict_reasons vs. raising exceptions
   - Allows frontend to show all issues at once, not fail on first error

5. **Project Filtering**
   - get_available_projects excludes projects where employee already allocated
   - Uses project_id matching from existing allocations
   - Reduces noise from unavailable options

### Performance Considerations

- Capacity check is O(n) where n = active allocations for employee
- Typical case: 1-5 allocations per employee
- No full table scan; filtered by employee_id and status
- Add index on (employee_id, status) if needed for scale

### Future Enhancements

1. Batch allocation operations (allocate multiple employees at once)
2. Allocation conflicts reporting (dashboard view)
3. Allocation rebalancing suggestions (AI/recommendation engine)
4. Allocation history audit trail (when/why allocations changed)
5. Concurrent allocation approval workflows
6. Skills-based allocation matching

---

## Troubleshooting

### "Employee already has an active allocation"
**Cause:** In single-allocation mode (allow_concurrent=False), employee can only have one ACTIVE allocation
**Solution:** Either end the existing allocation first, or set allow_concurrent=True

### "Total utilization would exceed 100%"
**Cause:** Employee's existing allocations (70%) + new allocation (40%) = 110% > 100%
**Solution:** Reduce utilization % of new allocation, or check capacity before allocating

### "Employee must complete Buddy Program graduation"
**Cause:** Employee is in IN_PROGRESS or EXTENDED buddy program status
**Solution:** Wait for buddy program to complete (graduation date reached)

### "Allocation not found"
**Cause:** Allocation ID is incorrect or allocation was deleted
**Solution:** Verify allocation ID exists, check list of allocations for employee

---

## Related Documentation

- **HRMS-0507:** Employee Allocation Records model definition
- **HRMS-0803:** Multi-Allocation Support specification
- **HRMS-0812:** Project Allocation Capacity Management
- **S-365:** Buddy Program implementation
- **04-RESOURCE-MANAGEMENT.md:** Phase 4 Resource Management architecture

---

## Support

For questions or issues:
1. Check test cases for usage examples
2. Review error messages and conflict_reasons
3. Consult WROS_Development_Review_Standard.md for business rules
4. Open issue with allocation details and error logs
