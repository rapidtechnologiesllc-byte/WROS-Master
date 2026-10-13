# CYCLE 4: Queue-Driven Architecture Audit (CORRECTED)

## THE RULE (Non-Negotiable)

**NO endpoint writes directly to database.**

All writes must follow:
```
API Endpoint → Enqueue Message → Handler Processes → Handler writes DB + db.commit()
```

## Pattern: Replace Direct DB Writes

### WRONG (Current - Must Fix):
```python
@router.post("/endpoint")
def create_thing(request, db: Session):
    thing = Thing(...)
    db.add(thing)
    db.commit()  # ❌ WRONG - endpoint writes directly
    return thing
```

### RIGHT (Queue-Driven):
```python
@router.post("/endpoint")
def create_thing(request, db: Session):
    # Queue the message, don't write DB
    msg_id = MessageQueueService.enqueue(
        task_name="create_thing_flash",
        data={...}
    )
    return {"status": "queued", "message_id": msg_id}

# Handler processes asynchronously
def handle_create_thing(message, db: Session):
    thing = Thing(**message.payload)
    db.add(thing)
    db.commit()  # ✅ RIGHT - handler writes with explicit commit
    return {"status": "created"}
```

## Critical Endpoints to Audit

Search for patterns in:
- `backend/app/api/v1/endpoints/candidates/*.py` - candidate CRUD
- `backend/app/api/v1/endpoints/jobs/*.py` - job CRUD  
- `backend/app/api/v1/endpoints/timesheets.py` - timesheet CRUD
- `backend/app/api/v1/endpoints/interviews.py` - interview CRUD
- `backend/app/api/v1/endpoints/offers.py` - offer CRUD

Pattern to find:
```
db.add(...)
db.commit()
return response
```

If found in endpoint: MIGRATE to queue-driven pattern

## Why This Matters (Spartan)

Direct DB writes cause:
- ❌ No cascade detection (write completes before downstream validation)
- ❌ No formation integrity checks
- ❌ Hidden failures (DB succeeds but handler later fails)
- ❌ No queue tracing (disappeared into void)

Queue-driven allows:
- ✅ Handler cascade detection (check if result is viable)
- ✅ Formation health reporting (pass status back to Flash)
- ✅ Explicit db.commit() (no silent failures)
- ✅ Async processing (handlers can escalate if needed)

## CRITICAL RULE

**If queue handler doesn't exist: CREATE IT FIRST**

```
Do NOT: Write to DB directly because no handler exists
DO:    Create the handler, then queue the message

Pattern:
1. Identify: "API needs to write X to database"
2. Check: "Does a queue handler for X exist?"
3. If YES: Use queue
4. If NO: CREATE handler first, THEN use queue
```

## CYCLE 4 Task

1. Audit: Find endpoints with direct db.add() + db.commit()
2. Count: How many violations exist?
3. Plan: Queue name for each (create handlers if needed)
4. Next cycle: Migrate one endpoint family (candidates, jobs, etc.)

This is the ARCHITECTURAL FIX that Spartan pattern requires.

## Queue Handler Template

For ANY new DB operation:

```python
# File: app/services/message_handlers/thing_created_handler.py
def handle_thing_created(message: Any, db: Session) -> Dict[str, Any]:
    try:
        payload = message.payload or {}
        thing = Thing(**payload)
        db.add(thing)
        db.commit()  # ← Explicit commit in handler
        return {"status": "created", "id": thing.id}
    except Exception as e:
        db.rollback()
        raise

# File: app/services/message_handler_registry.py
# Add registration:
MessageHandlerRegistry.register("thing_created_flash", handle_thing_created)

# File: API endpoint
# Use queue, don't write directly:
MessageQueueService.enqueue(
    task_name="thing_created_flash",
    data={"...payload..."}
)
```

This is mandatory for ALL database writes.
