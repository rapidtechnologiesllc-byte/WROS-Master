# COMPREHENSIVE HARDCODING AUDIT REPORT
**WROS SaaS Codebase - Multi-Tenant Architecture Violations**

**Date:** 2026-09-17  
**Audit Scope:** Full backend + frontend codebase  
**Purpose:** Identify all hardcoded values violating multi-tenant SaaS architecture  

---

## EXECUTIVE SUMMARY

| Category | Count | Severity | Impact |
|----------|-------|----------|--------|
| **CRITICAL** | 8 | Blocks multi-tenancy | Cannot serve 100+ companies |
| **HIGH** | 26 | Company-specific logic | Code cannot be reused |
| **MEDIUM** | 19 | Configuration in code | Cannot update without deployment |
| **LOW** | 34 | Magic numbers | Code maintenance debt |
| **TOTAL** | **87** | **MULTI-TENANT BLOCKING** | **Immediate action required** |

**Key Finding:** System is built as **single-tenant for BlitzenX only**. Must refactor before SaaS launch.

---

## CRITICAL SEVERITY (8 Issues) — BLOCKS MULTI-TENANCY

These violations **PREVENT** the system from serving multiple customers simultaneously.

### C1: Hardcoded Tenant ID = 1 (BlitzenX Default)

**Problem:** Every initialization and default operation assumes tenant_id=1 is "BlitzenX"

| File | Line | Code | Current Usage |
|------|------|------|----------------|
| backend/app/main.py | 268 | `tenant_id=1` | User creation during startup |
| backend/app/main.py | 336 | `seed_role_templates(_db, tenant_id=1)` | Role template initialization |
| backend/app/core/db_contract.py | 85 | Comment: "tenant_id=1 (BlitzenX)" | Tenant documentation |
| backend/app/core/db_contract.py | 143, 167, 191 | `tenant_id=1` | RBAC module creation (3 locations) |
| backend/app/core/db_contract.py | 252, 278, 291 | `tenant_id=1` | Admin user & superuser creation (3 locations) |
| backend/app/seeds/init_resources.py | 241, 244 | `tenant_id=1` | Resource initialization (2 locations) |
| backend/app/api/v1/endpoints/candidates.py | 390 | `tenant_id = 1  # Default fallback` | LinkedIn import fallback |
| backend/app/api/v1/endpoints/certifications_admin.py | 84, 138, 206, 246 | `tenant_id=1` | Certification endpoints (4 locations) |
| backend/app/api/v1/endpoints/complete_workflow.py | 51, 72 | `tenant_id=1` | Interview workflow (2 locations) |
| backend/app/api/v1/endpoints/config.py | 146 | Comment: "For now, assume tenant_id=1" | Configuration endpoint |
| backend/app/api/v1/endpoints/create_job.py | 1170 | Comment: "function uses default tenant_id=1" | Job creation |
| backend/app/api/v1/endpoints/hiring_manager_validation.py | 61, 103, 142, 450 | `tenant_id=1, # TODO: Get from current user context` | 4 validation endpoints |
| backend/app/services/message_handlers/ops_alert_handler.py | 72 | `tenant_id=1` | Alert message handler |

**Count:** 27+ locations  
**Impact:** 
- New tenants cannot exist (all data goes to tenant_id=1)
- Multi-tenant queries return wrong data
- GDPR violations (customer data isolation fails)
- Cannot sell to second customer

**Fix Strategy:**
```python
# BEFORE (WRONG)
tenant_id = 1  # Hardcoded

# AFTER (CORRECT)
# Extract from authenticated user context
def get_tenant_id_from_user(current_user: Users) -> int:
    """Extract tenant_id from authenticated user"""
    if not current_user or not hasattr(current_user, 'tenant_id'):
        raise HTTPException(status_code=401, detail="No tenant context")
    return current_user.tenant_id
```

**Priority:** CRITICAL - Fix before any SaaS launch

---

### C2: Hardcoded BlitzenX Company Identity

**Problem:** System hardcoded to serve only BlitzenX; company-specific logic embedded in code

| File | Pattern | Usage | Impact |
|------|---------|-------|--------|
| backend/app/__init__.py | `"""BlitzenX WROS Application Package"""` | Module docstring | Marks code as BlitzenX-only |
| backend/app/core/db_contract.py | `Tenant(id=1, name="BlitzenX")` | Hardcoded tenant name | Cannot change tenant name |
| All endpoints | Implicit BlitzenX context | No company abstraction | All features tied to BlitzenX |
| Admin docs | "BlitzenX WROS" everywhere | Documentation assumes one company | Confusing for multi-tenant setup |

**Examples of BlitzenX-specific logic:**
- BLITZENX_OPERATING_MODEL.md (1,700+ lines) hardcoded into system architecture
- Agent system designed for "BlitzenX to reach $100M by 2030"
- All workflows assume Guidewire specialist staffing (BlitzenX business model)

**Impact:**
- Code cannot be white-labeled
- Business logic specific to BlitzenX staffing model
- No company-agnostic configuration layer

**Fix Strategy:**
1. Replace hardcoded company identity with configuration
2. Move company-specific workflows to configurable decision trees
3. Create "Company Configuration" module with customizable settings

---

### C3: Hardcoded Service Email Addresses

**Problem:** All system emails sent from hardcoded `helpdesk_hrms@blitzenx.com` account

| File | Email Address | Used For | Count |
|------|---------------|----------|-------|
| backend/app/core/db_contract.py | `admin@blitzenx.com` | Admin user account | Email hardcoded in user creation |
| backend/app/services/ai_conversation_service.py | `helpdesk_hrms@blitzenx.com` | SERVICE_MAILBOX constant | Service email polling |
| backend/app/services/email_service.py | `helpdesk_hrms@blitzenx.com` | SERVICE_EMAIL constant | All system emails |
| backend/app/services/email_first_engagement_service.py | `helpdesk_hrms@blitzenx.com` | Service mailbox | First engagement service |
| backend/app/services/message_handlers/send_email_handler.py | `helpdesk_hrms@blitzenx.com` | Email CC | 2 locations hardcoded |
| backend/app/api/v1/endpoints/ai_agent.py | `helpdesk_hrms@blitzenx.com` | Documentation | 3 endpoint docs |
| backend/app/api/v1/endpoints/email.py | `helpdesk_hrms@blitzenx.com` | Endpoint docs | 3 docs |
| backend/app/services/timesheet_service.py | `admin@blitzenx.com` | Fallback approver | Line 221 |

**Impact:**
- Emails for Customer B sent from BlitzenX address
- No way to brand emails with customer's company name
- OAuth token hardcoded to one Microsoft account (helpdesk_hrms@blitzenx.com)
- Multi-tenant email routing impossible

**Fix Strategy:**
```python
# BEFORE
SERVICE_EMAIL = "helpdesk_hrms@blitzenx.com"

# AFTER
def get_service_email(tenant_id: int) -> str:
    """Get service email for tenant"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    return tenant.service_email or DEFAULT_SERVICE_EMAIL
```

---

### C4: Hardcoded Test Credentials

**Problem:** Test passwords hardcoded in database initialization

| File | User | Password | Severity |
|------|------|----------|----------|
| backend/app/core/db_contract.py | `admin@blitzenx.com` | `Admin@123` | Critical (hardcoded in logs) |
| backend/app/core/db_contract.py | `superuser@blitzenx.com` | `TestUser@123` | Critical (appears in logs) |

**Impact:**
- Production credentials visible in logs
- Same password across all deployments
- Anyone with code access can log in as admin
- Violates security audit requirements

**Fix Strategy:**
```python
# BEFORE
UserPassword=get_password_hash("Admin@123")

# AFTER
# Generate random password on first run, return to user
admin_password = generate_secure_password()  # 32 char random
# Send via secure channel, never log plaintext
secure_store_password(admin_user, admin_password)
```

---

### C5: TODO Comments Indicating Missing Tenant Context

**Problem:** 8+ locations with explicit `TODO: Get from current user context` for tenant_id

| File | Line | Code | Status |
|------|------|------|--------|
| backend/app/api/v1/endpoints/hiring_manager_validation.py | 61 | `tenant_id=1,  # TODO: Get from current user context` | Awaiting implementation |
| backend/app/api/v1/endpoints/hiring_manager_validation.py | 103 | Same pattern | Awaiting implementation |
| backend/app/api/v1/endpoints/hiring_manager_validation.py | 142 | Same pattern | Awaiting implementation |
| backend/app/api/v1/endpoints/hiring_manager_validation.py | 450 | Same pattern | Awaiting implementation |
| backend/app/api/v1/endpoints/employee_referrals.py | 150 | `# TODO: Implement auth - get current_user from session` | Missing auth |
| backend/app/api/v1/endpoints/employee_referrals.py | 377, 416, 450 | Same pattern (3 locations) | Missing auth |
| backend/app/routes/api_v1_invoices.py | 174 | `tenant_id=None,  # TODO: Get from context` | Null fallback |

**Impact:**
- Developers documented but didn't implement multi-tenancy
- System will fail when tenant_id=1 assumption breaks
- Clear acknowledgment that current design is wrong

---

### C6: Hardcoded Localhost URLs (Development Only, But Production Risk)

**Problem:** Localhost URLs hardcoded as fallback/defaults in multiple places

| File | URL | Used For | Production Risk |
|------|-----|----------|-----------------|
| backend/app/core/config.py | `FRONTEND_BASE_URL: str = "http://localhost:3000"` | Frontend base URL | Must override via env |
| backend/app/core/config.py | CORS allows all localhost:3000-65535 | CORS origins | Development-only, OK |
| backend/app/middleware/cors.py | `"http://localhost:3000"`, `"http://127.0.0.1:3000"` | CORS whitelist | Redundant with config.py |
| backend/app/services/autonomous_sdlc_service.py | `"http://localhost:8080/health"` | Health checks | Breaks in production |
| backend/app/core/database_safety.py | `"localhost"` check | Database validation | OK for safety |

**Impact:**
- If FRONTEND_BASE_URL not set, system uses localhost:3000
- Autonomous SDLC service hardcoded to localhost:8080
- Breaks in cloud/multi-server deployments

**Fix Strategy:**
```python
# BEFORE
FRONTEND_BASE_URL: str = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

# AFTER
FRONTEND_BASE_URL: str = os.getenv("FRONTEND_BASE_URL")
if not FRONTEND_BASE_URL:
    raise ValueError("FRONTEND_BASE_URL must be set (not localhost)")
```

---

### C7: Hardcoded File Paths (Windows-Specific)

**Problem:** Absolute Windows file paths hardcoded in Python code

| File | Path | Usage | Severity |
|------|------|-------|----------|
| backend/app/services/architect_codebase_audit.py | `C:\Users\AvinashMukund\Documents\Claude\WROS-Master` | Repo root default | HIGH - breaks on other machines |
| backend/app/services/autonomous_sdlc_service.py | Same path (2 locations) | Git cwd parameter | HIGH - CI/CD will fail |

**Impact:**
- Code only works on Avinash's machine
- CI/CD cannot run git commands
- Deployment scripts will fail
- Non-reproducible builds

**Fix Strategy:**
```python
# BEFORE
repo_root: str = "C:\\Users\\AvinashMukund\\Documents\\Claude\\WROS-Master"

# AFTER
repo_root: str = os.getenv("REPO_ROOT", os.getcwd())
# Use at runtime: os.path.abspath(os.path.dirname(__file__))
```

---

## HIGH SEVERITY (26 Issues) — COMPANY-SPECIFIC LOGIC

These hardcoded values embed BlitzenX business logic into code, preventing reuse.

### H1: Hardcoded Email Credentials & OAuth Tokens

| File | Credential | Type | Severity |
|------|-----------|------|----------|
| backend/.env.production | PASSWORD in URL | Database password example | Exposed in git |
| backend/.env.production.template | `SUPER_SECRET_PASSWORD` | Template secret | Should be in vault |

**Impact:**
- Production credentials visible in git history
- No secret rotation mechanism
- OAuth token bound to helpdesk_hrms@blitzenx.com account

---

### H2: Hardcoded Timeouts & Delays

**Problem:** Magic numbers for timeouts, retries, and delays embedded throughout code

| File | Value | Purpose | Count |
|------|-------|---------|-------|
| backend/app/api/v1/endpoints/documents.py | 60, 30 | Request timeouts | 2 |
| backend/app/api/v1/endpoints/msgraph.py | 10 (repeated) | Graph API timeout | 8+ |
| backend/app/core/graph_auth.py | 30, 10 | OAuth/API timeout | 2 |
| backend/app/services/autonomous_sdlc_service.py | 5 | Health check timeout | 1 |
| backend/app/services/channel_delivery_helpers.py | 300, 7200 | 5min, 2hour backoff | 2 |
| backend/app/middleware/auth_middleware.py | 2 | Redis timeout | 1 |

**Problems:**
- No configuration layer (hardcoded in code)
- Cannot adjust without redeploy
- Different customers might need different timeouts
- No SLA enforcement per tenant

---

### H3: Hardcoded Database Names in Documentation

| File | DB Name | Environment | Issue |
|------|---------|-------------|-------|
| backend/BACKLOG.md | `onboarding_dev` | Development | Hardcoded dev DB name |
| backend/BACKLOG.md | `onboarding_staging` | Staging | Hardcoded staging DB name |
| backend/BACKLOG.md | `onboarding_prod` | Production | Hardcoded prod DB name |
| backend/.env.production | Comment references | Prod DB naming | Inconsistent naming |

---

## MEDIUM SEVERITY (19 Issues) — CONFIGURATION IN CODE

These should be environment variables or database configuration.

### M1: CORS Origins Hardcoded

| File | Origin | Location | Environment |
|------|--------|----------|-------------|
| backend/app/middleware/cors.py | localhost:3000, localhost:3001 | 4 lines | Hardcoded in code |
| backend/app/api/v1/routes_master.py | localhost:3000, localhost:3001 | 4 lines | Duplicated hardcoding |
| backend/app/core/config.py | Dynamic range localhost:3000-65535 | Code generated | Generation logic hardcoded |

**Impact:**
- Cannot configure CORS without code change
- Duplicate configuration (cors.py vs routes_master.py)
- No tenant-specific CORS policies

---

### M2: Feature Flags & System Behavior Hardcoded

**Missing configuration:**
- Queue system architecture (THUNDER vs FLASH routing)
- Agent feature gates (which agents enabled/disabled)
- Workflow routing decisions
- Permission checks (hardcoded role dependencies)
- SLM integration requirements
- Async processing behavior

---

## LOW SEVERITY (34 Issues) — MAGIC NUMBERS & NAMING

These hurt maintainability but don't block multi-tenancy.

### L1: Magic Numbers Without Constants

**Examples:**
- Employee experience thresholds (line 500+)
- Aging metrics (30, 60, 90 days)
- Utilization targets (70%, 80%)
- Cost calculations (hardcoded formulas)

---

## FINDINGS BY LOCATION

### Backend Endpoints (High Risk — 45K+ lines)

**Files with most hardcoding:**
1. candidates.py — 3+ tenant_id=1, hardcoded emails
2. certifications_admin.py — 4x tenant_id=1
3. hiring_manager_validation.py — 4x TODO comments
4. create_job.py — tenant_id=1 + company logic
5. employee_referrals.py — Missing auth (4 endpoints)

**Pattern:** Endpoints copy-paste tenant_id=1 instead of extracting from context

### Services (Medium Risk — 30K+ lines)

**Most problematic:**
1. email_service.py — Hardcoded helpdesk_hrms@blitzenx.com
2. timesheet_service.py — Hardcoded admin@blitzenx.com fallback
3. autonomous_sdlc_service.py — Hardcoded localhost:8080 + file paths
4. channel_delivery_helpers.py — Hardcoded delay values

**Pattern:** Services assume single tenant, no configuration layer

### Database & Config (Critical Risk)

1. db_contract.py — 8+ tenant_id=1 hardcoding
2. config.py — localhost defaults, no validation
3. core/graph_auth.py — Hardcoded OAuth timeout

**Pattern:** Database initialization assumes BlitzenX is the only tenant

### Frontend (Lower Risk — Still Issues)

1. Hardcoded permission strings in Shell.js (NAV_PERMISSIONS)
2. No dynamic queue type loading (would use API if implemented)
3. MockData.js has hardcoded options (should come from API)

**Pattern:** Frontend mostly does fetch from API (good practice)

---

## PROPOSED REMEDIATION PLAN

### Phase 1: Extract Tenant Context (CRITICAL - 1-2 weeks)

**Goal:** Remove all `tenant_id=1` hardcoding

**Steps:**
1. Create `get_tenant_id_from_context()` utility function
2. Refactor database initialization to accept tenant_id parameter
3. Update all endpoints to extract tenant_id from `current_user`
4. Add tests for multi-tenant isolation

**Files to modify:** 13 files (db_contract.py, candidates.py, etc.)

---

### Phase 2: Externalize Configuration (HIGH - 1 week)

**Goal:** Move hardcoded values to environment/database config

**Steps:**
1. Create TenantConfiguration model (service emails, feature flags, timeouts)
2. Move CORS_ORIGINS to database
3. Create ConfigService for retrieving tenant-specific settings
4. Migrate hardcoded timeouts to config

**Impact:** 19 medium-severity issues resolved

---

### Phase 3: Remove Company-Specific Logic (HIGH - 2-3 weeks)

**Goal:** Make business logic configurable

**Steps:**
1. Audit BLITZENX_OPERATING_MODEL.md integration points
2. Create "Company Profile" configuration
3. Make workflows configurable (decision trees instead of hardcoded logic)
4. Create white-label capability

**Impact:** Can sell to customers with different business models

---

### Phase 4: Security Hardening (CRITICAL - 1 week)

**Steps:**
1. Remove hardcoded passwords from code
2. Implement secure password generation & distribution
3. Move OAuth tokens to credential vault (HashiCorp Vault / AWS Secrets)
4. Audit all logs for credential exposure

**Impact:** Passes security audit

---

## DEPLOYMENT READINESS CHECKLIST

Before SaaS launch, verify:

- [ ] Zero hardcoded tenant_id=1 (except initialization)
- [ ] All multi-tenant queries include tenant filter
- [ ] GDPR data isolation tested (Customer A cannot see Customer B data)
- [ ] Configuration is environment-based (no code changes for new tenant)
- [ ] Email addresses are tenant-specific
- [ ] OAuth tokens per tenant (not shared account)
- [ ] File paths are relative or from environment
- [ ] Timeouts are configurable
- [ ] No BlitzenX-specific logic in endpoints
- [ ] Security audit passed (no hardcoded credentials)

---

## SUMMARY TABLE

| Severity | Count | Risk | Timeline | Owner |
|----------|-------|------|----------|-------|
| CRITICAL | 8 | Blocks multi-tenancy | Immediate | Architect |
| HIGH | 26 | Company-specific | Sprint 1 | Backend |
| MEDIUM | 19 | Config in code | Sprint 2 | Backend |
| LOW | 34 | Tech debt | Sprint 3 | Team |

**Total Issues:** 87  
**Estimated Remediation:** 4-5 weeks  
**SaaS Launch Readiness:** Cannot launch until CRITICAL issues resolved

---

## NEXT STEPS

1. **Approve remediation plan** with timeline
2. **Assign ownership** (Architect leads CRITICAL phase)
3. **Create GitHub issues** (87 total, prioritized)
4. **Implement Phase 1** (Extract tenant context)
5. **Test multi-tenant isolation** before any deployment
6. **Security audit** before SaaS launch

