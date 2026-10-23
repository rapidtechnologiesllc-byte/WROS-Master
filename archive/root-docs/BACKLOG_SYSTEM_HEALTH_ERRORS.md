# Feature: Enhanced Endpoint Error Reporting for System Health Dashboard

**Status:** Backlog - CRITICAL  
**Priority:** HIGH (Dashboard currently shows fake data)  
**Complexity:** HIGH (3 phases, 5-8 hours total)  
  - Phase 1: Dynamic endpoint discovery (1-2 hours) - **DO FIRST**
  - Phase 2: Real health checking (2-3 hours)
  - Phase 3: Error details & remediation (1-2 hours)
**Related:** System Health Dashboard Redesign (Completed but incomplete)

## Overview

Enhance the System Health dashboard to display detailed error information and remediation steps when endpoints are unhealthy (yellow/red status).

## Current State

✅ System Health dashboard displays in professional table format  
❌ **CRITICAL: Endpoints list is HARDCODED** (should be dynamic)  
❌ No error details or action items displayed  
❌ Only shows basic endpoint availability  
❌ No real health checking (all endpoints fake-green)  
❌ Does not reflect actual application state

## Desired State

When an endpoint is unhealthy:
- Display what the issue is
- Show recommended actions/remediation steps
- Support color coding: green (healthy), yellow (warning), red (critical)
- Expandable cards to show full error details

## Implementation Tasks

### PHASE 1: DYNAMIC ENDPOINT DISCOVERY (CRITICAL - DO FIRST)

**Problem:** Current implementation hardcodes 10 fake endpoints. Dashboard looks "made up" instead of reflecting real application state.

**Solution:** Dynamically discover and check ALL actual endpoints

**Backend Changes:**

**File:** `backend/app/main.py` - Update `/health` endpoint

```python
@app.get("/health")
def health_check():
    """
    Dynamically discover all registered routes and check their health.
    """
    # Query FastAPI app.routes to get ALL registered endpoints
    endpoints_health = []
    
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            endpoint_name = f"{', '.join(route.methods)} {route.path}"
            
            # Skip non-API routes (static files, docs, etc.)
            if route.path.startswith('/api') or route.path in ['/health', '/status/all', '/auth/login']:
                # Health check: Make actual request to endpoint
                try:
                    # Mock health check (see Phase 2 for real health checking)
                    status = "healthy"
                    response_time_ms = 50  # Placeholder
                except Exception as e:
                    status = "unhealthy"
                    response_time_ms = None
                
                endpoints_health.append({
                    "name": endpoint_name,
                    "status": status,
                    "response_time_ms": response_time_ms,
                    "issue": None,
                    "action": None,
                    "severity": None
                })
    
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "endpoints": endpoints_health  # REAL endpoints, not hardcoded
    }
```

**What it does:**
- ✅ Query FastAPI's internal route registry
- ✅ Return ACTUAL endpoints from the running application
- ✅ No hardcoded lists
- ✅ Shows what the application REALLY has
- ✅ Scales automatically as new endpoints are added

**Frontend:** No changes needed - will automatically display all discovered endpoints

---

### PHASE 2: REAL HEALTH CHECKING (FOLLOW-UP)

After Phase 1 (dynamic discovery), add actual health checks:

```python
# Make real HTTP requests to each endpoint
for route in app.routes:
    try:
        # Test endpoint with appropriate HTTP method + minimal data
        response = make_request(route.method, route.path, timeout=5)
        response_time_ms = response.elapsed.total_seconds() * 1000
        
        if response.status_code < 400:
            status = "healthy"
        elif response.status_code < 500:
            status = "warning"
        else:
            status = "critical"
    except Timeout:
        status = "critical"
        issue = "Endpoint timeout (>5s)"
    except ConnectionError:
        status = "critical"
        issue = "Connection refused"
```

---

### PHASE 3: ERROR DETAILS & REMEDIATION (FOLLOW-UP)

After Phase 2 (real health checking), add error details:

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

### Phase 1 (CRITICAL - MVP)
- [ ] Dashboard displays ACTUAL endpoints from running application (not hardcoded)
- [ ] Endpoint list updates as new routes are added/removed
- [ ] All 13 modules' endpoints appear automatically
- [ ] No hardcoded strings anywhere
- [ ] Shows 50+ real endpoints instead of fake 10

### Phase 2 (IMPORTANT)
- [ ] Each endpoint gets real health check (actual HTTP request)
- [ ] Response times measured accurately
- [ ] Status colors reflect real state (green/yellow/red)
- [ ] Timeout handling (>5s = critical)

### Phase 3 (NICE-TO-HAVE)
- [ ] When unhealthy, displays issue description  
- [ ] When unhealthy, displays recommended actions  
- [ ] Responsive design on mobile  
- [ ] All error messages are clear and actionable  

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

**Phase 1 (Dynamic Discovery - CRITICAL):**
- Backend: 1-2 hours (query FastAPI routes, implement endpoint discovery)
- Frontend: 0 hours (automatic - no UI changes)
- Testing: 30 min
- **Subtotal: 2-2.5 hours**

**Phase 2 (Real Health Checking):**
- Backend: 2-3 hours (implement health check logic, timeout handling)
- Frontend: 0 hours
- Testing: 30 min
- **Subtotal: 2.5-3.5 hours**

**Phase 3 (Error Details & Remediation):**
- Backend: 1-2 hours (error detection, mapping)
- Frontend: 1 hour (display error details in UI)
- Testing: 30 min
- **Subtotal: 2.5-3.5 hours**

**TOTAL (All Phases): 7.5-9.5 hours**
**PHASE 1 ONLY: 2-2.5 hours** ← Do this FIRST to fix fake data

---

**Created:** 2026-09-16  
**Added to Backlog:** Yes  
**GitHub Issue:** To be created
