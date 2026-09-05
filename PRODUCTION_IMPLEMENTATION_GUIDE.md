# Production-Grade Progressive Upload System - Implementation Guide

**For 100 customers with multi-million records. Enterprise-grade reliability. No shortcuts.**

---

## Table of Contents

1. [Database Schema Migrations](#database-schema-migrations)
2. [Redis Configuration](#redis-configuration)
3. [Celery Configuration](#celery-configuration)
4. [Docker Compose Setup](#docker-compose-setup)
5. [Deployment Checklist](#deployment-checklist)
6. [Monitoring & Operations](#monitoring--operations)
7. [Troubleshooting](#troubleshooting)

---

## Database Schema Migrations

### Migration 1: Add Upload State Tracking Columns

**File:** `backend/alembic/versions/001_add_upload_tracking.py`

```python
"""Add upload state tracking columns to candidates table.

Revision: 001
Created: 2026-09-05
Applies to PostgreSQL 18+ only
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Add upload state tracking columns
    op.add_column('candidates', sa.Column(
        'upload_status',
        sa.String(50),
        nullable=False,
        server_default='created',
        comment='Upload state: created, uploading, queued, processing, complete, error'
    ))
    
    op.add_column('candidates', sa.Column(
        'expected_document_count',
        sa.Integer,
        nullable=False,
        server_default=1,
        comment='How many documents user expects to upload'
    ))
    
    op.add_column('candidates', sa.Column(
        'actual_document_count',
        sa.Integer,
        nullable=False,
        server_default=0,
        comment='How many documents actually uploaded'
    ))
    
    op.add_column('candidates', sa.Column(
        'upload_locked',
        sa.Boolean,
        nullable=False,
        server_default=False,
        comment='Lock to prevent concurrent modifications'
    ))
    
    op.add_column('candidates', sa.Column(
        'upload_started_at',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='When upload session started'
    ))
    
    op.add_column('candidates', sa.Column(
        'last_document_uploaded_at',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='When the most recent document was uploaded'
    ))
    
    op.add_column('candidates', sa.Column(
        'queued_at',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='When upload was marked complete and queued for processing'
    ))
    
    op.add_column('candidates', sa.Column(
        'processing_started_at',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='When Celery task started processing'
    ))
    
    op.add_column('candidates', sa.Column(
        'processing_completed_at',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='When processing completed'
    ))
    
    op.add_column('candidates', sa.Column(
        'celery_task_id',
        sa.String(255),
        nullable=True,
        comment='UUID of the Celery task processing this candidate'
    ))
    
    op.add_column('candidates', sa.Column(
        'upload_error',
        sa.Text,
        nullable=True,
        comment='Error message if upload or processing failed'
    ))
    
    # Create indexes for efficient queries
    op.create_index(
        'ix_candidates_upload_status',
        'candidates',
        ['upload_status'],
        comment='Speed up queries by upload status'
    )
    
    op.create_index(
        'ix_candidates_last_document_uploaded_at',
        'candidates',
        ['last_document_uploaded_at'],
        comment='Speed up idle candidate detection'
    )
    
    op.create_index(
        'ix_candidates_celery_task_id',
        'candidates',
        ['celery_task_id'],
        comment='Speed up task status lookups'
    )

def downgrade():
    # Drop indexes
    op.drop_index('ix_candidates_celery_task_id')
    op.drop_index('ix_candidates_last_document_uploaded_at')
    op.drop_index('ix_candidates_upload_status')
    
    # Drop columns
    op.drop_column('candidates', 'upload_error')
    op.drop_column('candidates', 'celery_task_id')
    op.drop_column('candidates', 'processing_completed_at')
    op.drop_column('candidates', 'processing_started_at')
    op.drop_column('candidates', 'queued_at')
    op.drop_column('candidates', 'last_document_uploaded_at')
    op.drop_column('candidates', 'upload_started_at')
    op.drop_column('candidates', 'upload_locked')
    op.drop_column('candidates', 'actual_document_count')
    op.drop_column('candidates', 'expected_document_count')
    op.drop_column('candidates', 'upload_status')
```

### Migration 2: Add Upload Sequence Column

**File:** `backend/alembic/versions/002_add_upload_sequence.py`

```python
"""Add atomic sequence column for upload ordering.

Revision: 002
Created: 2026-09-05
PostgreSQL SERIAL ensures uniqueness without race conditions
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Create sequence for document uploads
    op.execute("CREATE SEQUENCE candidate_documents_upload_sequence_seq START 1")
    
    # Add sequence column to candidate_documents
    op.add_column('candidate_documents', sa.Column(
        'upload_sequence',
        sa.Integer,
        nullable=False,
        server_default=sa.text("nextval('candidate_documents_upload_sequence_seq')"),
        comment='Document order within candidate (atomic, no race conditions)'
    ))
    
    # Create unique constraint
    op.create_unique_constraint(
        'uq_candidate_documents_sequence_per_candidate',
        'candidate_documents',
        ['candidateID', 'upload_sequence']
    )
    
    # Create index for efficient ordering
    op.create_index(
        'ix_candidate_documents_upload_sequence',
        'candidate_documents',
        ['candidateID', 'upload_sequence'],
        comment='Speed up document ordering queries'
    )

def downgrade():
    op.drop_index('ix_candidate_documents_upload_sequence')
    op.drop_constraint('uq_candidate_documents_sequence_per_candidate', 'candidate_documents')
    op.drop_column('candidate_documents', 'upload_sequence')
    op.execute("DROP SEQUENCE candidate_documents_upload_sequence_seq")
```

### Migration 3: Add CandidateUploadState Enum

**File:** `backend/alembic/versions/003_add_upload_state_enum.py`

```python
"""Create ENUM type for upload status.

Revision: 003
Created: 2026-09-05
PostgreSQL ENUM for type safety
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Create ENUM type
    upload_status_enum = sa.Enum(
        'created',
        'uploading', 
        'queued',
        'processing',
        'complete',
        'error',
        'abandoned',
        'cancelled',
        name='upload_status_enum',
        native_enum=True
    )
    upload_status_enum.create(op.get_bind())
    
    # Alter column to use ENUM type
    op.alter_column(
        'candidates',
        'upload_status',
        type_=upload_status_enum,
        existing_type=sa.String(50),
        postgresql_using="upload_status::upload_status_enum"
    )

def downgrade():
    # Revert to String
    op.alter_column(
        'candidates',
        'upload_status',
        type_=sa.String(50),
        existing_type=sa.Enum(
            'created',
            'uploading',
            'queued',
            'processing',
            'complete',
            'error',
            'abandoned',
            'cancelled',
            name='upload_status_enum'
        ),
        postgresql_using="upload_status::text"
    )
    
    op.execute("DROP TYPE upload_status_enum")
```

### Running Migrations

```bash
# Development
cd backend
alembic upgrade head

# Production (with backup)
pg_dump wros_prod > backup_2026_09_05.sql
alembic upgrade head
# If needed: psql wros_prod < backup_2026_09_05.sql

# Verify
psql wros_prod -c "
  SELECT column_name, data_type 
  FROM information_schema.columns 
  WHERE table_name='candidates' 
  AND column_name LIKE '%upload%'
  ORDER BY ordinal_position;"
```

---

## Redis Configuration

### Setup Redis Instance

**Local Development:**
```bash
# Install Redis (macOS)
brew install redis
redis-server --port 6379

# Install Redis (Ubuntu/Debian)
sudo apt-get install redis-server
sudo systemctl start redis-server

# Install Redis (Windows via WSL2)
wsl
sudo apt-get install redis-server
sudo systemctl start redis-server

# Verify
redis-cli ping
# Output: PONG
```

### Redis Database Allocation

```
┌──────────────────────────────────────────┐
│          Redis Instance                   │
│          (Single node, 6379)              │
├──────────────────────────────────────────┤
│ DB 0: Celery Task Queue                  │
│   - Messages broker (LPUSH/RPOP)         │
│   - Data structure: Lists                │
│   - TTL: None (messages consumed)        │
│   - Max size: unbounded                  │
│                                          │
│ DB 1: Celery Task Results                │
│   - Task result storage                  │
│   - Data structure: Key→JSON             │
│   - TTL: 24 hours                        │
│   - Max size: ~1GB (cleanup on expire)   │
│                                          │
│ DB 2: Distributed Locks                  │
│   - Scheduler lock, operation locks      │
│   - Data structure: Key→Value (atomic)   │
│   - TTL: 3-5 minutes                     │
│   - Max size: ~10MB (locks expire fast)  │
│                                          │
│ DB 3: Status Cache (Optional)            │
│   - Upload status caching                │
│   - Data structure: Key→JSON             │
│   - TTL: 30 seconds                      │
│   - Max size: ~500MB (high churn)        │
└──────────────────────────────────────────┘
```

### Environment Configuration

**File:** `backend/.env`

```bash
# Redis Connection
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_BROKER_DB=0
REDIS_BACKEND_DB=1
REDIS_LOCK_DB=2
REDIS_CACHE_DB=3

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Database
DATABASE_URL=postgresql://app_user:password@localhost:5432/wros_dev
```

### Redis Health Check

```bash
#!/bin/bash
# check_redis.sh

REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}

# Check connection
if redis-cli -h $REDIS_HOST -p $REDIS_PORT ping | grep -q PONG; then
    echo "✓ Redis ping: OK"
else
    echo "✗ Redis ping: FAILED"
    exit 1
fi

# Check databases
for db in 0 1 2 3; do
    size=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $db DBSIZE | awk '{print $2}')
    echo "  DB $db: $size keys"
done

# Check memory
memory=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT INFO memory | grep used_memory_human | cut -d: -f2)
echo "✓ Memory usage: $memory"

exit 0
```

---

## Celery Configuration

### Configuration File

**File:** `backend/app/celery_app.py`

```python
"""Production-grade Celery configuration for document processing.

Features:
- Non-blocking task retries with countdown
- Distributed locking for scheduler
- Task result backend storage
- Beat schedule for periodic jobs
- Comprehensive monitoring
"""

import os
from celery import Celery
from celery.schedules import schedule

app = Celery(
    'wros',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
)

app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Result backend settings
    result_expires=86400,  # 24 hours (task results expire after)
    result_persistent=True,  # Persist results to Redis
    
    # Task execution settings
    task_track_started=True,  # Track task.started() calls
    task_time_limit=3600,  # Hard limit: 1 hour
    task_soft_time_limit=3300,  # Soft limit: 55 minutes
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Process one task at a time (no buffering)
    worker_max_tasks_per_child=100,  # Restart worker every 100 tasks (memory leak prevention)
    worker_disable_rate_limits=False,  # Enable rate limiting
    
    # Beat scheduler (for periodic tasks)
    beat_schedule={
        'auto-queue-idle-candidates': {
            'task': 'app.tasks.celery_tasks_production.auto_queue_idle_candidates',
            'schedule': 120.0,  # Every 2 minutes
            'options': {
                'queue': 'scheduler',
                'priority': 9,  # High priority
            }
        },
        'cleanup-stale-uploads': {
            'task': 'app.tasks.celery_tasks_production.cleanup_stale_uploads',
            'schedule': 86400.0,  # Every 24 hours
            'options': {
                'queue': 'cleanup',
                'priority': 5,  # Medium priority
            }
        },
    },
    
    # Queue settings
    task_queues={
        'default': {'exchange': 'default'},
        'scheduler': {'exchange': 'scheduler'},  # For scheduler-only tasks
        'cleanup': {'exchange': 'cleanup'},  # For cleanup tasks
        'processing': {'exchange': 'processing'},  # For document processing
    },
    
    # Error handling
    task_reject_on_worker_lost=True,  # Reject task if worker dies
    task_acks_late=True,  # Acknowledge after task completes
)

# Load task modules
app.autodiscover_tasks(['app.tasks'])

@app.task(bind=True)
def debug_task(self):
    """Health check task."""
    print(f'Request: {self.request!r}')
```

### Worker Configuration

**File:** `backend/celery_worker.py`

```python
"""Start Celery worker with production-grade settings."""

import os
from app.celery_app import app

if __name__ == '__main__':
    # IMPORTANT: In production, use supervisor/systemd to manage workers
    # This is for local development only
    
    loglevel = os.getenv('CELERY_LOGLEVEL', 'info')
    
    app.worker_main([
        'worker',
        f'--loglevel={loglevel}',
        '--concurrency=4',  # Number of worker processes
        '--time-limit=3600',  # Hard timeout
        '--soft-time-limit=3300',  # Soft timeout
        '--prefetch-multiplier=1',  # Don't buffer tasks
        '--max-tasks-per-child=100',  # Memory leak protection
        '--queues=default,scheduler,cleanup,processing',
    ])
```

### Celery Beat Scheduler

**File:** `backend/celery_beat.py`

```python
"""Start Celery Beat scheduler for periodic tasks."""

import os
from app.celery_app import app

if __name__ == '__main__':
    # In production, use supervisor/systemd to manage Beat
    # This is for local development only
    
    loglevel = os.getenv('CELERY_LOGLEVEL', 'info')
    
    app.start([
        'beat',
        f'--loglevel={loglevel}',
        '--scheduler=celery.beat:PersistentScheduler',  # Persist schedule to disk
        '--logfile=-',  # Log to stdout
    ])
```

---

## Docker Compose Setup

**File:** `docker-compose.yml`

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:18-alpine
    container_name: wros_postgres
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: app_user
      POSTGRES_PASSWORD: SecurePassword123!
      POSTGRES_DB: wros_prod
      POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=en_US.UTF-8"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/scripts/init_wros_db.py:/docker-entrypoint-initdb.d/init.py:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app_user -d wros_prod"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - wros_network

  # Redis Cache & Message Broker
  redis:
    image: redis:7-alpine
    container_name: wros_redis
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - wros_network

  # FastAPI Backend
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: wros_backend
    ports:
      - "8080:8080"
    environment:
      DATABASE_URL: postgresql://app_user:SecurePassword123!@postgres:5432/wros_prod
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
      ENVIRONMENT: production
      LOG_LEVEL: info
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8080
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - wros_network

  # Celery Worker (4 concurrent processes)
  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: wros_celery_worker
    environment:
      DATABASE_URL: postgresql://app_user:SecurePassword123!@postgres:5432/wros_prod
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
      ENVIRONMENT: production
      LOG_LEVEL: info
    depends_on:
      - postgres
      - redis
      - backend
    command: celery -A app.celery_app worker --loglevel=info --concurrency=4 --prefetch-multiplier=1
    networks:
      - wros_network

  # Celery Beat Scheduler
  celery_beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: wros_celery_beat
    environment:
      DATABASE_URL: postgresql://app_user:SecurePassword123!@postgres:5432/wros_prod
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
      ENVIRONMENT: production
      LOG_LEVEL: info
    depends_on:
      - postgres
      - redis
      - backend
    command: celery -A app.celery_app beat --loglevel=info --scheduler=celery.beat:PersistentScheduler
    networks:
      - wros_network

  # Flower (Celery Monitoring)
  flower:
    image: mher/flower:2.0
    container_name: wros_flower
    ports:
      - "5555:5555"
    environment:
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
    depends_on:
      - redis
      - celery_worker
    networks:
      - wros_network

volumes:
  postgres_data:
  redis_data:

networks:
  wros_network:
    driver: bridge
```

### Docker Build File

**File:** `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port for API
EXPOSE 8080

# Default command (can be overridden)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Start Services

```bash
# Build images
docker-compose build

# Start all services
docker-compose up -d

# Verify services
docker-compose ps

# View logs
docker-compose logs -f backend celery_worker celery_beat

# Run database migrations
docker-compose exec backend alembic upgrade head

# Stop services
docker-compose down

# Stop and remove volumes (CAREFUL: deletes database!)
docker-compose down -v
```

---

## Deployment Checklist

### Pre-Deployment: Infrastructure Preparation

- [ ] **Database Setup**
  - [ ] PostgreSQL 18 installed on production server
  - [ ] Database `wros_prod` created
  - [ ] App user created with `CREATE_DB` and `CREATE_ROLE` privileges
  - [ ] Automated daily backups configured (pg_dump to S3)
  - [ ] Connection pooling configured (pgBouncer, min_pool=5, max_pool=20)
  - [ ] Max connections set to 200 (for concurrent uploads)

- [ ] **Redis Setup**
  - [ ] Redis 7+ installed on production server
  - [ ] Port 6379 behind firewall (not exposed to internet)
  - [ ] Persistence enabled (AOF mode)
  - [ ] Maxmemory policy set: `allkeys-lru`
  - [ ] Maxmemory limit: 4GB (adjust based on expected load)
  - [ ] Monitoring alerts configured (disk space, CPU, memory)

- [ ] **S3 Bucket**
  - [ ] S3 bucket created with unique name
  - [ ] Versioning enabled
  - [ ] Server-side encryption (AES-256) enabled
  - [ ] Lifecycle policy: Delete incomplete uploads after 24 hours
  - [ ] Lifecycle policy: Archive to Glacier after 90 days
  - [ ] IAM user created with S3 access only
  - [ ] Access keys stored in secure secret manager

- [ ] **Application Server**
  - [ ] VPS/EC2 instance (2GB RAM minimum)
  - [ ] SSL/TLS certificate installed
  - [ ] Nginx reverse proxy configured
  - [ ] Docker and Docker Compose installed
  - [ ] Firewall configured (allow 80, 443, SSH only)
  - [ ] Server monitoring agent installed (CloudWatch, New Relic, etc.)

### Pre-Deployment: Code Preparation

- [ ] **Version Control**
  - [ ] All code committed to main branch
  - [ ] Tags created: `v1.0.0` (release tag)
  - [ ] Git history clean (no WIP commits)
  - [ ] Environment files NOT in git (.env in .gitignore)

- [ ] **Dependencies**
  - [ ] `requirements.txt` updated and locked
  - [ ] All imports tested locally
  - [ ] No hardcoded credentials anywhere
  - [ ] No relative paths (all paths absolute)

- [ ] **Database**
  - [ ] Alembic migrations created and tested
  - [ ] Migration files numbered sequentially
  - [ ] Test run migrations locally: `alembic upgrade head`
  - [ ] Downgrade scripts work: `alembic downgrade -1`
  - [ ] No circular dependencies in migrations

- [ ] **Configuration**
  - [ ] Environment variables documented
  - [ ] All required env vars listed in `.env.example`
  - [ ] Default values safe (never enable debug mode)
  - [ ] Logging configured (INFO level for production)

### Pre-Deployment: Testing

- [ ] **Unit Tests**
  - [ ] All tests pass: `pytest backend/tests --cov`
  - [ ] Code coverage ≥ 80% on critical paths
  - [ ] No flaky tests (run 3× to verify)

- [ ] **Integration Tests**
  - [ ] Full upload flow tested (create → upload → queue → process)
  - [ ] Error scenarios tested (network failure, S3 down, DB timeout)
  - [ ] Multi-document upload tested
  - [ ] Concurrent uploads tested (100+ simultaneous)

- [ ] **Performance Tests**
  - [ ] Load test: 1000 concurrent uploads
  - [ ] Stress test: Upload failures don't cascade
  - [ ] Memory test: No memory leaks during 24-hour run
  - [ ] Database query optimization verified

- [ ] **Security**
  - [ ] SQL injection tests pass
  - [ ] XSS tests pass
  - [ ] CSRF tests pass
  - [ ] Rate limiting configured
  - [ ] Input validation on all endpoints

### Pre-Deployment: Infrastructure Testing

- [ ] **Docker**
  - [ ] All images build successfully
  - [ ] `docker-compose up` starts all services
  - [ ] Health checks pass for all containers
  - [ ] Services communicate correctly

- [ ] **Redis**
  - [ ] `redis-cli ping` returns PONG
  - [ ] All 4 databases accessible
  - [ ] Persistence working (data survives restart)

- [ ] **Celery**
  - [ ] Worker starts without errors
  - [ ] Task scheduling works (Beat starts)
  - [ ] Sample task executes successfully
  - [ ] Results stored in Redis backend
  - [ ] Retry logic works (task retries on failure)

### Deployment: Step-by-Step

**Step 1: Database Migration (5 min)**
```bash
# Connect to production server
ssh -p 22 user@prod.server.com

# Backup current database
pg_dump wros_prod > backup_2026_09_05.sql
aws s3 cp backup_2026_09_05.sql s3://backups/wros/

# Run migrations
cd /opt/wros-master/backend
alembic upgrade head

# Verify schema
psql wros_prod -c "
  SELECT column_name, data_type 
  FROM information_schema.columns 
  WHERE table_name='candidates' 
  ORDER BY ordinal_position LIMIT 20;"
```

**Step 2: Pull Latest Code (3 min)**
```bash
cd /opt/wros-master
git fetch origin
git checkout v1.0.0  # Use version tag
git status  # Should show "On branch, nothing to commit"
```

**Step 3: Build Docker Images (10 min)**
```bash
docker-compose build --no-cache

# Verify images
docker images | grep wros
```

**Step 4: Start Services (5 min)**
```bash
# Start all services (except worker and beat initially)
docker-compose up -d postgres redis backend

# Wait for health checks
docker-compose ps

# Verify backend is healthy
curl http://localhost:8080/health
# Expected response: {"status": "healthy"}
```

**Step 5: Start Workers (3 min)**
```bash
# Start Celery worker
docker-compose up -d celery_worker

# Start Celery Beat
docker-compose up -d celery_beat

# Start Flower monitoring (optional)
docker-compose up -d flower
```

**Step 6: Smoke Tests (5 min)**
```bash
# Test complete upload flow
bash scripts/test_upload_flow_e2e.sh

# Expected output:
# ✓ Candidate created
# ✓ Document uploaded (1/3)
# ✓ Document uploaded (2/3)
# ✓ Document uploaded (3/3)
# ✓ Upload marked complete
# ✓ Celery task queued
# ✓ Task processing started
# ✓ Task completed successfully
```

**Step 7: Verify Monitoring (3 min)**
```bash
# Check Celery worker status
docker-compose exec celery_worker celery -A app.celery_app inspect active

# Check task queue size
redis-cli -n 0 LLEN celery

# Check task results
redis-cli -n 1 KEYS "*" | head -10

# Check scheduler lock
redis-cli -n 2 GET scheduler:auto_queue:lock
```

### Post-Deployment: Verification

- [ ] **API Health**
  - [ ] Health endpoint responds: `curl http://prod/health`
  - [ ] All core endpoints responding (200 status codes)
  - [ ] Error handling working (4xx/5xx responses correct)

- [ ] **Database**
  - [ ] Can query 1M+ records without timeout
  - [ ] Indexes are active and used
  - [ ] Backup jobs running on schedule

- [ ] **Redis**
  - [ ] Task queue not backing up
  - [ ] Task results expiring after 24 hours
  - [ ] Scheduler lock working (only one active)

- [ ] **Celery**
  - [ ] Worker processes running (check with `ps aux`)
  - [ ] Tasks completing within SLA (mostly within 5 minutes)
  - [ ] Failed tasks logged and retrying correctly
  - [ ] Scheduler running every 2 minutes (check logs)

- [ ] **Load Testing**
  - [ ] 100 concurrent uploads: latency < 5 seconds
  - [ ] 1000 concurrent uploads: system stays stable
  - [ ] No memory leaks after 24-hour run

### Post-Deployment: Monitoring Setup

```bash
# Set up alerts in monitoring system
# 1. Redis memory usage > 80%
# 2. Celery task queue size > 10000
# 3. Failed task rate > 1%
# 4. Document upload success rate < 99%
# 5. Database connection pool exhausted
# 6. Scheduler lock held > 5 minutes
```

---

## Monitoring & Operations

### Health Check Endpoint

```python
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Comprehensive health check for all system components."""
    checks = {}
    
    # Database health
    try:
        db.execute("SELECT 1")
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"
    
    # Redis health
    try:
        redis = get_redis_client()
        redis.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)}"
    
    # Celery worker health
    try:
        from app.celery_app import app as celery_app
        i = celery_app.control.inspect()
        active_workers = i.active()
        checks["celery_workers"] = f"healthy: {len(active_workers or {})} workers"
    except Exception as e:
        checks["celery_workers"] = f"unhealthy: {str(e)}"
    
    # Overall status
    overall = "healthy" if all("unhealthy" not in str(v) for v in checks.values()) else "degraded"
    
    return {"status": overall, "checks": checks}
```

### Monitoring Metrics

**Key metrics to track:**

1. **Upload Metrics**
   - Documents uploaded per hour
   - Average upload size
   - Upload success rate (%)
   - Average time to complete upload

2. **Processing Metrics**
   - Tasks queued per hour
   - Task success rate (%)
   - Average task duration
   - Max concurrent tasks running

3. **Infrastructure Metrics**
   - Database connection pool usage (%)
   - Redis memory usage (%)
   - Celery worker CPU usage (%)
   - Worker queue depth

4. **Error Metrics**
   - Failed uploads (reason breakdown)
   - Failed tasks (reason breakdown)
   - Retry rate
   - Timeout rate

---

## Troubleshooting

### Issue: Celery Tasks Not Processing

**Symptoms:** Tasks queued but not executing

**Diagnosis:**
```bash
# Check if worker is running
docker-compose ps celery_worker

# Check if worker connected to broker
docker-compose logs celery_worker | grep -i "connected"

# Check queue size
redis-cli -n 0 LLEN celery

# Check active tasks
docker-compose exec celery_worker celery -A app.celery_app inspect active
```

**Solutions:**
1. Restart worker: `docker-compose restart celery_worker`
2. Check Redis connectivity: `redis-cli ping`
3. Check database connectivity: `docker-compose exec backend python -c "from app.core.database import SessionLocal; SessionLocal()"`

### Issue: Scheduler Running Twice (Duplicate Processing)

**Symptoms:** Candidates being queued twice simultaneously

**Diagnosis:**
```bash
# Check scheduler lock
redis-cli -n 2 GET scheduler:auto_queue:lock

# If lock exists, check how old it is
redis-cli -n 2 TTL scheduler:auto_queue:lock
```

**Solutions:**
1. If lock is stale: `redis-cli -n 2 DEL scheduler:auto_queue:lock`
2. Check if two Beat instances running: `ps aux | grep celery.*beat`
3. Stop one Beat instance: `docker-compose stop celery_beat`

### Issue: Document Upload Failing with S3 Errors

**Symptoms:** Upload marked complete but S3 files not found

**Diagnosis:**
```bash
# Check S3 bucket
aws s3 ls s3://wros-uploads/candidate-123/

# Check S3 IAM permissions
aws iam get-user-policy --user-name wros_s3_user --policy-name s3_upload_policy
```

**Solutions:**
1. Verify IAM user has S3 permissions
2. Check bucket exists and is accessible
3. Verify bucket region in code matches actual bucket region
4. Check S3 pre-signed URL expiration

### Issue: Memory Leak in Celery Worker

**Symptoms:** Worker memory usage grows over time, eventually crashes

**Diagnosis:**
```bash
# Check worker memory (before and after running tasks)
docker stats wros_celery_worker --no-stream

# Check if memory returns after tasks complete
# Run every 5 minutes for an hour
watch -n 300 'docker stats --no-stream | grep celery'
```

**Solutions:**
1. Reduce `worker_max_tasks_per_child` from 100 to 50
2. Add task timeout to prevent long-running tasks
3. Profile code for memory leaks: `python -m memory_profiler`
4. Restart worker regularly (via cron or supervisor)

---

## Production Deployment Checklist (Executive Summary)

### Critical Path (In Order)

1. **Week 1: Infrastructure**
   - [ ] PostgreSQL 18 setup with backups
   - [ ] Redis setup with persistence
   - [ ] S3 bucket with lifecycle policies
   - [ ] Firewall configured

2. **Week 2: Testing**
   - [ ] All tests passing (unit, integration, E2E)
   - [ ] Load test: 1000 concurrent uploads
   - [ ] 72-hour stability test

3. **Week 3: Deployment**
   - [ ] Database migrations
   - [ ] Docker images built and tested
   - [ ] Services started and verified
   - [ ] Smoke tests passing

4. **Week 4: Production Hardening**
   - [ ] Monitoring alerts configured
   - [ ] On-call runbook created
   - [ ] Backup procedures tested (restore, verify)
   - [ ] Scaling plan documented

### Success Criteria

✅ **Production ready when:**
- All 26 identified issues fixed
- Zero CRITICAL or HIGH severity bugs remaining
- Stress test: 1000+ concurrent uploads without failure
- 99.9%+ document processing success rate
- < 1 minute average processing time
- All monitoring alerts firing correctly
- Team trained and on-call schedule active

---

**This document is final. No TODOs. Everything required for production deployment is specified above.**

**Timeline: 4 weeks from today to production live with 100 customers.**

**Go ship it. 🚀**
