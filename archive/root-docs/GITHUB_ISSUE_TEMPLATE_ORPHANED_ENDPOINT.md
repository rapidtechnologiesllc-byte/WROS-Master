# GitHub Issue Template - Orphaned Endpoint

**Use this template to create individual issues for each of the 26 orphaned endpoints.**

---

## Title Template
```
Backlog: [FILENAME] endpoint - Not registered (orphaned code)
```

## Body Template (Copy-Paste for each endpoint)

```markdown
## Status: Orphaned / Not Registered

**File:** `backend/app/api/v1/endpoints/[FILENAME].py`

**Issue:** This endpoint file exists in the codebase but is NOT registered in `app/api/v1/routes.py`. 

This causes:
- Frontend screens trying to call it get 404 errors
- Dead code that appears complete but doesn't run
- Gate reports false positives for security issues

## Current Situation

The file exists:
- ✅ File: `backend/app/api/v1/endpoints/[FILENAME].py`
- ❌ Registered in routes.py: NO

## Decision Required

**Choose ONE option:**

### Option A: DELETE (if truly dead code)
This endpoint is no longer needed. Remove it entirely.

```bash
git rm backend/app/api/v1/endpoints/[FILENAME].py
git commit -m "remove: Delete orphaned endpoint [FILENAME]"
```

### Option B: REGISTER (if it should be active)
This endpoint is complete and should be active. Register it in routes.py.

**Steps:**
1. Open `backend/app/api/v1/routes.py`
2. Add import:
   ```python
   from app.api.v1.endpoints.[FILENAME] import router as [FILENAME]_router
   ```
3. Add router inclusion:
   ```python
   router.include_router([FILENAME]_router)
   ```
4. Test the endpoint is accessible
5. Coordinate with frontend team to connect UI

### Option C: ARCHIVE (if might need it later)
This endpoint might be needed in future. Move to backlog folder.

```bash
mkdir -p backend/backlog/endpoints
git mv backend/app/api/v1/endpoints/[FILENAME].py backend/backlog/endpoints/
git commit -m "archive: Move orphaned endpoint [FILENAME] to backlog"
```

## Related
- Parent Issue: #[NUMBER] - Clean up 26 orphaned endpoints
- Gate Accuracy Report: GATE_ACCURACY_REPORT.md
- Endpoint Audit: BACKLOG_ORPHANED_ENDPOINTS.md

## Labels
- `backlog`
- `backend`
- `cleanup`
- `orphaned-code`
```

---

## Files to Create Issues For (26 total)

Create one issue per file:

1. agent_config.py
2. bi_explorer.py
3. bu_head_dashboard.py
4. candidate_ranking.py
5. candidate_rejection.py
6. complete_workflow.py
7. conversions.py
8. crud.py
9. doctor_traces_dashboard.py
10. employee_conversion.py
11. hiring_manager_validation.py
12. interview_decision.py
13. invoices_s316.py
14. offers.py
15. onboarding_orchestrator.py
16. onboarding_workflow.py
17. queue.py
18. queue_dashboard.py
19. queues.py
20. resume_versions.py
21. revenue_recognition.py
22. spartan_forecasting.py
23. spartan_integration.py
24. strategic_consul.py
25. system_health.py
26. training_dashboards.py

## Quick Steps (for each file)

1. Go to GitHub repository Issues tab
2. Click "New Issue"
3. Title: `Backlog: [FILENAME] endpoint - Not registered (orphaned code)`
4. Body: Use template above, replace `[FILENAME]` with actual filename
5. Labels: Add `backlog`, `backend`, `cleanup`
6. Create Issue

## Bulk Create via gh CLI (if available)

```bash
for file in agent_config bi_explorer bu_head_dashboard candidate_ranking candidate_rejection complete_workflow conversions crud doctor_traces_dashboard employee_conversion hiring_manager_validation interview_decision invoices_s316 offers onboarding_orchestrator onboarding_workflow queue queue_dashboard queues resume_versions revenue_recognition spartan_forecasting spartan_integration strategic_consul system_health training_dashboards; do
  gh issue create --title "Backlog: $file endpoint - Not registered (orphaned code)" \
    --body "**File:** \`backend/app/api/v1/endpoints/$file.py\`

**Issue:** This endpoint file exists but is NOT registered in \`app/api/v1/routes.py\`.

**Decision Required:**
- [ ] Option A: DELETE (if truly dead)
- [ ] Option B: REGISTER (if should be active) 
- [ ] Option C: ARCHIVE (if backlog)

**Related:** Parent issue on orphaned endpoints cleanup" \
    --label "backlog,backend,cleanup,orphaned-code"
done
```

---

## Tracking Progress

After creating all issues:
- [ ] 26 issues created (1 per orphaned file)
- [ ] Team reviews and decides for each
- [ ] Delete the dead ones
- [ ] Register the active ones
- [ ] Archive the backlog ones
- [ ] Update gate to skip orphaned files
- [ ] Re-run scan to get accurate baseline

---

## Why This Matters

These 26 orphaned files cause:
- **Code Gate False Positives:** ~40% of security issues flagged are in dead code
- **Frontend 404 Errors:** UI screens try to call non-existent endpoints
- **Maintenance Burden:** Dead code adds to lines of code without value
- **Developer Confusion:** Endpoint looks complete but doesn't run

**Cleanup unblocks:**
- Accurate security scanning
- Cleaner codebase
- UI/Backend alignment
- Faster onboarding for new developers
