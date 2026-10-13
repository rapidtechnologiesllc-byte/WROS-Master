# POST-MVP LAUNCH FIXES - COMPREHENSIVE ROADMAP

**Launch Date:** 2026-09-17 11:59 PM (TONIGHT)  
**Remediation Period:** 4-5 weeks  
**Target:** Full multi-tenant SaaS-ready system

---

## 📋 WHAT'S DEFERRED TO POST-LAUNCH

### MVP (LAUNCHING TONIGHT) ✅
- Email delivery system with async queue
- Candidate creation with recruiter auto-assignment
- Business Unit assignment
- Thunder autonomous candidate engagement
- Queue monitoring and SLM integration
- Role-based RBAC system

### POST-MVP (4-5 WEEK REMEDIATION)
- **87 hardcoding violations** fixing multi-tenant support
- 27 instances of `tenant_id=1` hardcoding removal
- Service email externalization (helpdesk_hrms@blitzenx.com → dynamic)
- Business logic flexibility (Guidewire-specific → configurable)
- Credential management (vault integration)
- Windows file paths → cloud-ready paths
- Localhost URLs → environment-based configuration

---

## 📁 FOLDER STRUCTURE

```
post-go-live-fixes/
├── README.md (this file)
├── LAUNCH_NOTES.md
│
├── HARDCODING_AUDIT/
│   ├── 01_EXECUTIVE_SUMMARY.md (Stakeholder-facing overview)
│   ├── 02_COMPREHENSIVE_TECHNICAL.md (Developer reference with all 87 issues)
│   ├── 03_REMEDIATION_CHECKLIST.md (Day-to-day implementation guide)
│   └── TIMELINE.md (Sprint-by-sprint breakdown)
│
├── MULTI_TENANCY_REMEDIATION/
│   ├── Phase_1_Foundation.md (Weeks 1-2: tenant_id extraction, multi-tenant filters)
│   ├── Phase_2_Configuration.md (Week 3: externalize service emails, timeouts)
│   ├── Phase_3_Business_Logic.md (Weeks 4-5: remove Guidewire-specific code)
│   ├── Phase_4_Security.md (Week 6: credential vault, test credentials removal)
│   └── ARCHITECTURE_DECISIONS.md (Design patterns for multi-tenancy)
│
├── CANDIDATE_FEATURES/
│   ├── Recruiter_Assignment_System.md
│   └── Business_Unit_Assignment_System.md
│
├── DATABASE_SCHEMA/
│   └── Multi_Tenant_Isolation.md
│
└── DEPLOYMENT_GUIDE.md (Production deployment with multi-tenancy)
```

---

## 🎯 PRIORITY ORDER (4-5 WEEKS)

### Week 1-2: PHASE 1 - Multi-Tenant Foundation (BLOCKING)
**Why Critical:** Cannot add Customer 2 without this

**Deliverables:**
- ✅ Extract tenant_id from user context (not hardcoded)
- ✅ Remove all 27 instances of `tenant_id=1` hardcoding
- ✅ Add multi-tenant query filters to all database queries
- ✅ Remove Windows file paths (`C:\Users\...`)
- ✅ Create multi-tenant isolation tests
- ✅ Data isolation verification (no cross-tenant leaks)

**Risk if skipped:** Customer data leaks, GDPR violation, system collapse

---

### Week 3: PHASE 2 - Configuration Externalization
**Why Important:** Company-specific values in code

**Deliverables:**
- ✅ Create TenantConfiguration model
- ✅ Move service email to configuration (`helpdesk_hrms@blitzenx.com` → dynamic)
- ✅ Externalize timeouts, CORS, retry configs
- ✅ Remove hardcoded test credentials from code
- ✅ Environment-based configuration loading

**Risk if skipped:** Every customer sees BlitzenX branding, hardcoded configs break at scale

---

### Weeks 4-5: PHASE 3 - Business Logic Flexibility
**Why Important:** Code assumes Guidewire staffing model (BlitzenX only)

**Deliverables:**
- ✅ Remove Guidewire-specific business logic
- ✅ Create configurable workflow system
- ✅ Support multiple staffing models (Guidewire, general ATS, contract)
- ✅ Per-tenant feature flags
- ✅ Flexible permission system (not hardcoded to BlitzenX model)

**Risk if skipped:** Cannot sell to companies with different business models

---

### Week 6: PHASE 4 - Security Hardening
**Why Important:** Credentials exposed in code

**Deliverables:**
- ✅ Remove hardcoded credentials (Admin@123, TestUser@123)
- ✅ Vault integration (AWS Secrets Manager or HashiCorp Vault)
- ✅ Per-tenant credentials
- ✅ Remove localhost URLs from code
- ✅ Security audit pass

**Risk if skipped:** Credentials visible in logs, deployments, code review

---

## 📊 METRICS

| Metric | Current | Target |
|--------|---------|--------|
| Hardcoding Violations | 87 | 0 |
| SaaS Readiness | 1/10 | 10/10 |
| Multi-Tenant Support | ❌ Single-tenant | ✅ Full multi-tenant |
| Deployments Required | Per-customer | Single deployment |
| Customer Data Isolation | ❌ Not isolated | ✅ GDPR compliant |
| Config Flexibility | ❌ Hardcoded | ✅ Externalized |
| Business Model Support | ❌ Guidewire only | ✅ Configurable |

---

## 🚀 GETTING STARTED

1. **Read PHASE 1 details:** `MULTI_TENANCY_REMEDIATION/Phase_1_Foundation.md`
2. **Check the checklist:** `HARDCODING_AUDIT/03_REMEDIATION_CHECKLIST.md`
3. **Start with highest-impact files:** See `HARDCODING_AUDIT/02_COMPREHENSIVE_TECHNICAL.md`

---

## 📞 QUESTIONS?

- **What's in here?** → Read this README
- **How do we fix it?** → Check PHASE files
- **Where's the technical detail?** → `02_COMPREHENSIVE_TECHNICAL.md`
- **What do I do today?** → `03_REMEDIATION_CHECKLIST.md`

---

**Status:** 📋 Documentation complete, ready for post-launch execution  
**Last Updated:** 2026-09-17  
**Maintained by:** Architecture team
