# PHASE A EXECUTION TEMPLATE (Ready to Execute)

This file will be populated with the architect's battle plan once it arrives.

## Status: Awaiting Architect Execution Plan

Architect agent is determining:
1. ✅ Optimal execution sequence (sequential/parallel/bundled)
2. ✅ Time allocation per fix (5 fixes in 4-5 hours)
3. ✅ Acceptance criteria per fix (what proves "done")
4. ✅ Go-live criteria (when to say MVP is working)
5. ✅ Autonomy boundaries (what needs human approval)
6. ✅ Detailed timeline with checkpoints

## Fixes Being Planned

### F1: Database Columns Migration
**Current:** Models define columns, database doesn't have them
**Blocker:** First message processed → AttributeError → system crashes
**Files:** 
- `backend/app/core/database.py` (startup)
- `backend/migrations/20260910_cycle19_queue_columns.py` (NEW)
- `backend/app/services/queue_processor_service.py` (line 259 - add graceful handling)

### F2: Interview Scheduling Handler
**Current:** Handler exists but only pauses Thunder, doesn't schedule
**Blocker:** Candidates reach interview stage, system can't schedule
**Files:**
- `backend/app/services/message_handlers/interview_schedule_from_queue_handler.py` (NEW)
- `backend/app/api/v1/endpoints/interviews.py` (modify create_interview to queue)
- `backend/app/services/message_handler_registry.py` (register handler)

### F3: Offer Generation Handler
**Current:** Handler is 3.3KB stub, doesn't generate offers
**Blocker:** Approved candidates get no offer letter
**Files:**
- `backend/app/services/message_handlers/offer_generation_handler.py` (NEW)
- `backend/app/services/message_handler_registry.py` (register)

### F4: HR Onboarding Kickoff
**Current:** Accepted offers don't trigger onboarding workflow
**Blocker:** Accepted candidates disappear, no onboarding starts
**Files:**
- `backend/app/services/message_handlers/offer_accepted_onboarding_handler.py` (modify)
- `backend/app/services/message_handler_registry.py` (register if new)

### F5: Circuit Breaker Recovery
**Current:** 3 failures → stalls forever, no recovery
**Blocker:** Brief DB issue = total recruitment halt
**Files:**
- `backend/app/services/queue_processor_service.py:207-224` (modify thresholds + add recovery)

---

## Execution Flow (To Be Populated by Architect)

```
[ARCHITECT PLAN WILL FILL THIS IN]

Sequence: F1 → F2 → F3 → F4 → F5 (or optimal order per architect)
Parallelization: [which can run together]
Time per fix: [hours each]
Checkpoints: [when to reassess]
Go-live criteria: [exact conditions]
```

---

## Ready to Execute

All infrastructure prepared:
- ✅ Test suite created (`test_e2e_candidate_job_interview_flow.py`)
- ✅ Code templates ready (handlers, migrations)
- ✅ Git setup for autonomous commits
- ✅ Code review gate active

**Waiting for:** Architect execution strategy

**Next step:** Architect provides plan → Execute per spec → End-to-end test → GO/NO-GO decision
