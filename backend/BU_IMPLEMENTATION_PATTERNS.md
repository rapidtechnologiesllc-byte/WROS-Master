# Business Unit Implementation - Code Patterns & Templates (2026-08-12)

## Quick Reference: Apply These Patterns to ALL Screens

---

## Pattern 1: Auto-Scoped List Screen (No BU Dropdown)

**Use for:** Regular users (non-Finance roles)
**Effect:** User sees only THEIR BU data - filter is invisible

```javascript
// Example: CandidateList.jsx
import { getCurrentUserBU } from "../utils/userContext";

export default function CandidatesList() {
  const currentUser = getCurrentUserBU();
  
  // Auto-filter: if user has a BU, use it
  const [filters, setFilters] = useState({
    business_unit_id: currentUser?.business_unit_id || null,
    status: "active"
  });

  useEffect(() => {
    // Only fetch data for user's BU - no dropdown shown
    fetchCandidates({
      business_unit_id: filters.business_unit_id
    });
  }, [filters.business_unit_id]);

  return (
    <div>
      {/* NO BU dropdown shown - just status filter */}
      <FilterBar>
        <Select 
          placeholder="Status"
          onChange={(status) => setFilters({ ...filters, status })}
        />
        {/* Status and other filters only */}
      </FilterBar>

      <Table columns={[
        { key: "name", title: "Name" },
        { key: "email", title: "Email" },
        { key: "business_unit_name", title: "Business Unit" }, // ← Show BU info but don't filter
        { key: "status", title: "Status" }
      ]} />
    </div>
  );
}
```

---

## Pattern 2: Cross-BU Toggle (Finance Only)

**Use for:** Finance/Executive users
**Effect:** One toggle switches between "My BU" and "All BUs"

```javascript
// Example: InvoicesScreen.jsx
import { hasRole } from "../utils/permissionsRbac";
import { getCurrentUserBU } from "../utils/userContext";

export default function InvoicesScreen() {
  const currentUser = getCurrentUserBU();
  const isFinance = hasRole("FINANCE") || hasRole("EXECUTIVE");
  
  const [viewAllBUs, setViewAllBUs] = useState(false);
  
  const filters = {
    business_unit_id: (viewAllBUs || !isFinance) 
      ? null  // null = all BUs
      : currentUser?.business_unit_id,
    status: "pending"
  };

  return (
    <div>
      <FilterBar>
        {isFinance && (
          <Checkbox
            label="View All BUs"
            checked={viewAllBUs}
            onChange={() => setViewAllBUs(!viewAllBUs)}
          />
        )}
        <Select placeholder="Status" />
      </FilterBar>

      <Table columns={[
        { key: "invoice_id", title: "Invoice #" },
        { key: "amount", title: "Amount" },
        { key: "business_unit_name", title: "Business Unit" },
        { key: "client_name", title: "Client" },
        { key: "status", title: "Status" }
      ]} 
      dataSource={invoices.groupBy('business_unit_name')} />
    </div>
  );
}
```

---

## Pattern 3: Auto-Populated BU Field (Create Form)

**Use for:** Job creation, user creation, client creation
**Effect:** BU pre-filled from user's context - read-only unless multi-BU role

```javascript
// Example: JobCreateForm.jsx
import { getCurrentUserBU } from "../utils/userContext";

export default function JobCreateForm() {
  const currentUser = getCurrentUserBU();
  const canChangeBU = currentUser?.business_unit_id?.length > 1; // Multi-BU user?
  
  const [formData, setFormData] = useState({
    title: "",
    description: "",
    business_unit_id: currentUser?.business_unit_id?.[0] || null, // Auto-fill
    department_id: null
  });

  return (
    <Form>
      <Input 
        label="Job Title" 
        value={formData.title}
        onChange={(e) => setFormData({ ...formData, title: e.target.value })}
      />
      
      <Select
        label="Business Unit"
        value={formData.business_unit_id}
        onChange={(value) => setFormData({ ...formData, business_unit_id: value })}
        disabled={!canChangeBU} // Read-only for single-BU users
        helpText={!canChangeBU ? `All candidates submitted to this job will be in ${currentUser.business_unit_name}` : ""}
      />
      
      <Select
        label="Department"
        // Filter by selected BU
        options={departments.filter(d => d.business_unit_id === formData.business_unit_id)}
        onChange={(value) => setFormData({ ...formData, department_id: value })}
      />
      
      <Button onClick={submit}>Create Job</Button>
    </Form>
  );
}
```

---

## Pattern 4: Auto-Inherited BU (Dependent Field)

**Use for:** Candidate details, employee details, allocations
**Effect:** BU shown but not editable - inherited from parent entity

```javascript
// Example: OfferLetterForm.jsx
import { getCandidateDetails } from "../services/candidates";

export default function OfferLetterForm({ candidateId }) {
  const candidate = getCandidateDetails(candidateId);
  
  // BU is auto-inherited from candidate
  const [formData, setFormData] = useState({
    position: "",
    salary: "",
    start_date: null,
    business_unit_id: candidate?.business_unit_id, // AUTO - cannot change
  });

  return (
    <Form>
      <Alert>
        Creating offer for <strong>{candidate.name}</strong> (BU: <strong>{candidate.business_unit_name}</strong>)
      </Alert>
      
      <Input 
        label="Position"
        value={formData.position}
        onChange={(e) => setFormData({ ...formData, position: e.target.value })}
      />
      
      <Input 
        label="Salary"
        value={formData.salary}
        onChange={(e) => setFormData({ ...formData, salary: e.target.value })}
      />
      
      <Display 
        label="Business Unit"
        value={candidate.business_unit_name}
        helpText="Inherited from candidate's BU"
      />
      
      <Button onClick={submit}>Create Offer</Button>
    </Form>
  );
}
```

---

## Pattern 5: Validation - Prevent Cross-BU Operations

**Backend Validators (FastAPI):**

```python
# app/services/allocation_service.py

def validate_allocation_same_bu(employee_id: str, job_id: str, db: Session):
    """Prevent allocating employee to job outside their BU"""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    
    if not employee or not job:
        return
    
    if employee.bu_id != job.business_unit_id:
        raise ValidationError(
            f"Cannot allocate {employee.first_name} {employee.last_name} "
            f"(BU: {employee.bu_id}) to {job.jobTitle} (BU: {job.business_unit_id})"
        )

# Usage in endpoint:
@router.post("/allocations")
def create_allocation(
    body: AllocationCreate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin)
):
    validate_allocation_same_bu(body.employee_id, body.job_id, db)
    # Proceed with creation
```

**Frontend Validation (React):**

```javascript
// utils/buValidation.js

export function validateAllocationSameBU(employee, job) {
  if (!employee?.bu_id || !job?.business_unit_id) {
    return true; // No validation needed if missing data
  }
  
  if (employee.bu_id !== job.business_unit_id) {
    return {
      valid: false,
      error: `Cannot allocate ${employee.name} (BU: ${employee.bu_name}) to ${job.title} (BU: ${job.bu_name})`,
      action: "Choose a different employee or job"
    };
  }
  
  return true;
}

// Usage in component:
const result = validateAllocationSameBU(selectedEmployee, selectedJob);
if (result !== true) {
  showError(result.error);
  return; // Prevent submit
}
```

---

## Pattern 6: Automatic Cascade (Employee → Timesheet → Invoice)

**Backend Service (Python):**

```python
# app/services/timesheet_service.py

def create_weekly_draft(employee_id: str, week_start_date: date, db: Session):
    """Create timesheet with automatic BU inheritance"""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    
    timesheet = Timesheet(
        employee_id=employee_id,
        business_unit_id=employee.bu_id,  # AUTO - inherit from employee
        week_starting_date=week_start_date,
        status="DRAFT"
    )
    
    db.add(timesheet)
    db.commit()
    return timesheet

def generate_invoice(timesheet_id: str, db: Session):
    """Create invoice with automatic BU inheritance"""
    timesheet = db.query(Timesheet).filter(Timesheet.id == timesheet_id).first()
    
    invoice = Invoice(
        timesheet_id=timesheet_id,
        business_unit_id=timesheet.business_unit_id,  # AUTO - inherit from timesheet
        total_usd_cents=calculate_total(timesheet),
        status="DRAFT"
    )
    
    db.add(invoice)
    db.commit()
    return invoice
```

---

## Pattern 7: Employment History on BU Change

**Backend Service:**

```python
# app/services/employee_service.py

def update_employee_bu(employee_id: str, new_bu_id: int, db: Session):
    """Update employee BU and create history record"""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    old_bu_id = employee.bu_id
    
    # Validate allocation compatibility
    allocations = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.employee_id == employee_id,
        EmployeeAllocation.status == "active"
    ).all()
    
    for alloc in allocations:
        job = db.query(Jobs).filter(Jobs.jobID == alloc.job_id).first()
        if job.business_unit_id != new_bu_id:
            raise ValidationError(
                f"Employee has active allocation in different BU. "
                f"Cannot transfer. Please complete allocation first."
            )
    
    # Update employee
    employee.bu_id = new_bu_id
    
    # Create history record
    history = EmployeeEmploymentHistory(
        employee_id=employee_id,
        change_type="BU",
        old_value=str(old_bu_id),
        new_value=str(new_bu_id),
        effective_date=date.today(),
        changed_by=current_user.UserID,
        reason="Employee transfer"
    )
    
    db.add(history)
    db.commit()
```

---

## Pattern 8: Automatic Candidate BU Assignment

**Backend Endpoint (Already Done ✅):**

```python
# app/api/v1/endpoints/submissions.py

@router.post("/submissions")
def submit_candidate(body: CreateSubmissionRequest, db: Session, current_user: Users):
    submission = create_submission(...)
    
    # AUTO-ASSIGN BU FROM JOB
    job = db.query(Jobs).filter(Jobs.jobID == body.demand_id).first()
    if job and job.business_unit_id and not candidate.business_unit_id:
        candidate.business_unit_id = job.business_unit_id
        db.commit()
    
    return submission
```

---

## Pattern 9: Display BU Info (All Detail Screens)

**React Component:**

```javascript
// components/BUInfoBanner.jsx

export default function BUInfoBanner({ entity, entityType }) {
  if (!entity?.business_unit_id) {
    return <Alert type="warning">Business Unit: Not Assigned</Alert>;
  }

  const statusText = {
    "candidate": "Submitted to this BU",
    "employee": "Assigned to this BU",
    "job": "All submissions will be in this BU",
    "invoice": "Billing for this BU"
  };

  return (
    <div style={styles.banner}>
      <Badge color="blue">
        {entity.business_unit_name}
      </Badge>
      <Text size="sm" color="gray">
        {statusText[entityType] || ""}
      </Text>
    </div>
  );
}

// Usage in detail screens:
<BUInfoBanner entity={candidate} entityType="candidate" />
<BUInfoBanner entity={employee} entityType="employee" />
<BUInfoBanner entity={job} entityType="job" />
```

---

## Pattern 10: Reporting with Auto-Grouping

**React Component:**

```javascript
// screens/RevenueReport.jsx

export default function RevenueReport() {
  const [invoices, setInvoices] = useState([]);
  
  // Auto-group by BU
  const groupedByBU = invoices.reduce((acc, inv) => {
    const buKey = inv.business_unit_id;
    if (!acc[buKey]) {
      acc[buKey] = { name: inv.business_unit_name, invoices: [], total: 0 };
    }
    acc[buKey].invoices.push(inv);
    acc[buKey].total += inv.total_usd_cents / 100;
    return acc;
  }, {});

  return (
    <div>
      <h2>Revenue by Business Unit</h2>
      {Object.entries(groupedByBU).map(([buId, group]) => (
        <Card key={buId}>
          <h3>{group.name}</h3>
          <div style={{ fontSize: "24px", fontWeight: "bold" }}>
            ${group.total.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: "12px", color: "gray" }}>
            {group.invoices.length} invoices
          </div>
          <CollapsibleTable data={group.invoices} />
        </Card>
      ))}
    </div>
  );
}
```

---

## Checklist: Apply to Each Screen

For **every list screen** in Phase 1-5, apply these in order:

- [ ] **Step 1:** Remove BU dropdown if user doesn't have multi-BU role
- [ ] **Step 2:** Auto-filter query: `where business_unit_id = current_user.business_unit_id`
- [ ] **Step 3:** Add BU column to table showing `business_unit_name`
- [ ] **Step 4:** Add Finance toggle: "View All BUs" (if Finance role)
- [ ] **Step 5:** Auto-group/sort by BU in table/Kanban

For **every detail/create screen**:

- [ ] **Step 1:** Display BU banner (BUInfoBanner component)
- [ ] **Step 2:** Pre-fill BU from user context (if create form)
- [ ] **Step 3:** Make BU read-only if inherited from parent
- [ ] **Step 4:** Add validation: prevent cross-BU operations
- [ ] **Step 5:** Add cascade: auto-set child entity's BU

---

## Copy-Paste Snippets

### Import statements (add to every component):
```javascript
import { getCurrentUserBU, hasMultiBU } from "../utils/userContext";
import { hasRole } from "../utils/permissionsRbac";
import BUInfoBanner from "../components/BUInfoBanner";
```

### Auto-filter logic:
```javascript
const currentUser = getCurrentUserBU();
const filters = {
  business_unit_id: currentUser?.business_unit_id || null
};
```

### Finance toggle:
```javascript
const isFinance = hasRole("FINANCE") || hasRole("EXECUTIVE");
const [viewAllBUs, setViewAllBUs] = useState(false);
const buFilter = (viewAllBUs && isFinance) ? null : currentUser?.business_unit_id;
```

### Table columns:
```javascript
{
  dataIndex: ["business_unit", "name"],
  title: "Business Unit",
  render: (text, record) => record.business_unit_name || "Unassigned"
}
```

---

## Implementation Efficiency Tips

1. **Create once, copy often:** Write BU logic once in util files, import everywhere
2. **Use hooks:** Create `useBUContext()` hook for auto-filtering logic
3. **Reuse components:** One `BUInfoBanner` component for all detail screens
4. **Batch updates:** Apply to one screen, then copy pattern to similar screens
5. **Test coverage:** One test suite for BU logic, apply to all screens

---

This is the **production-ready implementation strategy**. Apply these patterns systematically across all 35 screens over 2-3 weeks.

