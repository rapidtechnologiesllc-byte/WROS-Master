# WROS Server Startup Guide

**MANDATORY: Run this at the beginning of each development session or after server restart.**

## Quick Start (One Command)

```powershell
.\scripts\startup-production.ps1
```

This starts everything in order:
1. ✅ Verifies Redis (6379)
2. ✅ Starts Celery Worker (background tasks)
3. ✅ Starts Flower Monitoring (5555)
4. ✅ Starts FastAPI Backend (8080)
5. ✅ Verifies all services responsive

## What Gets Started

| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| Redis | 6379 | Message broker for Celery | Core dependency |
| Celery Worker | - | Async task execution | Required for features |
| Flower | 5555 | Queue monitoring dashboard | For operations |
| FastAPI Backend | 8080 | Main API server | Core |
| Frontend | 3000 | React dashboard | Run separately: `cd frontend && npm start` |

## Pre-Flight Checklist

Before running startup script:

- [ ] PostgreSQL running on 5432 (verify: `psql --version`)
- [ ] Redis installed (verify: `redis-server.exe` exists or `redis-cli --version`)
- [ ] Python 3.12+ installed (`python --version`)
- [ ] Backend dependencies installed (`pip list | grep celery`)
- [ ] No processes on ports 6379, 8080, 5555 (verify: `netstat -ano | findstr :PORT`)

## Manual Startup (If Script Fails)

If `startup-production.ps1` fails, start services manually in this order:

### 1. Start Redis
```powershell
redis-server.exe
```

### 2. Start Celery Worker
```powershell
cd backend
python -m celery -A app.celery_app worker --loglevel=info --concurrency=4
```

### 3. Start Flower (in new terminal)
```powershell
cd backend
python -m celery -A app.celery_app flower --port=5555
```

### 4. Start Backend (in new terminal)
```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

### 5. Start Frontend (in new terminal)
```powershell
cd frontend
npm start
```

## Verification

Once startup completes, verify all services:

```powershell
# Backend API
curl http://localhost:8080/api/v1/config/queue-types

# Flower Dashboard
# Open browser: http://localhost:5555

# Frontend
# Open browser: http://localhost:3000

# Queue Monitoring (redirects to Flower)
# Open browser: http://localhost:3000/admin/messagequeue
```

Expected results:
- ✅ Backend returns `{"status":"success","queue_types":[...]}`
- ✅ Flower shows worker status and queue metrics
- ✅ Frontend dashboard loads with navigation
- ✅ `/admin/messagequeue` redirects to Flower with 2-second countdown

## Troubleshooting

### "Redis is not running"
```powershell
redis-server.exe
# Leave this running in a terminal
```

### "ModuleNotFoundError: No module named 'flower'"
```powershell
pip install flower
```

### "Port already in use"
```powershell
# Find process on port (e.g., 8080)
netstat -ano | findstr :8080

# Kill process by PID
taskkill /F /PID <PID>
```

### "Celery worker not connecting to Flower"
- Verify Redis is running on 6379
- Check no firewall blocking localhost connections
- Restart Celery worker and Flower

### Backend won't start (ModuleNotFoundError)
```powershell
cd backend
pip install -r requirements.txt
```

## Environment Variables

Set these before startup for custom behavior:

```powershell
$env:DATABASE_URL = "postgresql://user:pass@localhost:5432/wros_dev"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:CELERY_BROKER_URL = "redis://localhost:6379/0"
$env:ENVIRONMENT = "development"
```

## GitHub Actions / CI/CD Integration

**For production deployments, the startup sequence runs automatically via:**

```yaml
# .github/workflows/deploy.yml includes:
- Run: ./scripts/startup-production.ps1
- Verify: All services health checks pass
- Monitor: Services stay running during deployment
```

## Session Startup Command

**Add this to your development workflow:**

```powershell
# Start of day
.\scripts\startup-production.ps1

# Verify everything
curl http://localhost:8080/api/v1/config/queue-types

# Open browser tabs:
# - http://localhost:3000 (Frontend)
# - http://localhost:5555 (Flower)
# - http://localhost:8080/docs (Backend API Docs)
```

## Logs & Monitoring

Monitor startup progress:

```powershell
# Backend logs (shows startup sequence)
Get-Content $env:TEMP\backend.log -Tail 20 -Wait

# Celery worker logs
Get-Process python | Where-Object {$_.CommandLine -match "celery.*worker"}

# Flower status
curl http://localhost:5555/api/workers
```

## Daily Development Workflow

```powershell
# 1. Terminal 1: Run full startup
.\scripts\startup-production.ps1

# Wait 10 seconds for services to initialize

# 2. Terminal 2: Start frontend dev server
cd frontend
npm start

# 3. Open browser
# Frontend: http://localhost:3000
# Flower: http://localhost:5555
# API Docs: http://localhost:8080/docs
```

## Shutdown

To stop all services:

```powershell
# Method 1: Kill by port
netstat -ano | findstr :8080 | ForEach-Object { $PID = $_ -split '\s+' | Select-Object -Last 1; taskkill /F /PID $PID }
netstat -ano | findstr :5555 | ForEach-Object { $PID = $_ -split '\s+' | Select-Object -Last 1; taskkill /F /PID $PID }
netstat -ano | findstr :6379 | ForEach-Object { $PID = $_ -split '\s+' | Select-Object -Last 1; taskkill /F /PID $PID }

# Method 2: Close terminals (graceful shutdown)
# Ctrl+C in each terminal window
```

---

**Last Updated:** 2026-09-06  
**Status:** Production-ready startup sequence  
**Maintained By:** WROS Development Team
