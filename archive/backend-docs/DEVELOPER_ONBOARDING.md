# Developer Onboarding Guide

**Welcome to WROS (Workforce Revenue Operating System)!**

This guide will get you up and running in 30 minutes.

---

## 1. Environment Setup (10 min)

### Prerequisites
- Python 3.9+
- PostgreSQL 18
- Node.js 16+ (for frontend)
- Git

### Step 1.1: Clone Repositories
```bash
# Backend
git clone https://github.com/blitzenx/OnboardingModule-Backend.git
cd OnboardingModule-Backend

# Frontend (in separate directory)
cd ..
git clone https://github.com/blitzenx/OnboardingModule-Frontend-main.git
```

### Step 1.2: Install PostgreSQL 18
**Windows:**
- Download: https://www.postgresql.org/download/windows/
- Install with default settings (user: postgres, password: 123)
- Start service from Services panel

**Mac:**
```bash
brew install postgresql@18
brew services start postgresql@18
```

**Linux:**
```bash
sudo apt update
sudo apt install postgresql-18 postgresql-contrib-18
sudo systemctl start postgresql
```

### Step 1.3: Create Development Database
```bash
# Connect to PostgreSQL
psql -h localhost -U postgres

# Create database
CREATE DATABASE wros_dev;

# Verify (should show wros_dev in list)
\l

# Exit
\q
```

### Step 1.4: Setup Python Environment
```bash
cd OnboardingModule-Backend

# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
.\venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 1.5: Set Environment Variable
```bash
# Windows (PowerShell):
$env:DATABASE_URL = "postgresql://postgres:123@localhost:5432/wros_dev"

# Mac/Linux (Bash):
export DATABASE_URL="postgresql://postgres:123@localhost:5432/wros_dev"

# Verify it's set:
echo $DATABASE_URL
```

### Step 1.6: Initialize Database
```bash
python init_wros_db.py

# Expected output:
# ✅ Creating database schema...
# ✅ Tenants table created
# ✅ Users table created
# ... (169 tables total)
# ✅ Database initialization complete!
```

---

## 2. Understanding the Architecture (10 min)

### The 7 Core Models

The system interconnects these 7 domain entities:

```
CANDIDATE ←→ JOB ←→ CLIENT ←→ PARTNER ←→ BUSINESS UNIT
                ↓          ↓
          OPPORTUNITY    CEO
```

**What they represent:**
- **Candidate:** Job seeker or contractor (person)
- **Job:** Position at a Client company
- **Client:** Company hiring (customer)
- **Opportunity:** Sales pipeline record
- **Partner:** Staffing partner/vendor organization
- **Business Unit (BU):** Internal org unit (NA, EU, APAC, etc.)
- **CEO:** Executive leadership (represented as special OrgNode)

### The 8-Step Workflow

**Complete journey from application to billing:**

```
1. Candidate applies for job (Thunder AI qualifies automatically)
   ↓
2. Interview scheduled (AI coordinates with hiring manager)
   ↓
3. Offer extended (customized salary/terms)
   ↓
4. Candidate converts to Employee (joins org)
   ↓
5. Employee allocated to Project (starts work)
   ↓
6. Timesheet submitted (tracks hours)
   ↓
7. Invoice generated (bill client)
   ↓
8. Payment collected (revenue recognized)
```

**Key insight:** Every step maintains database connections via Foreign Keys. A broken FK = workflow breaks.

### The 169 Tables (Organized by Domain)

| Domain | Purpose | Example Tables |
|--------|---------|-----------------|
| **Core** | Candidate-to-employee pipeline | candidates, jobs, offers, employees, interviews |
| **Engagement** | AI recruiter automation | thunder, conversations, activities, submissions |
| **Finance** | Billing & accounting | invoices, timesheets, expenses, revenue_recognition |
| **Org Structure** | Hierarchy & management | business_units, departments, org_nodes, org_structure |
| **Communication** | Messaging & notifications | email_messages, whatsapp_messages, notifications, tasks |
| **System** | Auth & configuration | users, roles, permissions, rbac, tenants |
| **Analytics** | Reporting & dashboards | activity_feeds, sla_metrics, kpi_tracking, dashboards |

---

## 3. Code Organization (5 min)

### Directory Structure
```
OnboardingModule-Backend/
├── app/
│   ├── main.py                    # FastAPI entry point
│   ├── core/
│   │   ├── database.py            # PostgreSQL connection
│   │   ├── config.py              # Configuration
│   │   └── security.py            # Auth & token handling
│   ├── models/                    # 169 SQLAlchemy models
│   │   ├── __init__.py            # IMPORTANT: Imports all models
│   │   ├── candidate.py
│   │   ├── job.py
│   │   ├── client.py
│   │   ├── user.py
│   │   └── ... (165 more models)
│   ├── services/                  # 206 business logic services
│   │   ├── candidate_service.py
│   │   ├── job_service.py
│   │   ├── client_service.py
│   │   ├── thunder_service.py    # AI recruiter
│   │   └── ... (202 more services)
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/        # 103 REST endpoints
│   │           ├── candidates.py
│   │           ├── jobs.py
│   │           ├── clients.py
│   │           └── ... (100 more endpoints)
│   └── schemas/                   # Pydantic request/response models
│       ├── candidate_schemas.py
│       ├── job_schemas.py
│       └── ...
├── tests/
│   ├── conftest.py               # Test fixtures & PostgreSQL setup
│   ├── test_candidate_to_invoicing.py  # End-to-end workflow test
│   └── test_*.py                 # Individual tests
├── init_wros_db.py               # Database schema initialization
├── requirements.txt              # Python dependencies
├── pytest.ini                    # Test configuration
├── DEPLOYMENT_NOTES.md           # Deployment instructions
├── CLAUDE.md                     # Session notes & architecture decisions
└── README.md                     # Project overview

Frontend (separate repo):
OnboardingModule-Frontend-main/
├── src/
│   ├── components/               # React components
│   ├── screens/                  # Full page screens
│   ├── services/                 # API calls
│   └── App.js                    # Root component
├── package.json
└── README.md
```

### Key Files to Know

**Backend Startup:**
- `app/main.py` - FastAPI app creation & middleware setup
- `app/core/database.py` - PostgreSQL connection pool
- `init_wros_db.py` - Schema creation on startup

**Models (choose by domain):**
- Candidate pipeline: `models/candidate.py`, `models/job.py`, `models/interview.py`
- Finance: `models/invoice.py`, `models/timesheet.py`, `models/expense.py`
- Org: `models/business_unit_context.py`, `models/org_structure.py`

**Services (same naming as models):**
- `services/candidate_service.py` - Candidate CRUD operations
- `services/job_service.py` - Job management (partial)
- `services/thunder_service.py` - AI recruiter automation

**Endpoints (REST API):**
- `api/v1/endpoints/candidates.py` - GET/POST/PUT /candidates
- `api/v1/endpoints/interviews.py` - Interview scheduling
- `api/v1/endpoints/invoices.py` - Invoice management

---

## 4. Common Developer Tasks

### Task 1: Creating a New Endpoint

**Step 1: Check if model exists**
```python
# app/models/my_domain.py
class MyModel(Base):
    __tablename__ = "my_domains"
    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    name = Column(String(100), nullable=False)
    # ... more columns
```

**Step 2: Create service**
```python
# app/services/my_domain_service.py
from sqlalchemy.orm import Session
from app.models.my_domain import MyModel

class MyDomainService:
    def create(self, db: Session, name: str, tenant_id: int) -> MyModel:
        obj = MyModel(name=name, tenant_id=tenant_id)
        db.add(obj)
        db.commit()
        return obj
    
    def get_by_id(self, db: Session, obj_id: str, tenant_id: int) -> MyModel:
        return db.query(MyModel).filter(
            MyModel.id == obj_id,
            MyModel.tenant_id == tenant_id  # ← ALWAYS filter by tenant
        ).first()
```

**Step 3: Create API endpoint**
```python
# app/api/v1/endpoints/my_domain.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.my_domain_service import MyDomainService

router = APIRouter(prefix="/my-domains", tags=["my-domain"])
service = MyDomainService()

@router.post("/")
def create_my_domain(name: str, db: Session = Depends(get_db)):
    # Get current user's tenant_id from request context
    tenant_id = 1  # In real code: get from authenticated user
    return service.create(db, name, tenant_id)

@router.get("/{obj_id}")
def get_my_domain(obj_id: str, db: Session = Depends(get_db)):
    tenant_id = 1
    obj = service.get_by_id(db, obj_id, tenant_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    return obj
```

**Step 4: Register endpoint in main app**
```python
# app/main.py
from app.api.v1.endpoints import my_domain

app = FastAPI()
app.include_router(my_domain.router, prefix="/api/v1")
```

### Task 2: Adding a Foreign Key Relationship

**Critical:** FK column type must match parent column type!

```python
# Bad (Integer → String mismatch):
class Child(Base):
    parent_id = Column(Integer, ForeignKey("parents.id"))
    # ❌ If parents.id is String(36), this will fail

# Good (types match):
class Child(Base):
    parent_id = Column(String(36), ForeignKey("parents.id"))
    # ✅ Both are String(36)
    parent = relationship("Parent", foreign_keys=[parent_id], lazy="select")
    # ✅ relationship() enables ORM loading
```

### Task 3: Writing Tests

```python
# tests/test_my_feature.py
import pytest
from sqlalchemy.orm import Session
from app.services.my_domain_service import MyDomainService

@pytest.fixture
def service():
    return MyDomainService()

def test_create_my_domain(db: Session, service):
    """Test creating a new record"""
    obj = service.create(db, name="Test", tenant_id=1)
    
    assert obj.id is not None
    assert obj.name == "Test"
    assert obj.tenant_id == 1

def test_get_my_domain(db: Session, service):
    """Test retrieving a record"""
    created = service.create(db, name="Test", tenant_id=1)
    retrieved = service.get_by_id(db, created.id, tenant_id=1)
    
    assert retrieved.id == created.id
    assert retrieved.name == "Test"

def test_multi_tenancy_isolation(db: Session, service):
    """Test that tenant_id prevents data leakage"""
    # Create in tenant 1
    obj1 = service.create(db, name="Tenant1", tenant_id=1)
    
    # Try to get it as tenant 2 (should be None)
    obj2 = service.get_by_id(db, obj1.id, tenant_id=2)
    
    assert obj2 is None  # ← Multi-tenancy working!
```

**Run tests:**
```bash
pytest tests/test_my_feature.py -v
# Or specific test:
pytest tests/test_my_feature.py::test_create_my_domain -v
```

### Task 4: Debugging a Broken FK

**Error message:**
```
FOREIGN KEY constraint failed: INSERT or UPDATE on table "child_table" violates foreign key constraint
```

**Diagnosis:**
```bash
# 1. Check parent table has the record
psql -h localhost -U postgres -d wros_dev
SELECT * FROM parent_table WHERE id = 'abc123';

# 2. Check column type matches
\d parent_table  # Check id column type
\d child_table   # Check parent_id column type
# Types must match! (both String(36) or both Integer, etc.)

# 3. Check if parent exists before inserting child
INSERT INTO child_table (parent_id) VALUES ('abc123');
# Only works if 'abc123' exists in parent_table.id
```

### Task 5: Checking Multi-Tenancy

**Always verify tenant isolation:**
```python
# WRONG - Exposes data across tenants:
candidates = db.query(Candidate).all()

# RIGHT - Filters by current tenant:
candidates = db.query(Candidate).filter(
    Candidate.tenant_id == current_user.tenant_id
).all()
```

---

## 5. Common Commands

### Backend Commands
```bash
# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_candidate_to_invoicing.py -v

# Check code quality
flake8 app/

# View database
psql -h localhost -U postgres -d wros_dev

# List all tables
\dt

# Describe a table
\d candidates

# Query data
SELECT * FROM candidates LIMIT 5;
```

### Frontend Commands
```bash
cd ../OnboardingModule-Frontend-main

# Install dependencies
npm install

# Start development server
npm start

# Build for production
npm run build

# Run tests
npm test
```

### Git Commands
```bash
# Create feature branch
git checkout -b feature/my-feature

# Commit changes
git commit -m "Brief description of change"

# Push to remote
git push origin feature/my-feature

# Create pull request (on GitHub)
# ... review & merge ...

# Switch back to main
git checkout main
git pull origin main
```

---

## 6. Architecture Principles

### Principle 1: Never Hardcode
```python
# ❌ WRONG
DATABASE_URL = "postgresql://postgres:123@localhost:5432/wros_dev"

# ✅ CORRECT
DATABASE_URL = os.environ.get("DATABASE_URL")
```

### Principle 2: Always Use ORM
```python
# ❌ WRONG (raw SQL)
result = db.execute("SELECT * FROM candidates WHERE id = ?", [candidate_id])

# ✅ CORRECT (ORM)
candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
```

### Principle 3: Filter by Tenant
```python
# ❌ WRONG (exposes all tenants' data)
candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()

# ✅ CORRECT (tenant isolation)
candidate = db.query(Candidate).filter(
    Candidate.id == candidate_id,
    Candidate.tenant_id == current_user.tenant_id
).first()
```

### Principle 4: Use Relationships
```python
# ❌ WRONG (separate queries → N+1 problem)
candidate = db.query(Candidate).filter(Candidate.id == cid).first()
jobs = db.query(Job).filter(Job.candidate_id == cid).all()  # Extra query!

# ✅ CORRECT (single query with relationship)
candidate = db.query(Candidate).filter(Candidate.id == cid).first()
jobs = candidate.jobs  # Already loaded via relationship!
```

### Principle 5: Document Complex Logic
```python
def calculate_bill_rate(base_rate, markup_pct, billing_currency):
    """
    Calculate final bill rate for a candidate allocation.
    
    Args:
        base_rate: Hourly rate in USD cents
        markup_pct: Markup percentage (5-15 typical)
        billing_currency: Currency for billing (USD, INR, etc.)
    
    Returns:
        Final bill rate in USD cents (always stored in cents per R-09)
    
    Note:
        Currency conversion (HRMS-0121) not implemented yet.
        Caller responsible for pre-converting to USD cents.
    """
    return base_rate * (1 + markup_pct / 100)
```

---

## 7. Important Rules

### Golden Rules
1. **Never change DATABASE_URL in code** - Use environment variable
2. **Never skip tenant_id checks** - Will leak data across tenants
3. **Never hardcode secrets** - Use environment variables
4. **Never use raw SQL** - Use SQLAlchemy ORM
5. **Never change ports 8080/3000** - Other systems depend on them

### Before Committing
- [ ] Tests pass: `pytest tests/ -v`
- [ ] Code is formatted: `flake8 app/`
- [ ] All FK types match
- [ ] All queries filter by tenant_id
- [ ] No secrets in code
- [ ] Comments explain WHY, not WHAT

### Code Review Checklist
- [ ] Does it use ORM (not raw SQL)?
- [ ] Does it filter by tenant_id?
- [ ] Are all FKs properly defined?
- [ ] Are relationships used (not separate queries)?
- [ ] Is the change backward compatible?
- [ ] Are new tests included?

---

## 8. Getting Help

### Before Asking:
1. **Check logs:** `tail -f logs/app.log`
2. **Check similar code:** Search codebase for similar pattern
3. **Check documentation:** Read CLAUDE.md & DEPLOYMENT_NOTES.md
4. **Run tests:** Verify test passes in isolation

### When Asking:
1. Include error message (full stack trace)
2. Share what you tried to fix it
3. Share the code that's failing
4. Share database schema if schema-related

### Resources:
- **Architecture:** CLAUDE.md (session notes & decisions)
- **Deployment:** DEPLOYMENT_NOTES.md (step-by-step guide)
- **Tests:** tests/test_*.py (examples of patterns)
- **Endpoints:** app/api/v1/endpoints/*.py (API examples)

---

## 9. Your First Task

**Objective:** Get familiar with the workflow by running the end-to-end test

```bash
# 1. Make sure PostgreSQL is running
psql -h localhost -U postgres -c "SELECT version();"

# 2. Make sure wros_dev database exists
psql -h localhost -U postgres -d wros_dev -c "SELECT 1;"

# 3. Set environment variable
export DATABASE_URL="postgresql://postgres:123@localhost:5432/wros_dev"

# 4. Create schema
python init_wros_db.py

# 5. Run the complete workflow test
pytest tests/test_candidate_to_invoicing.py -v -s

# 6. Read the test output and understand each step:
#    - Candidate created
#    - Job assigned
#    - Interview scheduled
#    - Offer created
#    - Employee created
#    - Allocation created
#    - Timesheet created
#    - Invoice created
```

**Expected output:**
```
test_candidate_to_invoicing.py::test_complete_workflow PASSED ✓
================================ 1 passed in 0.45s ================================
```

**If test fails:**
1. Check error message
2. Verify PostgreSQL is running
3. Check DATABASE_URL is set
4. Try running init_wros_db.py again
5. Ask for help with full error message

---

## Welcome! 🚀

You're now ready to start developing. Pick a feature, find the corresponding model/service/endpoint, and follow the patterns you see.

**Remember:** When in doubt, ask! The team is here to help.

**Happy coding! 💻**

