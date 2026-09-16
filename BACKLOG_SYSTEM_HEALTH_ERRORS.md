# Feature: Enhanced Endpoint Error Reporting for System Health Dashboard

**Status:** Backlog  
**Priority:** Medium  
**Complexity:** Medium (2-3 hours)  
**Related:** System Health Dashboard Redesign (Completed)

## Overview

Enhance the System Health dashboard to display detailed error information and remediation steps when endpoints are unhealthy (yellow/red status).

## Current State

✅ System Health dashboard shows endpoint status with green indicators  
❌ No error details or action items displayed  
❌ Only shows basic endpoint availability

## Desired State

When an endpoint is unhealthy:
- Display what the issue is
- Show recommended actions/remediation steps
- Support color coding: green (healthy), yellow (warning), red (critical)
- Expandable cards to show full error details

## Implementation Tasks

### Backend Changes

**File:** `backend/app/api/v1/endpoints/health.py`

Modify the `/health` endpoint to return detailed status information:

```python
{
  "status": "healthy",
  "app": "Onboarding Auth API",
  "version": "1.0.0",
  "endpoints": [
    {
      "name": "GET /health",
      "status": "healthy",
      "response_time_ms": 2,
      "issue": null,
      "action": null,
      "severity": null
    },
    {
      "name": "GET /status/all",
      "status": "unhealthy",
      "response_time_ms": null,
      "issue": "Database connection timeout after 30s",
      "action": "Check PostgreSQL service status: systemctl status postgresql. Verify DATABASE_URL is correct.",
      "severity": "critical"
    },
    {
      "name": "GET /onboarding/hr/get_all_candidates",
      "status": "warning",
      "response_time_ms": 5432,
      "issue": "Slow response time (5.4s) - query optimization needed",
      "action": "Check database indexes on candidates table. Run: ANALYZE candidates;",
      "severity": "high"
    }
  ]
}
```

**Status Values:**
- `healthy`: Green - endpoint responding normally
- `warning`: Yellow - endpoint responding but with issues/delays
- `critical`: Red - endpoint down or critical issues

**Severity Levels:**
- `critical`: Service unavailable, requires immediate action
- `high`: Significant degradation, fix soon
- `medium`: Minor performance issues
- `low`: Informational, no immediate action needed

### Frontend Changes

**File:** `frontend/src/screens/SystemHealth.js`

1. Parse and store endpoint health details
2. Update endpoint card rendering to conditionally display error info
3. Add expandable/collapsible sections for detailed issue info

Example card rendering:
```
┌─────────────────────────────────────────┐
│ ● GET /status/all                [RED] │
├─────────────────────────────────────────┤
│ Issue: Database connection timeout      │
│ Action: Check PostgreSQL service        │
│ Severity: Critical                      │
└─────────────────────────────────────────┘
```

**File:** `frontend/src/screens/SystemHealth.css`

Add styles for status states:
- `.endpoint-healthy`: Green indicator
- `.endpoint-warning`: Yellow indicator  
- `.endpoint-critical`: Red indicator
- `.endpoint-details`: Error info section
- `.severity-badge`: Color-coded severity badges

### Testing Checklist

- [ ] Backend returns proper error details for each status
- [ ] Frontend displays error info for unhealthy endpoints
- [ ] Color coding displays correctly (green/yellow/red)
- [ ] Action items are readable and actionable
- [ ] Responsive on mobile (single column)
- [ ] Test with mixed healthy/warning/critical endpoints
- [ ] Verify response times display correctly
- [ ] Test with null/empty error fields (healthy state)

## Acceptance Criteria

✅ System Health dashboard shows endpoint status indicators  
✅ When unhealthy, displays issue description  
✅ When unhealthy, displays recommended actions  
✅ Color coding: green/yellow/red based on severity  
✅ Responsive design on mobile  
✅ All error messages are clear and actionable  

## Notes

- Don't break existing /health endpoint usage
- Ensure backward compatibility
- Keep error messages concise but informative
- Consider adding response time metrics alongside status

## Related Issues

- System Health Dashboard Redesign (COMPLETED - 371d914f, af0115d9, 6c16e907)

## Files to Modify

- `backend/app/api/v1/endpoints/health.py` - Add error details
- `frontend/src/screens/SystemHealth.js` - Display error info
- `frontend/src/screens/SystemHealth.css` - Style error states
- `backend/app/main.py` - Update health check logic if needed

## Estimated Effort

- Backend: 1-1.5 hours
- Frontend: 1-1.5 hours  
- Testing: 30 minutes
- **Total: 2-3 hours**

---

**Created:** 2026-09-16  
**Added to Backlog:** Yes  
**GitHub Issue:** To be created
