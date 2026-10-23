# Backlog: Orphaned Endpoint Files

**Issue:** 26 endpoint files exist in the codebase but are NOT registered in `app/api/v1/routes.py`. This causes:
- Frontend UI screens try to call these endpoints and get 404 errors
- Dead code takes up maintenance burden
- Confusing for developers (endpoint looks complete but doesn't run)

## Status
- **Total endpoint files:** 140
- **Registered (active):** 114
- **Orphaned (dead):** 26

## Orphaned Files (26 total)

| File | Status | Action |
|------|--------|--------|
| agent_config.py | ❌ Not registered | Activate or delete |
| bi_explorer.py | ❌ Not registered | Activate or delete |
| bu_head_dashboard.py | ❌ Not registered | Activate or delete |
| candidate_ranking.py | ❌ Not registered | Activate or delete |
| candidate_rejection.py | ❌ Not registered | Activate or delete |
| complete_workflow.py | ❌ Not registered | Activate or delete |
| conversions.py | ❌ Not registered | Activate or delete |
| crud.py | ❌ Not registered | Activate or delete |
| doctor_traces_dashboard.py | ❌ Not registered | Activate or delete |
| employee_conversion.py | ❌ Not registered | Activate or delete |
| hiring_manager_validation.py | ❌ Not registered | Activate or delete |
| interview_decision.py | ❌ Not registered | Activate or delete |
| invoices_s316.py | ❌ Not registered | Activate or delete |
| offers.py | ❌ Not registered | Activate or delete |
| onboarding_orchestrator.py | ❌ Not registered | Activate or delete |
| onboarding_workflow.py | ❌ Not registered | Activate or delete |
| queue.py | ❌ Not registered | Activate or delete |
| queue_dashboard.py | ❌ Not registered | Activate or delete |
| queues.py | ❌ Not registered | Activate or delete |
| resume_versions.py | ❌ Not registered | Activate or delete |
| revenue_recognition.py | ❌ Not registered | Activate or delete |
| spartan_forecasting.py | ❌ Not registered | Activate or delete |
| spartan_integration.py | ❌ Not registered | Activate or delete |
| strategic_consul.py | ❌ Not registered | Activate or delete |
| system_health.py | ❌ Not registered | Activate or delete |
| training_dashboards.py | ❌ Not registered | Activate or delete |

## For Each File, Decide:

**Option A: Delete** (if truly unused)
```bash
git rm backend/app/api/v1/endpoints/agent_config.py
git commit -m "remove: Delete orphaned endpoint file agent_config.py"
```

**Option B: Register** (if should be active)
```python
# In backend/app/api/v1/routes.py
from app.api.v1.endpoints.agent_config import router as agent_config_router
router.include_router(agent_config_router)
```

**Option C: Archive** (if might need later)
```bash
mkdir -p backend/backlog/endpoints
git mv backend/app/api/v1/endpoints/agent_config.py backend/backlog/endpoints/
git commit -m "archive: Move orphaned endpoint to backlog"
```

## Related Issue
This explains why frontend UI screens show 404 errors - they're trying to call endpoints that don't exist or aren't registered in the app.

**Scanner Output:**
```
Total endpoint files: 140
Registered in app: 114
Orphaned (not registered): 26
```

## Action Items
- [ ] Review each file and decide: Delete, Register, or Archive
- [ ] Update code gate to warn about orphaned files
- [ ] Coordinate with frontend team on which screens need these endpoints
- [ ] Clean up routes.py if needed
