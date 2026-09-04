# Expense Management - Quick Reference Guide

## Story: S-325 Expense Management

**Implemented Methods:**
- `submit_expense` - Employee logs expense
- `approve_expense` (manager) - Manager approves
- `approve_expense` (finance) - Finance approves
- `reimburse_expense` - Mark as paid
- `track_reimbursement` - Monitor status

---

## API Quick Start

### 1. Employee Submits Expense

```bash
POST /expenses
Authorization: Bearer <EMPLOYEE_JWT>
Content-Type: application/json

{
  "purpose": "CONFERENCE",
  "conference_name": "NAMIC 2026",
  "expense_category": "TRAVEL",
  "travel_type": "AIRFARE",
  "amount_usd_cents": 45000,
  "expense_date": "2026-08-01",
  "receipt_ref": "REC-NAMIC-001",
  "location": "Orlando, FL",
  "description": "Airfare to NAMIC conference"
}

Response 201:
{
  "id": "exp-abc123",
  "logged_by_user_id": "curtis",
  "manager_approval_status": "PENDING",
  "payment_status": "PENDING",
  "amount_usd_cents": 45000
}
```

### 2. Manager Approves Expense

```bash
POST /expenses/exp-abc123/approve/manager
Authorization: Bearer <MANAGER_JWT>
Content-Type: application/json
Requires: employee.manage permission

{}

Response 200:
{
  "id": "exp-abc123",
  "manager_approval_status": "APPROVED",
  "manager_approved_by": "manager1",
  "manager_approved_at": "2026-08-02T09:00:00Z",
  "payment_status": "PENDING"
}
```

### 3. Finance Approves Expense

```bash
POST /expenses/exp-abc123/approve/finance
Authorization: Bearer <FINANCE_JWT>
Content-Type: application/json
Requires: revenue.view_pnl permission

{}

Response 200:
{
  "id": "exp-abc123",
  "manager_approval_status": "APPROVED",
  "payment_status": "APPROVED",
  "approved_by": "finance1"
}

Side effects:
- Email sent to accounts@blitzenx.com
- Task created: "Mark expense as paid: TRAVEL $450"
```

### 4. Finance Marks as Reimbursed

```bash
POST /expenses/exp-abc123/reimburse
Authorization: Bearer <FINANCE_JWT>
Content-Type: application/json
Requires: revenue.view_pnl permission

{}

Response 200:
{
  "id": "exp-abc123",
  "payment_status": "REIMBURSED"
}

Side effects:
- Associated task marked COMPLETED
```

### 5. Track Reimbursement Status

**Personal Tracking:**
```bash
GET /expenses/track-reimbursement
Authorization: Bearer <EMPLOYEE_JWT>

Response 200:
{
  "total_count": 5,
  "pending_count": 1,
  "approved_count": 2,
  "reimbursed_count": 2,
  "total_amount_usd_cents": 225000,
  "pending_amount_usd_cents": 45000,
  "reimbursements": [
    {
      "id": "exp-abc123",
      "amount_usd_cents": 45000,
      "expense_date": "2026-08-01",
      "manager_approval_status": "APPROVED",
      "payment_status": "REIMBURSED",
      "days_pending": 2,
      "days_awaiting_manager": 1,
      "days_awaiting_finance": 1,
      "is_fully_processed": true
    }
  ]
}
```

**All Reimbursements (Manager/Finance Only):**
```bash
GET /expenses/track-reimbursement/all
Authorization: Bearer <FINANCE_JWT>
Requires: revenue.view permission

Response 200:
{
  "total_count": 47,
  "pending_count": 12,
  "approved_count": 18,
  "reimbursed_count": 17,
  "total_amount_usd_cents": 1250000,
  "pending_amount_usd_cents": 425000,
  "reimbursements": [...]
}
```

### 6. View All Expenses (With Filters)

```bash
GET /expenses
Authorization: Bearer <FINANCE_JWT>
Requires: revenue.view permission

Optional query parameters:
- client_id: Filter by client (UUID)
- purpose: Filter by purpose (CLIENT_CURRENT, CLIENT_PROSPECT, CONFERENCE, INVESTMENT, OTHER)
- status: Filter by status (PENDING, APPROVED, REIMBURSED)

Examples:
GET /expenses?status=PENDING
GET /expenses?status=APPROVED&purpose=CONFERENCE
GET /expenses?client_id=client-123

Response 200:
{
  "expenses": [
    {
      "id": "exp-abc123",
      "logged_by_user_id": "curtis",
      "purpose": "CONFERENCE",
      "expense_category": "TRAVEL",
      "amount_usd_cents": 45000,
      "manager_approval_status": "APPROVED",
      "payment_status": "PENDING"
    }
  ]
}
```

### 7. View Own Expenses

```bash
GET /expenses/mine
Authorization: Bearer <EMPLOYEE_JWT>

Response 200:
{
  "expenses": [
    {
      "id": "exp-abc123",
      "purpose": "CONFERENCE",
      "amount_usd_cents": 45000,
      "expense_date": "2026-08-01",
      "manager_approval_status": "APPROVED",
      "payment_status": "REIMBURSED"
    }
  ]
}
```

### 8. Client Investment Position

```bash
GET /clients/client-123/investment-position
Authorization: Bearer <FINANCE_JWT>
Requires: revenue.view permission

Response 200:
{
  "client_id": "client-123",
  "company_name": "Acme Corp",
  "status": "ACTIVE",
  "prospect_since": "2026-01-15T00:00:00Z",
  "converted_on": "2026-03-20T00:00:00Z",
  "total_expense_usd_cents": 150000,
  "total_revenue_usd_cents": 250000,
  "net_position_usd_cents": 100000,
  "breakeven_date": "2026-04-15",
  "expense_count": 5
}
```

---

## Expense Submission Rules

### Purpose & Requirements

| Purpose | Requires | Example |
|---------|----------|---------|
| CLIENT_CURRENT | client_id | Lunch with active client contact |
| CLIENT_PROSPECT | client_id | Travel to prospect pitch meeting |
| CONFERENCE | conference_name | NAMIC 2026, IEEE 2026 |
| INVESTMENT | investment_label | Office equipment, software licenses |
| OTHER | (none) | General business expense |

### Categories

- TRAVEL - Airfare, hotel, ground transport
- MEALS - Restaurants, client entertainment
- LODGING - Hotel, accommodation
- ENTERTAINMENT - Events, team activities
- OTHER - Miscellaneous

### Travel Types (For TRAVEL category)

- AIRFARE - Flights
- GROUND_TRANSPORT - Taxis, rideshare, car rental
- HOTEL - Lodging
- MEALS - Restaurant meals on trip
- OTHER - Misc travel

---

## Workflow States

### Manager Approval Path

```
PENDING → APPROVED → REJECTED (optional)
```

### Payment Status Path

```
PENDING → APPROVED → REIMBURSED
```

### Complete Workflow

```
Employee submits
  ↓
manager_approval_status = PENDING
payment_status = PENDING
Task created for manager
  ↓
Manager approves
  ↓
manager_approval_status = APPROVED
  ↓
Finance approves
  ↓
payment_status = APPROVED
Email sent to accounts@blitzenx.com
Task created for finance
  ↓
Finance processes payment, marks as paid
  ↓
payment_status = REIMBURSED
Task marked COMPLETED
```

---

## Error Responses

### 400 Bad Request

```json
{
  "detail": "receipt_ref is mandatory for all expenses."
}
```

Valid receipt_ref is required.

```json
{
  "detail": "purpose=CLIENT_PROSPECT requires client_id."
}
```

CLIENT_CURRENT/CLIENT_PROSPECT purposes require client_id.

```json
{
  "detail": "Cannot approve expense for Finance until manager approves (current status: PENDING)"
}
```

Manager must approve before finance can approve.

```json
{
  "detail": "Expense must be APPROVED before it can be marked paid (currently PENDING)."
}
```

Finance approval required before marking as reimbursed.

### 404 Not Found

```json
{
  "detail": "Expense 'exp-xyz' not found."
}
```

Invalid expense ID.

### 403 Forbidden

```json
{
  "detail": "Not authenticated"
}
```

Missing or invalid JWT token.

```json
{
  "detail": "Insufficient permissions"
}
```

Missing required permission (revenue.view_pnl, employee.manage, etc).

---

## Permission Requirements

| Endpoint | Permission | Role |
|----------|-----------|------|
| POST /expenses | Authenticated | Employee |
| GET /expenses/mine | Authenticated | Employee |
| GET /expenses/track-reimbursement | Authenticated | Employee |
| POST /approve/manager | employee.manage | Manager |
| POST /approve/finance | revenue.view_pnl | Finance |
| POST /reimburse | revenue.view_pnl | Finance |
| GET /expenses | revenue.view | Manager/Finance/CEO |
| GET /track-reimbursement/all | revenue.view | Manager/Finance/CEO |
| GET /investment-position | revenue.view | Finance |

---

## Common Workflows

### For Employees

1. **Submit expense:** POST /expenses
2. **Check status:** GET /expenses/track-reimbursement
3. **View all my expenses:** GET /expenses/mine

### For Managers

1. **View pending approvals:** GET /expenses?status=PENDING
2. **Approve expense:** POST /expenses/{id}/approve/manager
3. **Track team reimbursements:** GET /expenses/track-reimbursement/all

### For Finance

1. **View manager-approved:** GET /expenses?status=APPROVED
2. **Approve for payment:** POST /expenses/{id}/approve/finance
3. **Process payment & close:** POST /expenses/{id}/reimburse
4. **View client investment position:** GET /clients/{id}/investment-position

---

## Database Details

**Table:** expense_records

**Key Fields:**
- `id` (VARCHAR 36) - UUID primary key
- `logged_by_user_id` (VARCHAR 50) - Who submitted
- `bu_context_id` (INT) - Business unit (derived)
- `amount_usd_cents` (BIGINT) - Amount in cents
- `receipt_ref` (VARCHAR 300) - Receipt proof
- `manager_approval_status` (ENUM) - PENDING, APPROVED, REJECTED
- `payment_status` (ENUM) - PENDING, APPROVED, REIMBURSED

**Relationships:**
- `users` via logged_by_user_id
- `clients` via client_id (optional)
- `tasks` (created for approvals)

---

## Development Notes

### Service Methods

All service methods in `app.services.expense_service`:

```python
# Submit/log expense
expense = log_expense(
    db, logged_by_user=current_user,
    purpose="CONFERENCE", conference_name="NAMIC 2026",
    expense_category="TRAVEL", amount_usd_cents=45000,
    expense_date=date(2026, 8, 1), receipt_ref="REC-001"
)

# Manager approval
expense = approve_manager_step(db, expense, approved_by=manager_id)

# Finance approval
expense = approve_expense(db, expense, approved_by=finance_id)

# Mark as paid
expense = mark_expense_paid(db, expense)

# Track reimbursement
tracking = track_reimbursement(db, user_id="curtis")
```

### Schema Classes

All in `app.schemas.expense`:

- `ExpenseCreateRequest` - POST /expenses body
- `ExpenseItem` - Single expense response
- `ExpenseListResponse` - GET /expenses response
- `ExpenseReimbursementStatus` - Single reimbursement status
- `ExpenseReimbursementTrackingResponse` - GET /track-reimbursement response
- `ClientInvestmentPositionResponse` - GET /investment-position response

### Validations (Service Layer)

- Receipt is mandatory (NOT NULL constraint)
- Amount must be positive
- CLIENT_CURRENT/CLIENT_PROSPECT require client_id
- CONFERENCE requires conference_name
- INVESTMENT requires investment_label
- Manager approval required before finance approval
- Finance approval required before marking as reimbursed

---

## Testing Examples

```bash
# Create test expense
curl -X POST http://localhost:8080/expenses \
  -H "Authorization: Bearer $EMPLOYEE_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "purpose": "CONFERENCE",
    "conference_name": "NAMIC 2026",
    "expense_category": "TRAVEL",
    "amount_usd_cents": 45000,
    "expense_date": "2026-08-01",
    "receipt_ref": "REC-001"
  }'

# Manager approves
curl -X POST http://localhost:8080/expenses/exp-abc123/approve/manager \
  -H "Authorization: Bearer $MANAGER_JWT"

# Finance approves
curl -X POST http://localhost:8080/expenses/exp-abc123/approve/finance \
  -H "Authorization: Bearer $FINANCE_JWT"

# Mark as paid
curl -X POST http://localhost:8080/expenses/exp-abc123/reimburse \
  -H "Authorization: Bearer $FINANCE_JWT"

# Track status
curl -X GET http://localhost:8080/expenses/track-reimbursement \
  -H "Authorization: Bearer $EMPLOYEE_JWT"
```

---

## FAQ

**Q: Can an employee submit on behalf of another employee?**  
A: No. The system always attributes the expense to the authenticated user. Impersonation is impossible (token-based).

**Q: Can a manager change the amount?**  
A: No. Manager can only approve/reject as-is. Finance could partially reimburse (future feature).

**Q: What happens if a manager never approves?**  
A: Expense stays PENDING indefinitely. No auto-escalation. Admin can intervene if needed.

**Q: Can expenses be deleted?**  
A: No. Audit trail maintained. Receipt is mandatory and immutable.

**Q: How are receipts stored?**  
A: receipt_ref is a text field (URL/path to receipt). Actual file storage is separate (S3/local storage).

**Q: What's the difference between manager and finance approval?**  
A: Manager validates business purpose. Finance validates policy compliance and amount reasonableness.

---

**Status:** Production Ready | **Updated:** 2026-08-15 | **Version:** 1.0
