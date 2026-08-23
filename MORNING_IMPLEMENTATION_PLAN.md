# Morning Implementation Plan - Multi-BU & Role-Based Integration

**Key Corrections Based on Your Input:**

---

## CRITICAL FIX: Multi-BU/Location Mapping

### The Problem
Your note: "one partner can have multiple BU, Multiple location and so on"

Current assumption: Partner → Single BU ❌  
Reality: Partner → Multiple BUs → Multiple Locations ✅

### What This Means

**Database Structure:**
```
User (Partner)
  ├─ BU Assignment 1 (via user_roles + business_unit_id)
  ├─ BU Assignment 2
  └─ BU Assignment 3

Each BU:
  ├─ Location 1
  ├─ Location 2
  └─ Location 3

Reporting Hierarchy (Corrected):
Partner (reports on ALL BUs they manage)
  ├─ BU 1 Head (location-scoped)
  │   └─ Tech Leads, Managers, Architects (location-scoped)
  ├─ BU 2 Head (location-scoped)
  │   └─ Teams
  └─ BU 3 Head (location-scoped)
```

### Impact on Pyramid Reporting

**Thursday 3PM Notifications:**

```
TO: All Partners
FROM: Finance Agent
SUBJECT: Weekly Report Deadlines

BU 1: Report due Friday 6PM
  └─ Tech Leads due Friday 3PM
  └─ Managers due Friday 4PM
  └─ Architects due Friday 5PM
  └─ BU Head due Friday 6PM

BU 2: Report due Friday 6PM
  └─ (same cascade)

BU 3: Report due Friday 6PM
  └─ (same cascade)

Your Consolidated Report (All BUs) due Friday 7PM
```

---

## Database Schema (From Models)

### Key Tables Needed

#### 1. users table
- UserID (Primary Key)
- UserName
- UserEmail
- UserRole (legacy - keep for backward compat)
- tenant_id
- **business_unit_id** (Primary BU)

#### 2. user_roles table (Junction - Multi-role/Multi-BU)
- id (PK)
- user_id → users.UserID
- role_id → role_templates.id
- **business_unit_id** → business_units.id
- Created when employee gets role assignment

#### 3. business_units table
- id (PK)
- name
- tenant_id
- manager_id → users.UserID (BU Head)
- **location_id** → locations.id

#### 4. locations table
- id (PK)
- name (city, office, region)
- business_unit_id
- tenant_id

#### 5. opportunities table
- id (PK)
- client_id
- owner_employee_id (sales person)
- revenue_value_usd_cents
- stage (QUALIFICATION, PROSPECT, PROPOSAL, NEGOTIATION, CONTRACT, ACTIVE, LOST)
- expected_close_date
- tenant_id
- created_at, updated_at

#### 6. employees table
- id (PK)
- UserID → users.UserID
- business_unit_id
- monthly_salary_usd
- role (DELIVERY, CONTRACTOR, SALES, MANAGER, ARCHITECT, HR, ADMIN)
- manager_id → employees.id
- current_project_id
- status (ACTIVE, INACTIVE, ON_LEAVE)
- tenant_id
- created_at

#### 7. invoices table
- id (PK)
- invoice_amount_usd
- partner_id → users.UserID
- vendor_type (CONTRACTOR, CLIENT, SERVICE)
- invoice_date
- status (PAID, PENDING, OVERDUE)
- tenant_id

---

## Role-Based Dashboard Access (Via Role Templates)

### Important: Dashboard Access via Role Templates

Current issue: Dashboards built but not connected to role_templates

**Each dashboard should be:**
1. Defined as a **Module** in role_templates
2. Assigned **Resource** permissions
3. Activated when user is added with that role

### Dashboard Modules to Create

#### 1. Pipeline Dashboard (Module: "pipeline_orchestration")
- **For Roles:** Manager, Architect, BU Head, CEO
- **Permissions:** "pipeline.view", "pipeline.status"
- **Data Filtered By:** BU (users' BU only, except CEO sees all)
- **Real-Time:** Queue depths, bottlenecks, recommendations

#### 2. Finance Dashboard (Module: "finance_monitoring")
- **For Roles:** Partner, BU Head, CEO, Finance
- **Permissions:** "finance.view", "finance.pl"
- **Data Filtered By:** BU/Location (partner sees only their BUs)
- **Real-Time:** Net profit %, margin tracking, P&L comparison
- **Note:** Partner sees ALL their BU P&Ls consolidated
- **Note:** BU Head sees only their BU
- **Note:** CEO sees all

#### 3. Pyramid Reporting Dashboard (Module: "agent_pyramid")
- **For Roles:** Manager+, CEO
- **Permissions:** "agents.view"
- **Data Filtered By:** BU
- **Cadence:** Updated Friday evening (after 8PM when CEO report ready)
- **Shows:**
  - Tech Lead reports (per manager)
  - Manager consolidations (per architect)
  - Architect assessments (per BU)
  - BU head metrics (per partner)
  - Partner consolidations (per CEO)

#### 4. Accountability Dashboard (Module: "personal_goals")
- **For Roles:** Self + Manager + CEO
- **Permissions:** "goals.view", "goals.my"
- **Data Filtered By:** Role + BU
- **Shows:**
  - Recruiter's 10 hires/month progress
  - Sales person's $15K/week progress
  - Partner's $5M annual + P&L
  - BU Head's KPIs
  - Your Own Goals (all roles)

---

## Endpoint Architecture (Updated for Multi-BU)

### Financial Accountability

**Partner P&L Endpoint**
```python
GET /operational/partner/{partner_id}/consolidation
# Returns:
# - All BUs for this partner
# - Consolidated revenue, profit, margin %
# - Per-BU breakdown
# - Pace to annual $5M goal
# - P&L Health Score (0-100)

Response:
{
  "partner_id": "partner-123",
  "period": "Week of 2026-08-18",
  "business_units": [
    {
      "bu_id": "bu-001",
      "bu_name": "NA - New York",
      "location": "New York",
      "revenue": "$180K",
      "profit": "$45K",
      "margin": "25%",
      "status": "ON_PACE"
    },
    {
      "bu_id": "bu-002",
      "bu_name": "EU - London",
      "location": "London",
      "revenue": "$120K",
      "profit": "$28K",
      "margin": "23.3%",
      "status": "SLIGHT_LAG"
    }
  ],
  "consolidated": {
    "total_revenue": "$300K",
    "total_profit": "$73K",
    "margin_pct": "24.3%",
    "annual_target": "$5,000,000",
    "ytd_revenue": "$4,080,000",
    "pace_pct": "85%",
    "status": "CAUTION"
  }
}
```

**BU Head Metrics Endpoint**
```python
GET /operational/bu/{bu_id}/metrics
# Returns metrics for SINGLE BU (location-scoped)

Response:
{
  "bu_id": "bu-001",
  "bu_name": "NA - New York",
  "location": "New York",
  "delivery_cadence": "92%",
  "utilization": "73%",
  "revenue": "$180K",
  "headcount": {"total": 25, "new": 2, "departed": 0},
  "status": "HEALTHY"
}
```

**Finance Real-Time Endpoint**
```python
GET /finance/dashboard
# Returns:
# - All partners' current P&L
# - Who's below 25% net profit (ALERT)
# - Hourly profitability check results

Only accessible to: Partner (their BUs), BU Head (their BU), CEO (all), Finance
```

---

## API Endpoints Priority (Systematic Order)

### PHASE 1 (Morning - 4 hours) - CRITICAL PATH

#### 1. Business Unit Scoping Setup
```python
# Create utility to get user's BUs
def get_user_business_units(user_id, db):
    """Get all BUs for this user (via user_roles)"""
    # Query: SELECT DISTINCT bu_id FROM user_roles WHERE user_id = ?
    
def get_user_locations(user_id, db):
    """Get all locations across user's BUs"""
    # Query: SELECT l.* FROM locations l 
    #        JOIN business_units bu ON l.bu_id = bu.id
    #        JOIN user_roles ur ON ur.bu_id = bu.id
    #        WHERE ur.user_id = ?
```

#### 2. Finance Endpoints (Most Critical - Feeds All Dashboards)
```python
# FILE: backend/app/api/v1/endpoints/finance_monitoring.py

router = APIRouter(prefix="/finance", tags=["finance"])

@router.get("/dashboard")
async def get_finance_dashboard(
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Real-time P&L dashboard"""
    # Check user role
    if current_user.role == "PARTNER":
        # Return all their BUs' P&L
        bus = get_user_business_units(current_user.id, db)
        return {
            "partner": current_user.name,
            "business_units": [
                FinanceAgent.calculate_real_time_partner_pl(db, current_user.tenant_id, bu_id)
                for bu_id in bus
            ]
        }
    elif current_user.role == "BU_HEAD":
        # Return their single BU's P&L
        return FinanceAgent.calculate_real_time_partner_pl(
            db, current_user.tenant_id, current_user.business_unit_id
        )
    elif current_user.role == "CEO":
        # Return all partners' P&L
        return FinanceAgent.hourly_partner_check(db, current_user.tenant_id)

@router.get("/partner/{partner_id}/pl")
async def get_partner_pl(partner_id: str, current_user = Depends(get_current_user), db = Depends(get_db)):
    """Partner's consolidated P&L"""
    # Verify access: user is partner OR user is CEO
    # Return: All BUs for this partner + consolidated
    
@router.get("/bu/{bu_id}/pl")
async def get_bu_pl(bu_id: str, current_user = Depends(get_current_user), db = Depends(get_db)):
    """Single BU P&L"""
    # Verify access: user's BU OR user is CEO
    # Return: This BU's metrics only
```

#### 3. Operational Accountability Endpoints
```python
# FILE: backend/app/api/v1/endpoints/operational_accountability.py

@router.get("/partner/{partner_id}/roi")
async def get_partner_roi(partner_id, current_user, db):
    """Partner's weekly revenue tracking"""
    
@router.get("/bu/{bu_id}/health")
async def get_bu_health(bu_id, current_user, db):
    """BU's daily health metrics"""
    
@router.get("/employee/{emp_id}/health")
async def get_employee_health(emp_id, current_user, db):
    """Employee's health score"""
```

#### 4. Pipeline Orchestration Endpoints
```python
# FILE: backend/app/api/v1/endpoints/pipeline_orchestration.py

@router.get("/status")
async def get_pipeline_status(current_user, db):
    """Pipeline queue depths"""
    # Only visible to Manager+ and CEO
    
@router.post("/start/{candidate_id}")
async def start_candidate(candidate_id, current_user, db):
    """Put candidate in pipeline"""
    # Only HR/Recruiters
```

### PHASE 2 (Mid-morning - 2 hours)

#### 5. Agent Pyramid Endpoints
```python
# Only after Finance endpoints working
@router.get("/agents/pyramid")
@router.get("/agents/technical-health")
@router.get("/agents/team-velocity")
```

#### 6. Personal Goal Endpoints
```python
@router.get("/goals/my-progress")
@router.get("/goals/team-progress")
@router.get("/goals/partner-annual")
```

### PHASE 3 (Afternoon - 2 hours)

#### 7. Dashboard Visualization
Create dashboard screens and wire to endpoints

---

## Thursday 3PM Notification Flow

**How It Works:**

```
Thursday 3:00 PM
└─ Finance Agent runs FinanceAgent.hourly_partner_check()
└─ If any partner below 25%: ALERT sent to partner + CEO
└─ Sends notification: "Weekly reports due Friday"
   
   TO: All Org
   SUBJECT: Weekly Report Deadlines (Friday 3PM-8PM)
   
   Tech Leads: Friday 3PM (submit)
   Managers: Friday 4PM (submit)
   Architects: Friday 5PM (submit)
   BU Heads: Friday 6PM (submit)
   Partners: Friday 7PM (submit)
   CEO: Friday 8PM (review & decide)
```

**Implementation:**
1. Add APScheduler job (weekly, Thursday 3PM)
2. Call notification service with deadline summary
3. Email + dashboard notification for each recipient

---

## BU Isolation & Access Control

**Rule: Each user only sees their own BU data (except CEO)**

```python
def get_allowed_business_units(user, db):
    """Get BUs the user can see"""
    if user.role == "CEO":
        # CEO sees all
        return db.query(BusinessUnit).filter(
            BusinessUnit.tenant_id == user.tenant_id
        ).all()
    else:
        # Everyone else: only their assigned BUs
        return get_user_business_units(user.id, db)

def filter_query_by_bu(query, user, bu_foreign_key="business_unit_id"):
    """Add BU filter to any query"""
    allowed_bus = get_allowed_business_units(user)
    bu_ids = [bu.id for bu in allowed_bus]
    return query.filter(bu_foreign_key.in_(bu_ids))
```

**Apply this to EVERY query:**
- Pipeline status → filtered by user's BUs
- Finance metrics → filtered by user's BUs
- Team metrics → filtered by user's BUs
- Reports → filtered by user's BUs (CEO sees all)

---

## Role Template Integration

**Each Dashboard = New Module in role_templates**

```python
# Create role_template entries

DASHBOARD_MODULES = [
    {
        "module_name": "pipeline_orchestration",
        "description": "Pipeline queue status and bottleneck visibility",
        "roles": ["MANAGER", "ARCHITECT", "BU_HEAD", "CEO"],
        "resources": ["pipeline.view", "pipeline.status", "pipeline.queue"]
    },
    {
        "module_name": "finance_monitoring",
        "description": "Real-time P&L tracking and profit monitoring",
        "roles": ["PARTNER", "BU_HEAD", "CEO", "FINANCE"],
        "resources": ["finance.view", "finance.pl", "finance.forecast"]
    },
    {
        "module_name": "agent_pyramid",
        "description": "Weekly hierarchical reporting (Tech Leads → CEO)",
        "roles": ["MANAGER", "ARCHITECT", "BU_HEAD", "PARTNER", "CEO"],
        "resources": ["agents.view", "agents.reports"]
    },
    {
        "module_name": "personal_goals",
        "description": "Individual goal tracking (hiring, sales, revenue)",
        "roles": ["ALL"],  # Everyone sees their own + team sees team members
        "resources": ["goals.view", "goals.my", "goals.team"]
    }
]

# When employee gets role assigned:
# 1. Check role_template for that role
# 2. Activate all modules
# 3. Filter resources by BU
```

---

## Summary: What Needs To Be Done

1. ✅ **Database schema understood** (from models)
2. ❌ **API endpoints** - Create 5 files (~500 LOC)
3. ❌ **BU scoping** - Add utility functions (~100 LOC)
4. ❌ **Role template integration** - Wire dashboards (~200 LOC)
5. ❌ **Notification system** - Thursday 3PM scheduler (~100 LOC)
6. ❌ **Dashboard screens** - Frontend (4-6 hours)

**Total: 12-15 hours to full deployment**

**Critical Path: Finance → Pipeline → Pyramid → Dashboards**

---

## What I Need Confirmed

1. ✅ **Timing**: Thursday 3PM notifications
2. ✅ **Multi-BU**: Partner manages multiple BUs ✓
3. ✅ **Isolation**: Each BU isolated (CEO sees all) ✓
4. ✅ **Access**: Finance only for Partner/BU Head/CEO ✓
5. ✅ **Role Templates**: Dashboards added as modules ✓
6. ✅ **Priority**: Finance → Pipeline → Pyramid ✓

**Missing (Need From You):**
- Database password for PostgreSQL (to test queries)
- OR confirmation to use mock data for development

---

**Ready to implement:** Once you give DB access OR approve mock data approach, I can have all endpoints + dashboards live by tomorrow evening.
