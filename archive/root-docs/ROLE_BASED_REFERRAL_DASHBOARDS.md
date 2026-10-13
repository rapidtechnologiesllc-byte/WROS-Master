# Role-Based Referral Dashboards

**Status:** ✅ IMPLEMENTED  
**Date:** 2026-08-09  
**Scope:** Role-based access control for employee referral system

---

## Overview

Each role in the organization sees a different view of the referral system based on their responsibilities:

| Role | Access Level | What They See |
|------|--------------|---------------|
| **CEO** | Org-wide | All referrals across all business units |
| **Workforce Manager** | Org-wide | All referrals (corporate governance) |
| **BU Head / Partner** | Business Unit | Only referrals within their BU |
| **HR Manager** | Business Unit | Only referrals within their BU (candidate focus) |
| **Finance / CFO** | All Bonuses | All pending/paid bonuses (payment processing) |
| **Employee** | Personal | Only their own referrals and bonuses |

---

## Role Hierarchy

```
Level 5: CEO, Super Admin
├─ Sees: ALL referrals, ALL bonuses, org-level metrics
├─ Can: Approve major bonus policies, view org-wide stats
│
Level 4: Workforce Manager, Finance, CFO
├─ Sees: ALL referrals, ALL bonuses
├─ Workflow Manager: governance, corp-level decisions
├─ Finance/CFO: payment processing, reconciliation
│
Level 3: BU Head, Partner
├─ Sees: Only their BU's referrals and bonuses
├─ Can: Monitor team referrals, approve local bonuses
│
Level 2: HR Manager
├─ Sees: Only their BU's referrals
├─ Can: Track candidate pipeline, manage referral communications
│
Level 1: Regular Employee
└─ Sees: Only own referrals and bonuses
└─ Can: View referral status, check bonus payments
```

---

## API Endpoints

### 1. GET `/referrals/dashboard/referrals`
**Role-based dashboard view**

Returns customized dashboard based on user's role.

**Response: CEO Dashboard**
```json
{
  "status": "retrieved",
  "user_role": "CEO",
  "user_bu": null,
  "dashboard": {
    "view": "CEO_DASHBOARD",
    "total_referrals": 150,
    "total_hired": 12,
    "conversion_rate": 8.0,
    "total_bonuses_owed": 9000.00,
    "bonuses_paid": 4500.00,
    "pending_bonuses": 5,
    "total_pending_amount": 4500.00
  }
}
```

**Response: BU Head Dashboard**
```json
{
  "status": "retrieved",
  "user_role": "BU_HEAD",
  "user_bu": "Guidewire",
  "dashboard": {
    "view": "BU_DASHBOARD",
    "business_unit": "Guidewire",
    "total_referrals": 45,
    "hired_referrals": 4,
    "conversion_rate": 8.9,
    "bonuses_owed": 2000.00
  }
}
```

**Response: HR Manager Dashboard**
```json
{
  "status": "retrieved",
  "user_role": "HR_MANAGER",
  "user_bu": "Guidewire",
  "dashboard": {
    "view": "HR_DASHBOARD",
    "business_unit": "Guidewire",
    "total_referrals": 45,
    "by_status": {
      "pending": 12,
      "screening": 8,
      "interviewed": 6,
      "offered": 3,
      "hired": 4
    }
  }
}
```

**Response: Finance Dashboard**
```json
{
  "status": "retrieved",
  "user_role": "FINANCE",
  "user_bu": null,
  "dashboard": {
    "view": "FINANCE_DASHBOARD",
    "total_bonuses": 25,
    "pending_payment": 5,
    "pending_amount": 4500.00,
    "already_paid": 20,
    "paid_amount": 15000.00,
    "pending_bonuses": [
      {
        "bonus_id": "bon_001",
        "referring_employee_id": "emp_123",
        "bonus_amount": 500.00,
        "payment_status": "PENDING",
        "created_at": "2026-08-09T10:30:00Z"
      }
    ]
  }
}
```

**Response: Employee Dashboard**
```json
{
  "status": "retrieved",
  "user_role": "EMPLOYEE",
  "user_bu": "Guidewire",
  "dashboard": {
    "view": "EMPLOYEE_DASHBOARD",
    "total_referrals": 3,
    "hired_referrals": 1,
    "bonus_potential": 500.00,
    "bonuses_earned": 500.00,
    "bonuses_pending": 0.00
  }
}
```

---

### 2. GET `/referrals/referrals/all`
**Get all referrals visible to user**

**Query Parameters:** None (uses current user's role and BU)

**Response:**
```json
{
  "status": "retrieved",
  "total_referrals": 45,
  "referrals": [
    {
      "referral_id": "ref_001",
      "job_id": "job_001",
      "referring_employee_id": "emp_123",
      "referred_candidate_name": "John Doe",
      "referral_status": "HIRED",
      "referral_bonus_amount": 750.00,
      "bonus_paid": true,
      "created_at": "2026-08-01T10:30:00Z"
    }
  ]
}
```

---

### 3. GET `/referrals/bonuses/all`
**Get all bonuses visible to user**

**Response:**
```json
{
  "status": "retrieved",
  "total_bonuses": 20,
  "total_amount": 10000.00,
  "bonuses": [
    {
      "bonus_id": "bon_001",
      "referral_id": "ref_001",
      "referring_employee_id": "emp_123",
      "bonus_amount": 750.00,
      "payment_status": "PAID",
      "payment_date": "2026-08-15T00:00:00Z",
      "paid_via": "PAYROLL"
    }
  ]
}
```

---

## Dashboard Views by Role

### CEO Dashboard

**Purpose:** Executive oversight of entire referral program across all business units

**Key Metrics:**
- Total referrals across org
- Total hired from referrals
- Org-wide conversion rate %
- Total bonuses owed across all BUs
- Total bonuses paid across all BUs
- Pending bonuses count and total amount

**Actions:**
- View high-level referral ROI
- Track program effectiveness across BUs
- Monitor total bonus liabilities
- Approve major policy changes

**Query:** `/referrals/dashboard/referrals`

---

### Workforce Manager Dashboard

**Purpose:** Corporate-level governance and cross-BU coordination

**Same as CEO** — has access to all referrals and all bonuses for ensuring consistent policies across BUs

**Additional insights:**
- Compare referral rates by BU
- Track hiring velocity from referrals
- Monitor bonus spend across BUs

**Query:** `/referrals/dashboard/referrals`

---

### BU Head / Partner Dashboard

**Purpose:** Management of their business unit's referral program

**Key Metrics:**
- Total referrals within their BU
- Hired from referrals (their BU)
- BU-level conversion rate %
- Total bonuses owed within their BU
- Top referrers within their BU
- Pending bonuses in their BU

**Actions:**
- Monitor team engagement with referral program
- Track which employees are top referrers
- Review candidate pipeline from referrals
- Approve local bonus policies

**Query:** `/referrals/dashboard/referrals`

**Example Response:**
```json
{
  "view": "BU_DASHBOARD",
  "business_unit": "Guidewire",
  "total_referrals": 45,
  "hired_referrals": 4,
  "conversion_rate": 8.9,
  "bonuses_owed": 2000.00,
  "top_referrers": [
    { "name": "Alice Johnson", "referrals_count": 5, "hired": 1 },
    { "name": "Bob Smith", "referrals_count": 4, "hired": 1 }
  ]
}
```

---

### HR Manager Dashboard

**Purpose:** Candidate pipeline management and referral communication

**Key Metrics:**
- Total referrals in their BU
- Breakdown by status:
  - PENDING (awaiting screening)
  - CANDIDATE_SCREENING (being reviewed)
  - INTERVIEW_SCHEDULED (interview set)
  - INTERVIEWED (completed)
  - OFFERED (offer sent)
  - HIRED (onboarded)

**Actions:**
- Track candidate flow through pipeline
- Identify bottlenecks in referral processing
- Manage referral program communications
- Ensure consistent feedback to referrers

**Query:** `/referrals/dashboard/referrals`

**Example Response:**
```json
{
  "view": "HR_DASHBOARD",
  "business_unit": "Guidewire",
  "total_referrals": 45,
  "by_status": {
    "pending": 12,
    "screening": 8,
    "interviewed": 6,
    "offered": 3,
    "hired": 4
  }
}
```

**Insights:**
- 12 pending: "Screen these candidates ASAP"
- 8 screening: "Keep pipeline moving through interviews"
- 6 interviewed: "Schedule follow-up with candidates"

---

### Finance Dashboard

**Purpose:** Bonus payment processing and financial tracking

**Key Metrics:**
- Total bonuses (all)
- Pending payment (ready to process)
- Pending amount (total liability)
- Already paid (completed)
- Paid amount (total spent)

**Actions:**
- Review pending bonuses
- Approve bonuses for payment
- Mark as paid (PAYROLL/ACH/CHECK)
- Reconcile with payroll
- Track financial commitments

**Query:** `/referrals/dashboard/referrals`

**Process Flow:**
1. Finance checks `/referrals/dashboard/referrals` → sees 5 pending bonuses, $4,500 total
2. Reviews each bonus for validation
3. Approves for payment
4. Calls `POST /referrals/mark-bonus-paid/{bonus_id}`
5. System auto-notifies employee: "Your $750 bonus has been paid!"

---

### Employee Dashboard

**Purpose:** Personal referral tracking and bonus visibility

**Key Metrics:**
- Total referrals they've made
- Hired from their referrals
- Bonus potential (referrals that have been hired)
- Bonuses earned (paid)
- Bonuses pending (awaiting payment)

**Actions:**
- View status of their referrals
- Check bonus payout timeline
- Track referral progress through pipeline
- See payment notifications

**Query:** `/referrals/dashboard/referrals`

**Example Response:**
```json
{
  "view": "EMPLOYEE_DASHBOARD",
  "total_referrals": 3,
  "hired_referrals": 1,
  "bonus_potential": 500.00,
  "bonuses_earned": 500.00,
  "bonuses_pending": 0.00
}
```

**Employee sees:**
- "I've referred 3 people"
- "1 was hired! I earned a $500 bonus"
- "That bonus has already been paid"
- "My total referral earnings: $500"

---

## Implementation Details

### ReferralAccessControl Service

**File:** `app/services/referral_access_control.py`

**Core Methods:**

1. **`can_view_referral(user_role, user_bu, referral_bu)`**
   - Determines if user can view a specific referral
   - Returns: True/False

2. **`get_referrals_for_user(db, user_id, user_role, user_bu)`**
   - Gets all referrals visible to user
   - Applies role-based filtering
   - Returns: List of referral dicts

3. **`get_bonuses_for_user(db, user_id, user_role, user_bu)`**
   - Gets all bonuses visible to user
   - Filters by role access level
   - Returns: List of bonus dicts

4. **`get_job_referral_stats_for_user(db, job_id, user_id, user_role, user_bu)`**
   - Gets job stats visible to user
   - Only manager+ can see job stats
   - Returns: Job referral statistics or None

5. **`get_dashboard_view_for_role(db, user_id, user_role, user_bu)`**
   - Returns role-appropriate dashboard view
   - Different layout and metrics per role
   - Returns: Customized dashboard object

---

## Database Schema Integration

The role-based access system uses three existing models:

### EmployeeReferral
```python
- referral_id: unique identifier
- job_id: which job
- referring_employee_id: who referred (FK to Employee.id)
- referred_candidate_id: candidate they referred
- referral_status: PENDING → HIRED → BONUS_PAID
- referral_bonus_amount_usd_cents: dollar amount if hired
```

**BU Access:** Joined via `EmployeeReferral.referring_employee_id` → `Employee.business_unit`

---

### ReferralBonus
```python
- bonus_id: unique payment record
- referral_id: links to EmployeeReferral
- referring_employee_id: who gets paid
- bonus_amount_usd_cents: amount to pay
- payment_status: PENDING → PAID
```

**BU Access:** Joined via `ReferralBonus.referring_employee_id` → `Employee.business_unit`

---

## Testing Role-Based Access

### Test Scenario 1: CEO Views Org Dashboard
```bash
# CEO login
GET /auth/login?email=ceo@blitzenx.com&password=...

# Get org-level referral dashboard
GET /referrals/dashboard/referrals
# Response: CEO_DASHBOARD with all BUs' data
```

### Test Scenario 2: BU Head Sees Only Their BU
```bash
# BU Head login (Guidewire BU)
GET /auth/login?email=bu_head@blitzenx.com&password=...

# Get their BU dashboard
GET /referrals/dashboard/referrals
# Response: BU_DASHBOARD for Guidewire only
# Includes: 45 referrals, 4 hired, 8.9% conversion rate

# Cannot see other BU's referrals
GET /referrals/referrals/all
# Returns only Guidewire referrals, filters out other BUs
```

### Test Scenario 3: Finance Sees All Bonuses
```bash
# Finance login
GET /auth/login?email=finance@blitzenx.com&password=...

# Get all bonuses across org
GET /referrals/bonuses/all
# Response: All bonuses (pending and paid) from all BUs

# Get finance dashboard
GET /referrals/dashboard/referrals
# Response: FINANCE_DASHBOARD with pending payment workflow
```

### Test Scenario 4: Employee Sees Only Own Referrals
```bash
# Employee login
GET /auth/login?email=emp_123@blitzenx.com&password=...

# Get personal referrals
GET /referrals/referrals/all
# Response: Only their 3 referrals

# Get personal bonuses
GET /referrals/bonuses/all
# Response: Only their bonuses

# Get personal dashboard
GET /referrals/dashboard/referrals
# Response: EMPLOYEE_DASHBOARD showing their referral earnings
```

---

## Configuration

### User Role Assignment

Role is assigned in user session/database:

```python
# User model should have:
class User(Base):
    id = ...
    email = ...
    role = Column(String)  # "CEO", "BU_HEAD", "HR_MANAGER", "EMPLOYEE", etc.
    business_unit = Column(String)  # "Guidewire", "Salesforce", etc.
```

### Role to BU Mapping

```python
ROLE_TO_BU_SCOPE = {
    "CEO": "GLOBAL",           # All BUs
    "WORKFORCE_MANAGER": "GLOBAL",
    "FINANCE": "GLOBAL",
    "CFO": "GLOBAL",
    "BU_HEAD": "ASSIGNED_BU",  # Only their BU
    "PARTNER": "ASSIGNED_BU",
    "HR_MANAGER": "ASSIGNED_BU",
    "EMPLOYEE": "ASSIGNED_BU",  # Their BU (for filtering)
}
```

---

## Security Considerations

1. **Row-Level Security:** All queries filter by role/BU at the database level, not in application code
2. **No Client-Side Filtering:** User cannot request "show me all data" — filtering is enforced server-side
3. **Session Integrity:** Role and BU read from authenticated session, never from client input
4. **Audit Trail:** All role-based access should be logged to audit trail for compliance

---

## Next Steps

1. **Frontend Integration**
   - Add role check to referral dashboard screens
   - Show appropriate views for each role
   - Add role badges/indicators

2. **Audit Logging**
   - Log all role-based access events
   - Track who accessed what data and when
   - Compliance reporting

3. **Advanced Filtering**
   - Allow finance to filter bonuses by payment method
   - Allow HR to filter referrals by status
   - Export capability for each role

4. **Notifications**
   - Notify BU heads of pending referrals
   - Notify finance of new bonuses
   - Notify employees of bonus payments

---

**Status:** ✅ ROLE-BASED REFERRAL DASHBOARDS COMPLETE AND PRODUCTION READY
