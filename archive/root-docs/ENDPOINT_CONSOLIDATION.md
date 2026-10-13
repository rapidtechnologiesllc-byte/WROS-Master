# Endpoint Consolidation: Candidate Creation

**Date:** 2026-09-20  
**Architect Decision:** Consolidate duplicate candidate creation endpoints into single canonical endpoint  
**Status:** ✅ COMPLETE

## Summary

The system had two candidate creation endpoints performing identical operations. This was consolidated to **one canonical endpoint** to eliminate code duplication, confusion, and maintenance burden.

## Endpoints Affected

### Deleted (STALE)
- **Endpoint:** `POST /api/v1/candidate-form/`
- **File:** `backend/app/api/v1/endpoints/candidates.py` (line 654)
- **Permission:** `require_resource_permission("candidate-form", "create")`
- **Status:** Removed ❌
- **Last Commit:** 3e05d44d (before consolidation)

### Kept (CANONICAL)
- **Endpoint:** `POST /api/v1/candidates/`
- **File:** `backend/app/api/v1/endpoints/candidates/create_queue_first.py`
- **Permission:** `require_resource_permission("candidates", "create")`
- **Status:** Active ✅
- **Behavior:** Validates input → queues create_candidate message → returns message_id + polling endpoint

## Why Consolidation?

| Issue | Impact | Resolution |
|-------|--------|-----------|
| **Code Duplication** | Maintenance burden: same logic in two places | Deleted stale endpoint |
| **Permission Confusion** | Two different permission models ("candidate-form" vs "candidates") | Single model: `candidates:create` |
| **Single Source of Truth** | Changes must be applied twice or risk divergence | Now one endpoint to update |
| **Frontend Clarity** | Frontend already uses `/candidates/` only | Matches reality |
| **Architectural Debt** | Unclear which endpoint is authoritative | Explicitly documented as canonical |

## Migration Guide

### For API Clients

**Old Endpoint (NO LONGER WORKS):**
```bash
POST /api/v1/candidate-form/
{
  "candidate_email": "...",
  "candidate_first_name": "...",
  "candidate_last_name": "...",
  "candidate_mobile": "...",
  "candidate_source": "form_submission",
  "candidate_current_location": "..."
}
```

**New Endpoint (USE THIS):**
```bash
POST /api/v1/candidates/
{
  "email": "...",
  "first_name": "...",
  "last_name": "...",
  "mobile": "...",
  "source": "form_submission",
  "current_location": "..."
}
```

**Response (Same):**
```json
{
  "status": "queued",
  "message_id": "uuid-string",
  "polling_endpoint": "/api/v1/message-queue/status/{message_id}"
}
```

### For Frontend

No changes needed. Frontend already uses `POST /api/v1/candidates/`. Consolidation just removes dead code.

### For Permission Model

**Old:** `require_resource_permission("candidate-form", "create")`  
**New:** `require_resource_permission("candidates", "create")`

If you're checking permissions programmatically, update checks to use `"candidates"` resource name.

## Queue Behavior (Unchanged)

Both endpoints queued messages identically. The canonical endpoint continues:

1. Validates: email, first_name, last_name required
2. Queues: `create_candidate` task to Thunder queue
3. Returns: message_id for status polling
4. Handler: CandidateCreationHandler processes async with full record creation

## Database Impact

No schema changes. No data migrations needed. This is purely API-layer consolidation.

## Testing Checklist

- [x] Handler still receives queue messages correctly
- [x] Candidate creation flow end-to-end works
- [x] Permission checks enforced on canonical endpoint
- [x] Message ID correctly returned to frontend
- [x] Frontend confirmation modal displays message_id
- [x] No orphaned database records from stale endpoint

## Rollback Plan

If issues discovered:
1. Restore candidates.py from git (lines 654-691)
2. Re-register endpoint in routes.py if needed
3. Full commit rollback: `git revert [commit-hash]`

No data cleanup needed (no records were created via stale endpoint in production).

## References

- **Canonical Endpoint:** `backend/app/api/v1/endpoints/candidates/create_queue_first.py`
- **Handler:** `backend/app/services/message_handlers/candidate_creation_handler.py`
- **Queue Service:** `backend/app/services/message_queue_service.py`
- **Architect Decision:** Ruthless Architect Review 2026-09-20

---

**Consolidation Complete** ✅  
Single source of truth for candidate creation established.
