# Queue Handler Validation + Timeout Solution - START HERE

**Date:** 2026-09-12  
**Status:** 🚨 CRITICAL - Production blocker - Ready for implementation  
**Requirement:** Validation patterns + time-bound execution  
**Coordinator:** Added timeout requirement during architecture phase

---

## THE PROBLEM (Two Critical Issues)

### Issue 1: Silent Failures
- Handlers mark COMPLETED without verifying work happened
- Example: create_candidate returns HTTP 200 but candidate never inserted
- Example: engage_candidate shows COMPLETED but messages never delivered
- System **appears to work** but cascade fails 15-30 minutes later

### Issue 2: Infinite Hangs  
- Handlers can wait indefinitely on slow database/API
- Example: Database lock causes handler to hang forever
- Queue processor threads exhausted, entire system hangs
- One slow handler blocks all other queue processing

---

## THE SOLUTION (Two-Part Fix)

### Part 1: Validation Pattern
Before marking COMPLETED, handlers MUST:
1. ✅ Verify result structure (required fields exist)
2. ✅ Query database (record actually exists)
3. ✅ Check related records (FKs, status, etc.)
4. ✅ Verify data integrity (fields match payload)

If ANY check fails → Raise exception → Retry or escalate

### Part 2: Time-Bound Execution
All handlers MUST:
1. ✅ Start timeout clock (30-60 seconds depending on handler)
2. ✅ Complete work within timeout
3. ✅ Complete validation within timeout
4. ✅ If timeout expires → FAIL immediately (no indefinite waits)

---

## DOCUMENTATION - READ IN THIS ORDER

### 1. QUEUE_HANDLER_COMPLETE_SOLUTION.md (READ FIRST - 30 min)
- What's broken and why
- How validation + timeouts work together
- Complete handler implementation with both
- Scenario walkthroughs (what happens in different cases)
- START HERE if you want the big picture

### 2. handler_validation_template.py (REFERENCE - 10 min)
- Copy-paste ready reference implementation
- Shows exact pattern for all 4 methods (process, on_success, on_retry, on_failed)
- All 4 validation steps with logging
- All timeout checks
- Use this as your template when updating handlers

### 3. QUEUE_HANDLER_VALIDATION_PATTERN.md (REFERENCE - 20 min)
- Detailed validation patterns by handler type
- Validation checklist for each handler
- Error handling strategy (retryable vs non-retryable)
- Testing strategy
- Use when you need detailed guidance on validation logic

### 4. QUEUE_HANDLER_TIMEOUTS_CRITICAL.md (REFERENCE - 20 min)
- Detailed timeout architecture
- Timeout config by handler (30s, 60s, 45s, 40s)
- Queue processor integration
- Monitoring + alerting
- Use when you need detailed guidance on timeout enforcement

### 5. IMPLEMENTATION_CHECKLIST.md (REFERENCE - 10 min)
- Phase 1 checklist (4 Priority 1 handlers)
- Step-by-step implementation instructions
- Testing checklist
- Timeline and resource allocation
- Use as your implementation roadmap

---

## PRIORITY 1 HANDLERS (THIS WEEK - 4 Handlers)

### Handler 1: CREATE_CANDIDATE
- **Timeout:** 30 seconds
- **File:** backend/app/services/message_handlers/candidate_creation_handler.py
- **Validation:** candidate exists, status created, email matches, tenant correct
- **Test:** Happy path + record not found + timeout

### Handler 2: ENGAGE_CANDIDATE_WITH_THUNDER
- **Timeout:** 60 seconds (external API)
- **File:** backend/app/services/message_handlers/candidate_creation_handler.py:on_success()
- **Validation:** delivery logged, status='sent', conversation created, candidate exists
- **Test:** Happy path + delivery failed + timeout

### Handler 3: JOB_CREATED_FLASH
- **Timeout:** 45 seconds
- **File:** Job handler (Flash service)
- **Validation:** job exists, hiring manager FK valid, BU matches
- **Test:** Happy path + FK broken + timeout

### Handler 4: CANDIDATE_CONVERSION_HANDLER
- **Timeout:** 40 seconds
- **File:** backend/app/services/message_handlers/candidate_conversion_handler.py
- **Validation:** employee exists, candidate status=EMPLOYEE, emails match
- **Test:** Happy path + email mismatch + timeout

---

## QUICK START (1 Hour)

### For Architecture Review:
1. Read QUEUE_HANDLER_COMPLETE_SOLUTION.md (30 min)
2. Review handler template handler_validation_template.py (10 min)
3. Check implementation timeline in IMPLEMENTATION_CHECKLIST.md (10 min)
4. Approve architecture (10 min)

### For Development Start:
1. Read QUEUE_HANDLER_COMPLETE_SOLUTION.md (30 min)
2. Copy handler_validation_template.py as starting point (5 min)
3. Follow checklist in IMPLEMENTATION_CHECKLIST.md for your assigned handler (5 min)
4. Reference detailed guides as needed during implementation

---

## FILES CREATED (Complete Solution)

### Documentation (4 guides, 7,500 lines)
1. QUEUE_HANDLER_VALIDATION_PATTERN.md - Validation guide (2,500 lines)
2. QUEUE_HANDLER_TIMEOUTS_CRITICAL.md - Timeout guide (2,000 lines)
3. QUEUE_HANDLER_COMPLETE_SOLUTION.md - Integrated solution (1,500 lines)
4. IMPLEMENTATION_CHECKLIST.md - Checklist + timeline (800 lines)

### Code Reference
5. handler_validation_template.py - Reference implementation (400 lines)

### Configuration
6. handlers_timeout_config.yaml - Timeout values (TO CREATE: 50 lines)

---

## KEY PRINCIPLES

### Validation
- NEVER mark COMPLETED without database verification
- Must query database to confirm work actually persisted
- Must validate related records exist (FKs, status, etc.)
- Must detect data corruption (field mismatches)

### Timeouts
- EVERY handler has a time limit (30-60 seconds)
- Work + validation must complete within limit
- If timeout expires → FAIL immediately (no indefinite waits)
- Fail fast, retry later with exponential backoff

### Error Handling
- ValueError (non-retryable): Handler code bug → FAILED, no retry
- RuntimeError (retryable): Temporary DB issue → Schedule retry
- TimeoutError: Timeout exceeded → Schedule retry with backoff

---

## BEFORE vs AFTER

### Before (Broken)
```
User submits form → HTTP 200 "Success"
Message shown as COMPLETED (✓)
30 minutes later → Record doesn't exist (✗)
Team can't debug (looked successful!)
Cascade failures across system
```

### After (Fixed)
```
User submits form → HTTP 200 "Success"
Handler validates work in database
Message marked COMPLETED (with proof!)
30 minutes later → Record definitely exists (✓)
Team confident in COMPLETED status
No cascade failures
```

---

## IMPLEMENTATION TIMELINE

**This Week (2026-09-12 to 2026-09-18):**
- Day 1: Architecture review (done!)
- Days 2-3: Developers implement 4 Priority 1 handlers (parallel)
- Day 4-5: Testing + code review
- Day 6: Final verification + merge to main

**Next Week:**
- Phase 2: Priority 2 handlers (interview, offer, etc.)

**Following Week:**
- Phase 3: Production enforcement + monitoring

---

## NEXT STEPS

1. **Architect**: Review QUEUE_HANDLER_COMPLETE_SOLUTION.md (30 min)
2. **Architect**: Approve architecture and timeline
3. **Team Lead**: Assign 2 developers (parallel work)
   - Dev 1: create_candidate + job_created_flash
   - Dev 2: engage_candidate + candidate_conversion
4. **Developers**: Start from QUEUE_HANDLER_COMPLETE_SOLUTION.md → handler_validation_template.py → IMPLEMENTATION_CHECKLIST.md
5. **QA**: Follow testing checklist in IMPLEMENTATION_CHECKLIST.md

---

## WHAT YOU'LL GET

✓ **Zero silent failures** - COMPLETED status = work verified in database  
✓ **No system hangs** - All handlers have timeouts, fail fast  
✓ **Automatic retries** - Failed tasks retry with exponential backoff  
✓ **Monitoring** - Track timeouts, validation failures, retry rates  
✓ **Alerting** - Know when handlers are slow or failing  
✓ **Production ready** - Robust queue processing with validation + timeouts

---

## QUESTIONS?

- **What's the validation pattern?** → Read QUEUE_HANDLER_COMPLETE_SOLUTION.md
- **How do timeouts work?** → Read QUEUE_HANDLER_TIMEOUTS_CRITICAL.md
- **How do I implement this?** → Follow IMPLEMENTATION_CHECKLIST.md
- **What's the exact code?** → Copy handler_validation_template.py
- **What validation for my handler?** → Check QUEUE_HANDLER_VALIDATION_PATTERN.md

---

## CRITICAL REMINDERS

🚨 **NEVER commit handler without:**
- Timeout config (TIMEOUT_SECONDS)
- Validation in on_success() (4 checks)
- Timeout checks in process()
- Tests for all scenarios

🚨 **ALWAYS verify:**
- Result has required fields
- Record exists in database
- Related records are consistent
- No timeout exceeded

---

**Ready to implement? Start with QUEUE_HANDLER_COMPLETE_SOLUTION.md**
