# HARDCODING REMEDIATION CHECKLIST
**For Development Teams - Phase 1-4 Execution**

---

## PHASE 1: CRITICAL - MULTI-TENANT FOUNDATION (Weeks 1-2)

### Step 1.1: Create Tenant Context Extraction Utility

**Owner:** Architect  
**Timeline:** Day 1  
**File:** `backend/app/core/tenant_context.py` (NEW)

**Checklist:**
- [ ] Create utility module: `tenant_context.py`
- [ ] Function: `get_tenant_id_from_user(current_user: Users) -> int`
  - [ ] Validates current_user not None
  - [ ] Returns current_user.tenant_id
  - [ ] Raises 401 if no tenant context
- [ ] Function: `get_tenant_id_from_request(request: Request) -> int`
  - [ ] Extract from JWT token 'sub' claim
  - [ ] Fallback to user lookup
- [ ] Add docstring with examples
- [ ] Add unit tests (positive + negative cases)
- [ ] Import in all endpoints that currently hardcode tenant_id=1

**Test Cases:**
```python
def test_get_tenant_id_returns_user_tenant():
    """Verify tenant extraction from user"""
    
def test_get_tenant_id_raises_on_missing_user():
    """Verify 401 when no user context"""
    
def test_get_tenant_id_from_jwt():
    """Verify extraction from JWT token"""
```

**Acceptance:** 
- [ ] Utility tested and working
- [ ] Used in 2+ endpoints
- [ ] No hardcoded tenant_id=1 left in utility

---

### Step 1.2: Refactor Database Initialization

**Owner:** Backend Lead  
**Timeline:** Days 2-3  
**Files:** `backend/app/core/db_contract.py`, `backend/app/main.py`

**Checklist:**

**For db_contract.py:**
- [ ] Modify `initialize_database()` to accept `tenant_id` parameter
  - [ ] Default: 1 (for first-time setup)
  - [ ] Can be overridden via environment variable
- [ ] Update `_initialize_tenant()` to accept `tenant_id`
- [ ] Update `_initialize_rbac()` to accept `tenant_id`
- [ ] Update `_initialize_admin_user()` to accept `tenant_id`
- [ ] Replace ALL hardcoded `tenant_id=1` with parameter
- [ ] Count lines modified: Should be ~15 locations

**For main.py (Startup):**
- [ ] On startup, call: `initialize_database(tenant_id=1)`
  - [ ] Can be overridden: `INIT_TENANT_ID` env var
- [ ] Log: "[OK] Database initialized for tenant_id={tenant_id}"

**Test Cases:**
```python
def test_database_initialization_accepts_tenant_id():
    """Verify initialization with custom tenant"""
    
def test_rbac_created_for_custom_tenant():
    """Verify RBAC modules created for tenant_id=2"""
    
def test_admin_user_created_for_tenant():
    """Verify admin user has correct tenant_id"""
```

**Acceptance:**
- [ ] All hardcoded tenant_id=1 removed from db_contract.py
- [ ] Initialization works for any tenant_id
- [ ] Tests pass for tenant_id=1 and tenant_id=2
- [ ] Startup logs show correct tenant_id

---

### Step 1.3: Audit All Endpoints for Hardcoding

**Owner:** Backend Team (split by file)  
**Timeline:** Days 3-5  
**Deliverable:** Spreadsheet with all locations

**Checklist:**
- [ ] Create spreadsheet: `ENDPOINT_AUDIT_RESULTS.csv`
  - Columns: File | Line | Current Code | Required Change | Assigned To
- [ ] Search: `grep -r "tenant_id=1" backend/app/api/` 
- [ ] For each result:
  - [ ] Document file and line number
  - [ ] Identify if it's in an endpoint function
  - [ ] Check if function has `current_user` parameter
  - [ ] Assign to developer
- [ ] Count total locations: Should be ~27
- [ ] Assign to developers for fixing

**Expected Locations:**
- candidates.py: 1-2 locations
- certifications_admin.py: 4 locations
- complete_workflow.py: 2 locations
- create_job.py: 1 location
- hiring_manager_validation.py: 4 locations
- config.py: 1 location
- ops_alert_handler.py: 1 location
- Other files: ~5-10 locations

**Acceptance:**
- [ ] All 27 locations documented
- [ ] Each assigned to developer
- [ ] List sent to team

---

### Step 1.4: Fix All Hardcoded tenant_id=1 in Endpoints

**Owner:** Backend Team (individual developers)  
**Timeline:** Days 4-7  
**Per-file checklist:**

**For each endpoint file with tenant_id=1:**

```python
# BEFORE
def endpoint(
    request: Request,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tenant_id = 1  # ❌ HARDCODED

# AFTER
def endpoint(
    request: Request,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.core.tenant_context import get_tenant_id_from_user
    tenant_id = get_tenant_id_from_user(current_user)  # ✅ DYNAMIC
```

**Per file checklist:**
- [ ] Import `get_tenant_id_from_user` at top
- [ ] Replace all `tenant_id = 1` with utility call
- [ ] Verify function has `current_user` parameter
- [ ] Test endpoint (ensure it still works)
- [ ] Verify data isolation (queries filter by tenant_id)
- [ ] Commit with message: "refactor: Extract tenant_id from context in {file}"

**Test Each Fix:**
```bash
# 1. Create test tenant 1 data
# 2. Create test tenant 2 data
# 3. Login as user from tenant 1
# 4. Call endpoint
# 5. Verify only tenant 1 data returned
# 6. Repeat for tenant 2
```

**Acceptance:**
- [ ] No hardcoded tenant_id=1 remains in file
- [ ] All endpoints extract from context
- [ ] Multi-tenant tests pass
- [ ] Code review approved

---

### Step 1.5: Fix File Paths (Windows-Specific)

**Owner:** DevOps + Backend  
**Timeline:** Day 4

**Files to Fix:**
1. `backend/app/services/architect_codebase_audit.py` line 60
2. `backend/app/services/autonomous_sdlc_service.py` lines 363, 369

**Before:**
```python
repo_root: str = "C:\\Users\\AvinashMukund\\Documents\\Claude\\WROS-Master"
```

**After:**
```python
import os
repo_root: str = os.getenv("REPO_ROOT", os.path.dirname(os.path.dirname(__file__)))
# Or: Use git to find repo root
import subprocess
def get_repo_root():
    return subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).decode().strip()
```

**Checklist:**
- [ ] Remove absolute path hardcoding
- [ ] Use environment variable: `REPO_ROOT`
- [ ] Add fallback: `os.getcwd()`
- [ ] Test on Linux/Mac (verify paths work)
- [ ] Test in CI/CD (GitHub Actions)
- [ ] Document: Add `REPO_ROOT` to .env template

**Acceptance:**
- [ ] Code runs without Windows paths
- [ ] CI/CD builds succeed
- [ ] Environment variable documented

---

### Step 1.6: Add Multi-Tenant Query Filters

**Owner:** Database Team  
**Timeline:** Days 6-7

**Checklist:**
- [ ] Audit all queries in `candidates.py`, `jobs.py`, `interviews.py`
- [ ] Every `SELECT * FROM table` should include: `WHERE tenant_id = :tenant_id`
- [ ] Example:

**Before:**
```python
candidates = db.query(Candidate).all()  # ❌ Returns ALL candidates
```

**After:**
```python
candidates = db.query(Candidate).filter(
    Candidate.tenant_id == tenant_id  # ✅ Only this tenant
).all()
```

**Test:**
```python
def test_candidate_query_filters_by_tenant():
    """Verify Candidate queries filter by tenant_id"""
    # Create candidate for tenant 1
    # Create candidate for tenant 2
    # Query as tenant 1 user
    # Verify only tenant 1 candidate returned
```

**Acceptance:**
- [ ] All queries include tenant_id filter
- [ ] Multi-tenant tests pass
- [ ] No data leakage between tenants

---

### Step 1.7: Remove Hardcoded File Paths

**Owner:** Backend  
**Timeline:** Day 5

**Checklist:**
- [ ] `architect_codebase_audit.py`: Use `os.getcwd()` instead of absolute path
- [ ] `autonomous_sdlc_service.py`: Use `REPO_ROOT` environment variable
- [ ] Add `.env` entry: `REPO_ROOT=/path/to/repo`
- [ ] Test: Verify code works on different machines
- [ ] CI/CD: Ensure GitHub Actions can run without Windows paths

**Acceptance:**
- [ ] No Windows paths in code
- [ ] Works on Linux/Mac
- [ ] CI/CD builds pass

---

### Step 1.8: Create & Run Multi-Tenant Tests

**Owner:** QA + Backend  
**Timeline:** Days 6-8

**Test Scenarios:**

**1. Tenant Isolation Test**
```python
def test_tenant_a_cannot_see_tenant_b_candidates():
    """Critical: Verify GDPR data isolation"""
    # Setup: Create two tenants + test data
    # Action: Login as tenant A, query candidates
    # Verify: Only tenant A candidates returned
    # Verify: Tenant B candidates not visible
```

**2. Multi-Tenant Login Test**
```python
def test_login_returns_correct_tenant_id():
    """Verify JWT token includes correct tenant_id"""
    # Action: User A logs in (tenant_id=1)
    # Verify: JWT contains tenant_id=1
    # Action: User B logs in (tenant_id=2)
    # Verify: JWT contains tenant_id=2
```

**3. Endpoint Isolation Test**
```python
def test_endpoint_filters_by_user_tenant():
    """Verify endpoints respect tenant_id from user"""
    # Action: Call endpoint as tenant 1
    # Verify: Gets tenant 1 data
    # Action: Call same endpoint as tenant 2
    # Verify: Gets tenant 2 data (different set)
```

**Checklist:**
- [ ] Write 3+ multi-tenant test scenarios
- [ ] Create test data for tenant 1 and tenant 2
- [ ] Run tests on all endpoints handling data
- [ ] Document test results
- [ ] All tests passing before Phase 1 complete

**Acceptance:**
- [ ] Multi-tenant tests created and passing
- [ ] Data isolation verified
- [ ] No data leakage between tenants

---

### Step 1.9: Phase 1 Testing & Deployment

**Owner:** QA + DevOps  
**Timeline:** Day 9

**Checklist:**
- [ ] Run full test suite: `pytest backend/tests/`
- [ ] All 87 hardcoding-related tests passing
- [ ] Code review: Architect reviews all changes
- [ ] Security review: Verify no hardcoded values remain
- [ ] Deploy to staging: Verify no regressions
- [ ] Documentation: Update DEVELOPMENT.md with multi-tenant approach

**Acceptance Criteria:**
- [ ] All tests passing
- [ ] Zero hardcoded tenant_id=1 in business logic
- [ ] Multi-tenant data isolation verified
- [ ] Code review approved
- [ ] Ready for Phase 2

---

## PHASE 2: HIGH - CONFIGURATION EXTERNALIZATION (Week 3)

### Step 2.1: Create TenantConfiguration Model

**Owner:** Database Team  
**Timeline:** Day 1

**File:** `backend/app/models/tenant_config.py` (NEW)

**Schema:**
```python
class TenantConfiguration(Base):
    __tablename__ = "tenant_configurations"
    
    id = Column(UUID, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), unique=True)
    
    # Email Configuration
    service_email = Column(String(255))  # e.g., helpdesk@customerb.com
    service_email_oauth_account = Column(String(255))  # Microsoft Graph account
    
    # System Configuration
    default_timeout_seconds = Column(Integer, default=30)
    api_retry_count = Column(Integer, default=3)
    batch_size = Column(Integer, default=100)
    
    # Feature Flags
    enable_whatsapp = Column(Boolean, default=True)
    enable_email = Column(Boolean, default=True)
    enable_sms = Column(Boolean, default=True)
    enable_slack = Column(Boolean, default=False)
    
    # Business Configuration
    business_model = Column(String(100))  # e.g., "staffing", "hrm", "recruiting"
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**Checklist:**
- [ ] Create TenantConfiguration model
- [ ] Add fields: service_email, timeouts, feature_flags
- [ ] Create migration or add to db_contract.py initialization
- [ ] Initialize default config for tenant_id=1 (BlitzenX)
- [ ] Document schema

---

### Step 2.2: Create ConfigService

**Owner:** Backend  
**Timeline:** Day 2

**File:** `backend/app/services/config_service.py` (NEW)

**Functions:**
```python
class ConfigService:
    @staticmethod
    def get_tenant_config(db: Session, tenant_id: int) -> TenantConfiguration:
        """Get tenant configuration or raise"""
        
    @staticmethod
    def get_service_email(db: Session, tenant_id: int) -> str:
        """Get service email for tenant"""
        
    @staticmethod
    def get_timeout(db: Session, tenant_id: int, timeout_type: str) -> int:
        """Get timeout value for tenant"""
        
    @staticmethod
    def is_feature_enabled(db: Session, tenant_id: int, feature: str) -> bool:
        """Check if feature is enabled for tenant"""
        
    @staticmethod
    def update_config(db: Session, tenant_id: int, updates: dict) -> TenantConfiguration:
        """Update tenant configuration"""
```

**Checklist:**
- [ ] Create ConfigService class
- [ ] Implement get_tenant_config() method
- [ ] Add caching (avoid repeated DB queries)
- [ ] Add unit tests
- [ ] Document usage in comments

---

### Step 2.3: Update Email Service to Use Configuration

**Owner:** Backend  
**Timeline:** Day 2

**File:** `backend/app/services/email_service.py`

**Before:**
```python
SERVICE_EMAIL = "helpdesk_hrms@blitzenx.com"  # ❌ Hardcoded
```

**After:**
```python
@staticmethod
def get_service_email(db: Session, tenant_id: int) -> str:
    """Get service email from config"""
    return ConfigService.get_service_email(db, tenant_id)

async def send_email(
    to: str,
    subject: str,
    body: str,
    tenant_id: int,
    db: Session
):
    service_email = self.get_service_email(db, tenant_id)  # ✅ Dynamic
```

**Checklist:**
- [ ] Remove hardcoded SERVICE_EMAIL constant
- [ ] Replace with ConfigService call
- [ ] Update all callers to pass tenant_id
- [ ] Test with multiple emails for different tenants
- [ ] Verify emails send from correct address

---

### Step 2.4: Move CORS Origins to Configuration

**Owner:** Backend  
**Timeline:** Day 3

**Files:** `backend/app/middleware/cors.py`, `backend/app/core/config.py`

**Before:**
```python
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    ...
]
```

**After:**
```python
def get_cors_origins(db: Session, tenant_id: int) -> list:
    """Get CORS origins from config"""
    config = ConfigService.get_tenant_config(db, tenant_id)
    return config.cors_origins.split(',') if config.cors_origins else []
```

**Checklist:**
- [ ] Add cors_origins field to TenantConfiguration
- [ ] Create function to retrieve CORS origins per tenant
- [ ] Update middleware to use function
- [ ] Test CORS with multiple tenants
- [ ] Document CORS configuration format

---

### Step 2.5: Create Admin API for Tenant Configuration

**Owner:** Backend  
**Timeline:** Day 3-4

**File:** `backend/app/api/v1/endpoints/admin_tenant_config.py` (NEW)

**Endpoints:**
```
GET /admin/tenants/{tenant_id}/config
  - Returns: TenantConfiguration JSON
  - Auth: Admin only
  
POST /admin/tenants/{tenant_id}/config
  - Updates: TenantConfiguration
  - Auth: Admin only
  
GET /admin/tenants/{tenant_id}/config/service-email
  - Returns: { service_email: "..." }
  
PUT /admin/tenants/{tenant_id}/config/service-email
  - Sets: { service_email: "..." }
```

**Checklist:**
- [ ] Create admin endpoint file
- [ ] Add GET endpoints to read config
- [ ] Add POST/PUT endpoints to update config
- [ ] Add auth checks (admin only)
- [ ] Add validation (e.g., valid email format)
- [ ] Document endpoints in API docs
- [ ] Test via curl/Postman

---

### Step 2.6: Update Timeouts to Use Configuration

**Owner:** Backend  
**Timeline:** Day 4

**Files to Update:**
- backend/app/api/v1/endpoints/documents.py
- backend/app/api/v1/endpoints/msgraph.py
- backend/app/services/autonomous_sdlc_service.py
- All files with hardcoded timeout values

**Before:**
```python
response = requests.get(endpoint, timeout=10)  # ❌ Hardcoded
```

**After:**
```python
timeout = ConfigService.get_timeout(db, tenant_id, "api_request")  # ✅ Configurable
response = requests.get(endpoint, timeout=timeout)
```

**Checklist:**
- [ ] Create timeout configuration table
- [ ] Add get_timeout() method to ConfigService
- [ ] Replace all hardcoded timeouts with ConfigService calls
- [ ] Test with different timeout values
- [ ] Verify retries respect timeout configuration

---

### Step 2.7: Phase 2 Testing & Documentation

**Owner:** Backend + Architect  
**Timeline:** Day 5

**Checklist:**
- [ ] All config endpoints tested
- [ ] Multi-tenant config isolation verified
- [ ] Documentation: How to configure service email, timeouts, features
- [ ] README update: Configuration management section
- [ ] Example: How to create custom config for tenant 2

**Test Cases:**
```python
def test_config_service_returns_tenant_config():
    """Verify config retrieval"""
    
def test_service_email_from_config():
    """Verify emails use tenant-specific email"""
    
def test_timeout_configurable():
    """Verify timeout can be changed per tenant"""
    
def test_feature_flag_respected():
    """Verify features can be enabled/disabled"""
```

**Acceptance Criteria:**
- [ ] All configuration externalized from code
- [ ] Can be updated without redeployment
- [ ] Tested for multiple tenants
- [ ] Documented for operators
- [ ] Ready for Phase 3

---

## PHASE 3: HIGH - BUSINESS LOGIC FLEXIBILITY (Weeks 4-5)

**Owner:** Architect + Product Lead  
**Status:** Plan created in Phase 1, execute in Weeks 4-5

**Key Tasks:**
1. Document current BlitzenX workflows
2. Identify what's BlitzenX-specific vs. generic
3. Create CompanyProfile configuration model
4. Refactor workflows into decision trees
5. Make Spartan Phalanx agent system configurable

**High-level Checklist:**
- [ ] Create CompanyProfile model
- [ ] Document 5+ customer archetypes (staffing, HR, recruiting, etc.)
- [ ] Refactor agent system to use profiles
- [ ] Test with 2+ different business models
- [ ] No BlitzenX-specific code in endpoints

---

## PHASE 4: SECURITY - HARDENING (Week 6)

### Step 4.1: Remove Hardcoded Passwords

**Owner:** Security Team  
**Timeline:** Day 1

**File:** `backend/app/core/db_contract.py`

**Before:**
```python
UserPassword=get_password_hash("Admin@123")
```

**After:**
```python
import secrets
import string

def generate_secure_password(length: int = 32) -> str:
    """Generate cryptographically secure random password"""
    chars = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(chars) for _ in range(length))

# In _initialize_admin_user():
admin_password = generate_secure_password()
user.UserPassword = get_password_hash(admin_password)
# IMPORTANT: Return password to user via secure channel (NOT logged)
return {
    "user_id": user.UserID,
    "temporary_password": admin_password  # Sent via email, never logged
}
```

**Checklist:**
- [ ] Remove hardcoded password strings
- [ ] Implement secure password generation
- [ ] Return password via API only (not logged)
- [ ] Disable password after first login (force change)
- [ ] Audit git history for exposed passwords

---

### Step 4.2: Implement Credential Vault Integration

**Owner:** Security + DevOps  
**Timeline:** Days 2-3

**Options:**
- HashiCorp Vault
- AWS Secrets Manager
- Azure Key Vault

**Checklist:**
- [ ] Select vault solution
- [ ] Create vault namespace for WROS
- [ ] Migrate secrets: Database password, OAuth token, API keys
- [ ] Create Vault client wrapper: `backend/app/core/vault.py`
- [ ] Update startup: Load secrets from vault, not .env
- [ ] Test: Verify secrets not in logs

**Example (Vault):**
```python
from hvac import Client as VaultClient

class SecretStore:
    def __init__(self):
        self.vault = VaultClient(url=os.getenv("VAULT_ADDR"))
        self.vault.auth.userpass.login(
            username=os.getenv("VAULT_USER"),
            password=os.getenv("VAULT_PASS")
        )
    
    def get_database_password(self, tenant_id: int) -> str:
        """Get DB password from vault"""
        secret = self.vault.secrets.kv.v2.read_secret_version(
            path=f"wros/tenant-{tenant_id}/db-password"
        )
        return secret['data']['data']['password']
```

---

### Step 4.3: Audit All Logs for Credential Exposure

**Owner:** Security  
**Timeline:** Day 4

**Checklist:**
- [ ] Search git history: `git log -p | grep -i password`
- [ ] Search logs: `grep -r "Admin@123\|TestUser@123" backend/`
- [ ] Search code: `grep -r "password.*=" backend/app/`
- [ ] Check .env files: No secrets should be committed
- [ ] Review CI/CD logs: Ensure no secrets printed
- [ ] Create git pre-commit hook: Block secret patterns

**Git Hook Example:**
```bash
#!/bin/bash
# .git/hooks/pre-commit - Block secret commits

PATTERNS=(
    "password.*=.*['\"]"
    "api.key.*="
    "Admin@123"
    "TestUser@123"
    "[A-Z0-9]{32}"  # Potential API keys
)

for pattern in "${PATTERNS[@]}"; do
    if git diff --cached | grep -E "$pattern"; then
        echo "ERROR: Potential secret in commit"
        exit 1
    fi
done
```

---

### Step 4.4: Implement Credential Rotation

**Owner:** Security + DevOps  
**Timeline:** Day 5

**Checklist:**
- [ ] Create rotation policy: Credentials rotated quarterly
- [ ] Automate rotation: Vault + Lambda/Cronjob
- [ ] Update deployment: New credentials on each deploy
- [ ] Document: How to rotate credentials manually
- [ ] Test: Rotation doesn't break running instances

---

### Step 4.5: Security Audit & Certification

**Owner:** Security  
**Timeline:** Day 5-6

**Checklist:**
- [ ] Run security scanner: `bandit backend/app/`
- [ ] Code review: Security team reviews all credential changes
- [ ] Penetration test: Try to find exposed secrets
- [ ] Compliance audit: GDPR, SOC 2, etc.
- [ ] Generate security report: Document all fixes
- [ ] Get sign-off from security lead

---

## CROSS-PHASE TESTING & VALIDATION

### Integration Tests (Run After Each Phase)

**Test Template:**
```python
@pytest.mark.integration
class TestMultiTenantIsolation:
    @pytest.fixture
    def setup(self, db):
        # Create tenant 1 + 2
        # Create test data for each
        # Create users for each tenant
        return {...}
    
    def test_candidates_isolated(self, client, setup):
        """Verify candidates not visible across tenants"""
        
    def test_jobs_isolated(self, client, setup):
        """Verify jobs not visible across tenants"""
        
    def test_emails_use_tenant_email(self, client, setup):
        """Verify service email from config"""
        
    def test_configuration_isolated(self, client, setup):
        """Verify config not visible across tenants"""
```

**Run after each phase:**
```bash
pytest backend/tests/test_multi_tenant_integration.py -v
```

---

## CODE REVIEW GATES

### Gate Rules (Enforce via CI/CD)

**Automated checks:**
- [ ] No hardcoded tenant_id=1 (outside db_contract.py initialization)
- [ ] No hardcoded service emails
- [ ] No hardcoded file paths (Windows-specific)
- [ ] No hardcoded credentials
- [ ] No TODO comments about "get from context"

**Example GitHub Actions workflow:**
```yaml
name: Hardcoding Detection
on: [pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Check for hardcoding violations
        run: |
          # Detect patterns
          if grep -r "tenant_id = 1" --include="*.py" backend/app/api/; then
            echo "ERROR: Hardcoded tenant_id=1 in endpoints"
            exit 1
          fi
          
          if grep -r "helpdesk_hrms@blitzenx.com" --include="*.py" backend/app/ | grep -v test | grep -v comment; then
            echo "ERROR: Hardcoded email in non-test code"
            exit 1
          fi
          
          if grep -r "C:\\Users\\Avinash" --include="*.py" backend/; then
            echo "ERROR: Windows file path detected"
            exit 1
          fi
```

---

## SIGN-OFF CHECKLIST

### Before Each Phase Completes

**Phase 1 Sign-Off:**
- [ ] Architect: "Multi-tenant foundation is solid"
- [ ] Backend Lead: "All endpoints extract tenant from context"
- [ ] QA: "Multi-tenant tests passing"
- [ ] Product: "No feature regressions"

**Phase 2 Sign-Off:**
- [ ] Backend Lead: "All config externalized"
- [ ] DevOps: "Configuration manageable via API"
- [ ] Security: "No credentials in code"
- [ ] Product: "Can deploy with different configs"

**Phase 3 Sign-Off:**
- [ ] Architect: "Business logic configurable"
- [ ] Product: "Can support multiple business models"
- [ ] Engineering: "Code is flexible and maintainable"

**Phase 4 Sign-Off:**
- [ ] Security: "All credential storage secure"
- [ ] Compliance: "Meets GDPR/SOC 2 requirements"
- [ ] CTO: "Ready for SaaS launch"

---

## PROGRESS TRACKING

**Create a spreadsheet:** `REMEDIATION_PROGRESS.xlsx`

| Phase | Task | Owner | Status | % Complete | Target Date |
|-------|------|-------|--------|------------|-------------|
| 1.1 | Tenant Context Utility | Architect | In Progress | 50% | 2026-09-20 |
| 1.2 | Refactor DB Init | Backend | Not Started | 0% | 2026-09-22 |
| ... | ... | ... | ... | ... | ... |

**Update daily in standup.**

---

## COMPLETION CRITERIA

### Phase 1 Complete When:
- ✅ All 27 hardcoded tenant_id=1 removed
- ✅ All endpoints extract from context
- ✅ Multi-tenant tests passing
- ✅ Zero data leakage between tenants
- ✅ Code review approved

### Phase 2 Complete When:
- ✅ All 19 config values externalized
- ✅ ConfigService tested
- ✅ Admin API documented
- ✅ Operators can change config without redeploy

### Phase 3 Complete When:
- ✅ BlitzenX-specific logic removed from endpoints
- ✅ Business model configurable
- ✅ 2+ different companies supported (in test)
- ✅ No company-specific code in core

### Phase 4 Complete When:
- ✅ Zero hardcoded credentials
- ✅ All secrets in vault
- ✅ Security audit passed
- ✅ GDPR certified

---

## RISK MITIGATION STRATEGIES

**If a task takes longer than estimated:**
1. Extend timeline by 2-3 days (build in buffer)
2. Skip low-priority aspects
3. Escalate to steering committee

**If critical issues found during implementation:**
1. Pause current phase
2. Create hotfix branch
3. Review with architecture team
4. Resume after hotfix merged

**If test failures discovered:**
1. Root cause analysis
2. Fix the issue (don't mask)
3. Add regression test
4. Resume testing

---

## COMMUNICATION PLAN

**Weekly Updates (Every Friday):**
- Email progress to stakeholders
- Highlight blockers
- Update timeline if needed

**Daily Standups (15 min):**
- What was completed
- What's in progress
- Blockers and help needed

**Steering Committee (Weekly):**
- Status review
- Risk assessment
- Timeline confidence

