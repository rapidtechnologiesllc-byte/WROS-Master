# Celery + Redis Setup Guide

## Overview

The HRMS system uses **Celery** as the distributed task queue and **Redis** as the message broker for running background jobs without blocking the web server.

**Benefits:**
- ✅ Bulk imports run in background (200K candidates)
- ✅ Resume parsing doesn't slow down the API
- ✅ Email blasts don't block request handling
- ✅ Reports generate without timeout issues
- ✅ Real-time task monitoring via admin dashboard

## Architecture

```
Web API (FastAPI)
    ↓
Celery Task Queue
    ↓
Redis Message Broker
    ↓
Worker Processes (process tasks)
    ↓
Message Queue Dashboard (localhost:3000/admin/messagequeue)
```

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This includes:
- `celery[redis]>=5.3.0` - Task queue
- `redis>=5.0.0` - Message broker

### 2. Install and Start Redis

#### Option A: Docker (Recommended)
```bash
docker run -d -p 6379:6379 redis:latest
```

#### Option B: macOS (Homebrew)
```bash
brew install redis
brew services start redis
```

#### Option C: Windows (Chocolatey)
```bash
choco install redis-64
# Then start Redis from Services or:
redis-server
```

#### Option D: Manual Installation
Download from https://redis.io/download

### 3. Verify Redis is Running

```bash
redis-cli ping
# Should return: PONG
```

## Starting the System

### 1. Start the Web API (FastAPI)
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### 2. Start Celery Worker

**On Linux/macOS:**
```bash
./start_celery_worker.sh
# Or with custom concurrency:
./start_celery_worker.sh 4  # Use 4 workers
```

**On Windows:**
```bash
start_celery_worker.bat
```

**Or manually:**
```bash
celery -A app.core.celery_app worker --loglevel=info
```

### 3. Access the Dashboard

1. Open http://localhost:3000/admin/messagequeue
2. You'll see:
   - Task status (queued, active, completed, failed)
   - Real-time progress updates
   - Full message history for each task
   - Retry/Clear controls for failed tasks

## Task Types

### 1. Bulk Candidate Import
```python
from app.tasks.bulk_import import import_candidates_task

# Queue the task
task = import_candidates_task.delay(
    file_path="/path/to/candidates.csv",
    tenant_id="default"
)

# Track in dashboard
print(f"Task ID: {task.id}")
```

### 2. Resume Parsing
```python
from app.tasks.resume_parsing import parse_resume_task

task = parse_resume_task.delay(
    candidate_id="CAN-123456",
    file_path="/path/to/resume.pdf"
)
```

### 3. Send Email
```python
from app.tasks.email_tasks import send_email_task, send_bulk_emails_task

# Single email
send_email_task.delay(
    to_email="candidate@example.com",
    subject="Your Offer Letter",
    body="Please review your offer..."
)

# Bulk emails
send_bulk_emails_task.delay(
    recipient_list=["a@example.com", "b@example.com"],
    subject="Group notification",
    body="Message content..."
)
```

### 4. Generate Report
```python
from app.tasks.reporting import generate_report_task

task = generate_report_task.delay(
    report_type="pipeline",
    user_id="user123",
    filters={"status": "OFFER", "created_after": "2026-08-01"}
)
```

## Logging Task Messages

To log progress updates visible in the dashboard:

```python
from app.api.v1.endpoints.admin_queue import log_task_message

task_id = "your-task-id"

# Log info message
log_task_message(task_id, "Processing started", "info")

# Log warning message
log_task_message(task_id, "Skipped invalid row", "warning")

# Log error message
log_task_message(task_id, "Failed to process: invalid format", "error")
```

## Configuration

Redis connection details are in `app/core/celery_app.py`:

```python
broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
```

To use custom Redis:
```bash
export CELERY_BROKER_URL=redis://your-redis-server:6379/0
export CELERY_RESULT_BACKEND=redis://your-redis-server:6379/1
```

## Task Configuration

Edit `app/core/celery_app.py` to adjust:

```python
task_time_limit=30 * 60,          # Hard limit: 30 minutes
task_soft_time_limit=25 * 60,     # Soft limit: 25 minutes
worker_prefetch_multiplier=1,     # One task at a time
worker_max_tasks_per_child=1000,  # Restart after 1000 tasks
```

## Monitoring

### Admin Dashboard
**URL:** http://localhost:3000/admin/messagequeue

Shows:
- ✅ Task status breakdown
- ✅ Real-time progress
- ✅ Full message history
- ✅ Retry controls
- ✅ Clear failed tasks

### Celery Logs
Watch the terminal where Celery worker is running:
```
[2026-08-19 12:00:00,000: INFO/MainProcess] celery@hostname ready.
[2026-08-19 12:00:01,234: INFO/PoolWorker-1] Received task: tasks.bulk_import_candidates
[2026-08-19 12:00:05,567: INFO/PoolWorker-1] Task successful
```

### Redis CLI
```bash
redis-cli
> KEYS *  # See all tasks
> GET celery-task-meta-abc123  # Check specific task
> FLUSHDB  # Clear all data (warning!)
```

## Troubleshooting

### "Connection refused" on Redis
**Problem:** Celery can't connect to Redis
```
[ERROR/MainProcess] Failed to connect to Redis
```

**Solution:**
1. Verify Redis is running: `redis-cli ping`
2. Check Redis URL: `echo $CELERY_BROKER_URL`
3. Test connection: `redis-cli -h localhost -p 6379`

### Tasks stuck in "active"
**Problem:** Tasks appear stuck, not completing
**Solution:**
1. Check Celery worker: Is it still running?
2. Check logs for errors
3. Restart worker: Kill and re-run

### "Task revoked" in dashboard
**Problem:** Task shows as revoked/cancelled
**Solution:**
1. This is normal if retry failed multiple times
2. Click "Clear" to remove from queue
3. Check error messages for root cause

## Bulk Import Workflow

```
1. User uploads CSV file
   ↓
2. Frontend queues task: import_candidates_task.delay()
   ↓
3. Task appears in dashboard with "queued" status
   ↓
4. Worker picks up task, changes to "active"
   ↓
5. Progress bar updates as rows are processed
   ↓
6. Logs show: "Processing row 1/100", "Processing row 50/100"
   ↓
7. Task completes with "completed" status
   ↓
8. Dashboard shows: "100 candidates created, 25 updated, 0 failed"
```

## Performance Tips

### 1. Set Appropriate Concurrency
```bash
# CPU-bound (resume parsing): 
./start_celery_worker.sh $(nproc)  # Use all CPUs

# I/O-bound (email sending):
./start_celery_worker.sh 10  # More workers OK
```

### 2. Tune Task Time Limits
```python
# For long-running imports:
@celery_app.task(time_limit=60*60)  # 1 hour hard limit
def long_running_task():
    pass
```

### 3. Monitor Memory Usage
```bash
# Watch worker memory:
ps aux | grep celery
```

## Production Deployment

### On Linux/Ubuntu Server

```bash
# 1. Install systemd service
sudo cp celery.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable celery
sudo systemctl start celery

# 2. Monitor service
sudo systemctl status celery
sudo journalctl -u celery -f
```

### On AWS/Cloud

```bash
# Set environment variables:
export CELERY_BROKER_URL=redis://elasticache-endpoint:6379/0
export CELERY_RESULT_BACKEND=redis://elasticache-endpoint:6379/1

# Use managed Redis (AWS ElastiCache):
# - No need to run Redis yourself
# - Automatic backups
# - High availability
```

## Next Steps

1. ✅ Install Celery and Redis
2. ✅ Start Redis server
3. ✅ Start Celery worker
4. ✅ Access dashboard: http://localhost:3000/admin/messagequeue
5. ✅ Test with bulk import or email task
6. ✅ Monitor progress in real-time

---

**Questions?** Check the code in:
- Task definitions: `app/tasks/*.py`
- Queue endpoints: `app/api/v1/endpoints/admin_queue.py`
- Celery config: `app/core/celery_app.py`
