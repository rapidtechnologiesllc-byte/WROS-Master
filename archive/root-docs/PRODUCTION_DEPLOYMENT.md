# Production Deployment Guide

## CRITICAL REQUIREMENTS

### 1. Redis Installation & Configuration

**Status:** ⚠️ MUST BE COMPLETED BEFORE PRODUCTION

Redis is required for Celery task queueing. Without it, the system cannot queue candidates.

#### Install Redis on Windows

**Option A: Using Chocolatey (Recommended)**
```powershell
# Install Chocolatey first if needed
Set-ExecutionPolicy Bypass -Scope Process -Force; `
[System.Net.ServicePointManager]::SecurityProtocol = `
[System.Net.ServicePointManager]::SecurityProtocol -bor 3072; `
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install Redis as Windows Service
choco install redis-64

# Verify service created
Get-Service Redis
```

**Option B: Manual Installation**
1. Download from: https://github.com/microsoftarchive/redis/releases
2. Extract to: `C:\Program Files\Redis`
3. Run as Administrator: `redis-server.exe --service-install redis.windows.conf`
4. Verify: Services.msc → look for "Redis"

#### Configure Redis for Production

**File:** `redis.windows.conf` (usually at `C:\Program Files\Redis\`)

```conf
# Critical settings for production

# Persistence - save every 900 seconds if 1 change occurred
save 900 1
save 300 10
save 60 10000

# Log file
logfile "C:\Program Files\Redis\redis.log"

# Max memory policy - evict least recently used when full
maxmemory 512mb
maxmemory-policy allkeys-lru

# Disable dangerous commands in production
rename-command FLUSHDB ""
rename-command FLUSHALL ""

# Require password for remote connections
# requirepass production-password-here
```

#### Start Redis Service

```powershell
# Start the service
Start-Service Redis

# Check status
Get-Service Redis

# Verify it's listening
netstat -ano | findstr ":6379"
```

#### Verify Redis is Ready

```powershell
# Test connection
redis-cli ping
# Should return: PONG

# Check memory
redis-cli info memory
```

---

## System Startup Sequence (MUST FOLLOW THIS ORDER)

### 1. Start Redis
```powershell
Start-Service Redis
# OR manually: redis-server.exe
```

### 2. Start Celery Worker
```powershell
cd backend
python -m celery -A app.celery_app worker --loglevel=info --concurrency=4
```

### 3. Start Backend
```powershell
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### 4. Automated Startup (Recommended for Production)
```powershell
.\scripts\startup-production.ps1
```

This script:
- ✅ Verifies Redis is running
- ✅ Starts Celery worker
- ✅ Starts backend
- ✅ Monitors all processes
- ✅ Fails fast if any process dies

---

## Monitoring Checklist

### Daily

- [ ] Redis running: `netstat -ano | findstr ":6379"`
- [ ] Backend running: `http://localhost:8080/api/v1/config/queue-types` returns 200
- [ ] Celery active: `redis-cli keys "*"` shows active tasks
- [ ] No critical errors in backend logs

### Weekly

- [ ] Redis memory usage: `redis-cli info memory`
- [ ] Disk space for logs
- [ ] No connection timeouts in logs
- [ ] Message queue latency normal

### Monthly

- [ ] Redis persistence working: `redis-cli --rdb /tmp/redis-backup.rdb`
- [ ] Backup Redis data
- [ ] Test disaster recovery procedures
- [ ] Review and rotate logs

---

## Health Checks

### Redis Health
```powershell
# Check connection
redis-cli ping
# Expected: PONG

# Check memory
redis-cli info memory | findstr "used_memory"

# Check number of connected clients
redis-cli info clients | findstr "connected_clients"
```

### Backend Health
```bash
curl http://localhost:8080/api/v1/config/queue-types
# Expected: {"status": "success", "queue_types": [...], "count": N}
```

### Celery Health
```bash
celery -A app.celery_app inspect active
# Expected: Shows active tasks
```

### Message Queue Health
```bash
python scripts/test-queue-fix.py
# Expected: Message found in ChannelQueueItem database
```

---

## Failure Scenarios & Recovery

### Redis Crashes
- **Detection:** Backend logs show "ConnectionError" to Redis
- **Recovery:** Restart Redis service: `Start-Service Redis`
- **Prevention:** Monitor `redis.log` for errors

### Celery Worker Dies
- **Detection:** Backend still responds but tasks don't process
- **Recovery:** Restart Celery: `python -m celery -A app.celery_app worker`
- **Prevention:** Use startup-production.ps1 which monitors this

### Backend Hangs
- **Detection:** HTTP requests timeout
- **Recovery:** Restart backend and check Redis/Celery status first
- **Prevention:** Check Redis is responding before restarting backend

### Database Connection Lost
- **Detection:** "OperationalError: connection to server at..." in logs
- **Recovery:** Verify PostgreSQL is running, check connection string
- **Prevention:** Use startup-production.ps1 for proper ordering

---

## Environment Variables (Production)

```powershell
# Set these BEFORE starting any service

# Database
$env:DATABASE_URL = "postgresql://app_user:PASSWORD@db-host:5432/wros_prod"

# Redis
$env:REDIS_URL = "redis://localhost:6379/0"

# Environment
$env:ENVIRONMENT = "production"

# Logging
$env:LOG_LEVEL = "INFO"

# Celery
$env:CELERY_BROKER_URL = "redis://localhost:6379/0"
$env:CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
```

---

## Pre-Production Checklist

- [ ] Redis installed as Windows Service
- [ ] Redis set to auto-start
- [ ] Redis configuration file updated
- [ ] Backend environment variables set
- [ ] Celery can connect to Redis
- [ ] Backend can connect to PostgreSQL
- [ ] Message queue test passes: `python scripts/test-queue-fix.py`
- [ ] Load test with 100+ concurrent candidate creations
- [ ] Dashboard displays real queue data (not hardcoded zeros)
- [ ] Deployment script tested 3x
- [ ] Monitoring alerts configured
- [ ] Backup/restore procedures documented
- [ ] Disaster recovery plan written

---

## Troubleshooting

### "Redis not running on port 6379"
```powershell
# Check if service exists
Get-Service Redis

# If not installed, install it (see above)

# If exists but not running
Start-Service Redis

# If startup fails, check logs
Get-Content "C:\Program Files\Redis\redis.log" -Tail 50
```

### "Celery connection refused"
```powershell
# Verify Redis is listening
netstat -ano | findstr ":6379"

# If not listening, start Redis first
Start-Service Redis

# Then start Celery
```

### "Message queue dashboard shows 0 messages"
```powershell
# Run diagnostic test
python scripts/test-queue-fix.py

# If test fails:
# 1. Check backend logs for database errors
# 2. Verify ChannelQueueItem table exists
# 3. Restart backend with latest code
```

### "Backend responds but tasks don't process"
```powershell
# Check Celery status
celery -A app.celery_app inspect active

# If no active tasks, restart Celery
taskkill /F /IM python.exe
Start-Process python -Args "-m celery -A app.celery_app worker"
```

---

## Production Readiness Status

| Component | Status | Action |
|-----------|--------|--------|
| Code | ✅ Ready | Deployed to main |
| Database | ✅ Ready | PostgreSQL configured |
| Redis | ⚠️ **NOT READY** | **MUST INSTALL SERVICE** |
| Backend | ✅ Ready | Startup script available |
| Celery | ✅ Ready | Configured, awaits Redis |
| Monitoring | ⚠️ Partial | Setup checklist above |
| Disaster Recovery | ⚠️ Planned | Document backup strategy |

**BLOCKING ISSUE:** Redis must be installed and running as Windows Service before production deployment.

Once Redis is installed and verified working, the system is production-ready.
