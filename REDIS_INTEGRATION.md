# Redis Integration in Progressive Upload Architecture

**Role:** Redis is NOT optional—it's critical for:
1. Celery task queue (message broker)
2. Celery task results (backend storage)
3. Distributed locking (prevent scheduler race conditions)
4. Upload status caching (reduce database queries)

---

## 🔴 How Redis Is Used

### 1. Celery Message Broker (REQUIRED)

**Purpose:** Queue tasks to Celery workers

```python
# celery_app.py
from celery import Celery

app = Celery(
    'wros',
    broker='redis://localhost:6379/0',  # ← Task queue lives here
    backend='redis://localhost:6379/1',  # ← Task results live here
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)
```

**Data flow:**
```
API Endpoint → MessageQueueService.enqueue('process_candidate', candidate_id)
           ↓
       Redis Queue (DB 0)
           ↓
       Celery Worker pulls task
           ↓
       Executes process_candidate()
           ↓
       Stores result in Redis (DB 1)
           ↓
       Frontend polls GET /task-status/{task_id}
           ↓
       Task result read from Redis
```

---

### 2. Celery Task Results Backend (REQUIRED)

**Purpose:** Store task execution results (success/failure/status)

```python
# When task completes
@app.task
def process_candidate(candidate_id, tenant_id):
    try:
        # ... processing ...
        return {'status': 'success', 'candidate_id': candidate_id}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

# Result automatically stored in Redis:
# Key: celery-task-{task_id}
# Value: {'status': 'success', 'candidate_id': '...'}
# TTL: result_expires (default 24 hours)
```

**Frontend queries result:**
```python
def get_task_status(task_id: str):
    """Get Celery task result from Redis."""
    result = celery_app.AsyncResult(task_id)
    
    if result.state == 'PENDING':
        return {'status': 'pending', 'progress': 'task queued'}
    elif result.state == 'PROGRESS':
        return {'status': 'processing', 'progress': result.info}
    elif result.state == 'SUCCESS':
        return {'status': 'success', 'result': result.result}
    elif result.state == 'FAILURE':
        return {'status': 'error', 'error': str(result.info)}
    elif result.state == 'RETRY':
        return {'status': 'retrying', 'attempt': result.info}
```

---

### 3. Distributed Locking (PREVENTS RACE CONDITIONS)

**Purpose:** Ensure only ONE scheduler runs at a time across all server instances

**Problem without Redis locking:**
```
Server A (scheduler job at 2:00:00):
  - Queries candidates with status=uploading
  - Finds 50 candidates
  - Starts queueing them

Server B (scheduler job at 2:00:05, overlapping):
  - Queries candidates with status=uploading
  - Finds SAME 50 candidates (not updated yet)
  - Starts queueing them AGAIN
  
Result: 50 candidates queued TWICE
```

**Solution with Redis locking:**

```python
# celery_tasks.py
from redis import Redis
import time

redis_client = Redis(host='localhost', port=6379, db=2)  # DB 2 for locks

@app.task
def auto_queue_idle_candidates():
    """
    Scheduler job: Auto-queue candidates idle 2+ minutes.
    
    Uses Redis distributed lock to prevent duplicate execution.
    """
    
    # Acquire distributed lock
    lock_key = 'scheduler:auto_queue:lock'
    lock_value = str(time.time())  # Unique value per attempt
    lock_ttl = 180  # 3 minutes (longer than expected job duration)
    
    # Try to acquire lock (atomic operation in Redis)
    acquired = redis_client.set(
        lock_key,
        lock_value,
        nx=True,  # Only set if not exists
        ex=lock_ttl
    )
    
    if not acquired:
        # Another scheduler instance holds the lock
        logger.info("Scheduler already running on another server, skipping")
        return {'status': 'skipped', 'reason': 'lock held elsewhere'}
    
    try:
        db = SessionLocal()
        
        # Atomically select and lock candidates
        candidates = db.query(Candidate).filter(
            Candidate.upload_status == 'uploading',
            Candidate.last_document_uploaded_at < datetime.utcnow() - timedelta(minutes=2)
        ).with_for_update(skip_locked=True).all()
        
        logger.info(f"Auto-queuing {len(candidates)} candidates")
        
        # Queue all candidates atomically
        for candidate in candidates:
            MessageQueueService.enqueue(
                'process_candidate',
                candidate.candidateID,
                candidate.tenant_id
            )
            
            candidate.upload_status = 'queued'
            candidate.queued_at = datetime.utcnow()
        
        db.commit()
        
        return {
            'status': 'success',
            'queued_count': len(candidates)
        }
        
    except Exception as e:
        logger.error(f"Scheduler failed: {e}", exc_info=True)
        db.rollback()
        raise
        
    finally:
        # Release lock
        current_value = redis_client.get(lock_key)
        if current_value == lock_value.encode():
            # Only delete if we still own it (prevent race on cleanup)
            redis_client.delete(lock_key)
        
        db.close()
```

**With Redis lock:**
```
Server A at 2:00:00:
  - SET scheduler:auto_queue:lock (acquired=True)
  - Query and queue candidates
  - DELETE scheduler:auto_queue:lock

Server B at 2:00:05:
  - SET scheduler:auto_queue:lock (acquired=False, lock exists)
  - Skip execution
  - Return immediately
```

**Result:** Only one scheduler runs, zero duplicate processing.

---

### 4. Upload Status Caching (OPTIONAL OPTIMIZATION)

**Purpose:** Reduce database queries on high-frequency status checks

```python
# progressive_upload_service.py
from redis import Redis

redis_cache = Redis(host='localhost', port=6379, db=3)  # DB 3 for caching

def get_upload_status(candidate_id: str, tenant_id: int = 1):
    """Get upload status with Redis caching."""
    
    # Try cache first (fast, < 1ms)
    cache_key = f"upload_status:{candidate_id}"
    cached = redis_cache.get(cache_key)
    
    if cached:
        logger.debug(f"Cache hit for {candidate_id}")
        return json.loads(cached)
    
    # Cache miss: query database
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == candidate_id,
        Candidate.tenant_id == tenant_id
    ).first()
    
    if not candidate:
        return {'status': 'not_found'}
    
    response = {
        'candidate_id': candidate_id,
        'status': candidate.upload_status,
        'documents_uploaded': candidate.actual_document_count,
        'expected_documents': candidate.expected_document_count,
        'progress_percent': (
            (candidate.actual_document_count / candidate.expected_document_count * 100)
            if candidate.expected_document_count > 0 else 0
        ),
    }
    
    # Cache for 30 seconds (status changes aren't instant anyway)
    redis_cache.setex(
        cache_key,
        30,  # seconds
        json.dumps(response)
    )
    
    return response

def invalidate_status_cache(candidate_id: str):
    """Invalidate cache when status changes."""
    cache_key = f"upload_status:{candidate_id}"
    redis_cache.delete(cache_key)

# Usage in other functions:
def upload_document(...):
    # ... upload logic ...
    invalidate_status_cache(candidate_id)  # Clear cache after update

def mark_upload_complete(...):
    # ... complete logic ...
    invalidate_status_cache(candidate_id)  # Clear cache after update
```

---

## 🏗️ Redis Architecture

```
┌─────────────────────────────────────────┐
│          Application Servers            │
│  (API, Celery Workers, Schedulers)      │
└──────────────────┬──────────────────────┘
                   │
                   ↓
        ┌──────────────────────┐
        │   Redis Instance     │
        ├──────────────────────┤
        │ DB 0: Task Queue     │ ← Celery broker
        │ DB 1: Task Results   │ ← Celery backend
        │ DB 2: Locks          │ ← Scheduler locking
        │ DB 3: Cache          │ ← Status caching
        └──────────────────────┘
                   │
                   ↓
        ┌──────────────────────┐
        │   PostgreSQL DB      │
        │  (Authoritative)     │
        └──────────────────────┘
```

---

## ⚙️ Configuration

### Environment Variables

```bash
# Redis
export REDIS_URL=redis://localhost:6379
export REDIS_BROKER_DB=0
export REDIS_BACKEND_DB=1
export REDIS_LOCK_DB=2
export REDIS_CACHE_DB=3

# Celery
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

### Celery Configuration

```python
# celery_app.py
import os
from celery import Celery

app = Celery(
    'wros',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3300,  # 55 min soft limit
    result_expires=86400,  # 24 hours
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_max_tasks_per_child=100,  # Refresh worker every 100 tasks
    
    # Beat scheduler (for auto_queue_idle_candidates)
    beat_schedule={
        'auto-queue-idle-candidates': {
            'task': 'app.tasks.auto_queue_idle_candidates',
            'schedule': 120.0,  # Every 2 minutes
        },
        'cleanup-stale-uploads': {
            'task': 'app.tasks.cleanup_stale_uploads',
            'schedule': 86400.0,  # Every 24 hours
        },
    }
)
```

### Docker Compose

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    
  celery_worker:
    build: .
    command: celery -A app.celery_app worker --loglevel=info
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on:
      - redis
    
  celery_beat:
    build: .
    command: celery -A app.celery_app beat --loglevel=info
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on:
      - redis
```

---

## 🔍 Monitoring Redis

### Check Queue Size

```bash
# How many tasks queued?
redis-cli -n 0 LLEN celery

# What tasks are queued?
redis-cli -n 0 LRANGE celery 0 -1

# What's the scheduler lock status?
redis-cli -n 2 GET scheduler:auto_queue:lock

# Cache hit rate?
redis-cli -n 3 DBSIZE
```

### Memory Management

```python
# In production, set maxmemory policy
redis-cli CONFIG SET maxmemory 2gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru  # LRU eviction

# Monitor memory
redis-cli INFO memory
```

---

## 📊 Data Flow Example

```
1. User uploads 3 documents (progressive, each doc separate)
   
   Document 1:
   - GET /upload-url → S3 pre-signed URL
   - Browser uploads to S3
   - POST /document-uploaded → INSERT to DB, INVALIDATE CACHE
   
   Document 2: (same)
   Document 3: (same)

2. User calls POST /upload-complete
   - BEGIN TRANSACTION
     UPDATE candidates SET status='queued'
     WHERE candidateID='CAN-123'
   - Queue Celery task to Redis
     LPUSH celery "{'task': 'process_candidate', 'id': 'CAN-123'}"
   - COMMIT TRANSACTION
   
3. Celery Worker polls Redis
   - RPOP celery → gets task
   - Calls process_candidate('CAN-123')
   - Stores result in Redis: DB 1
   - Task status stored: {'state': 'SUCCESS', 'result': {...}}

4. Frontend polls upload status
   - GET /upload-status/CAN-123
   - Check Redis cache (DB 3) → MISS
   - Query DB → status='processing'
   - CACHE result for 30s
   - Return to user

5. Scheduler runs every 2 minutes (Celery Beat)
   - Try to acquire lock in Redis (DB 2)
   - If acquired:
     - Query idle candidates
     - Queue each to Redis (DB 0)
     - Update DB
     - Release lock
   - If not acquired (another scheduler has it):
     - Skip execution
```

---

## ✅ Summary: Redis in Architecture

| Component | Redis DB | Purpose | Critical? |
|-----------|----------|---------|-----------|
| Celery Broker | 0 | Task queue | YES |
| Celery Backend | 1 | Task results | YES |
| Scheduler Lock | 2 | Prevent duplicates | YES |
| Status Cache | 3 | Reduce DB load | NO (optional) |

**Without Redis:** Celery doesn't work (no task queue)  
**With Redis:** Complete async job processing, distributed locking, caching
