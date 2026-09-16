# WROS Production Deployment Guide

This document describes how WROS is deployed to production with automatic startup, health monitoring, and crash recovery.

## Production Architecture

### Service Management (systemd)

Both backend and Celery worker are managed by **systemd** for automatic startup and crash recovery:

- **wros-backend.service** - Uvicorn + FastAPI HTTP server (Port 8080)
- **wros-celery-worker.service** - Celery background task worker

#### Service Lifecycle

```
System Boot
    ↓
systemd reads /etc/systemd/system/wros-*.service
    ↓
Starts services (all dependencies met)
    ↓
Services running normally
    ↓
[Crash] → systemd detects → waits 10s → Restart=always → Service restarts
```

---

## Deployment Process

### Files Created

- `backend/systemd/wros-backend.service` - Backend systemd service
- `backend/systemd/wros-celery-worker.service` - Celery worker systemd service
- `backend/scripts/production-deploy.sh` - Deployment automation script
- `docker-compose.yml` - Local development environment
- `DEPLOYMENT.md` - This documentation

### Updated Files

- `.github/workflows/deploy.yml` - Now uses production-deploy.sh instead of manual nohup

---

## Key Improvements

### Before (Broken in Production)

```bash
# Old deploy.yml used nohup - no auto-restart on crash
nohup /path/to/python -m uvicorn app.main:app ... > /tmp/backend.log 2>&1 &

# Problems:
# ❌ If backend crashes, nothing restarts it
# ❌ No health monitoring
# ❌ No logging infrastructure
# ❌ Manual intervention required
# ❌ No process management
```

### After (Production-Ready)

```bash
# New deploy.yml runs production-deploy.sh
# Which installs systemd services for automatic management

# Features:
# ✅ Auto-restart on crash (within rate limits)
# ✅ Auto-start on system boot
# ✅ Centralized logging to /var/log/wros/
# ✅ Health checks integrated
# ✅ Zero manual intervention needed
# ✅ Complete process supervision
```

---

## How It Works

### On System Boot

1. systemd reads service files from `/etc/systemd/system/`
2. Detects dependencies (PostgreSQL, Redis)
3. Starts services in order:
   - Backend (Uvicorn + FastAPI)
   - Celery Worker (background tasks)
4. Monitors processes continuously

### On Service Crash

1. systemd detects process exit
2. Waits 10 seconds (RestartSec=10)
3. Restarts service automatically
4. Repeats up to 5 times per 600 seconds (restart rate limit)
5. If reaches limit, stops trying until manual restart

### On Deployment

1. GitHub Actions triggers on push to `main`
2. Builds frontend, runs tests
3. SSH to production, runs `production-deploy.sh`
4. Script:
   - Stops old services
   - Installs new code
   - Initializes database
   - Installs/updates systemd services
   - Starts services
   - Runs health checks
5. Services running with new code

---

## Service Management

### View Status

```bash
# Backend service
sudo systemctl status wros-backend.service

# Celery worker
sudo systemctl status wros-celery-worker.service
```

### View Logs

```bash
# Real-time backend logs
sudo journalctl -u wros-backend.service -f

# Real-time Celery logs
sudo journalctl -u wros-celery-worker.service -f

# Error logs
tail /var/log/wros/backend-error.log
tail /var/log/wros/celery-worker-error.log
```

### Restart Services

```bash
sudo systemctl restart wros-backend.service
sudo systemctl restart wros-celery-worker.service
```

---

## Health Checks

### Backend Health Endpoint

```bash
curl http://localhost:8080/health
# Expected: { "status": "healthy", "database": "connected", "redis": "connected" }
```

### Service Status

```bash
# Check if running
sudo systemctl is-active wros-backend.service
# Output: active

# Check if enabled on boot
sudo systemctl is-enabled wros-backend.service
# Output: enabled
```

---

## Local Development

### Using Docker Compose

```bash
# Start all services (production-like setup)
docker-compose up -d

# Services:
# - Frontend: http://localhost:3000
# - Backend: http://localhost:8081
# - Nginx: http://localhost:80
# - PostgreSQL: localhost:5432
# - Redis: localhost:6379

# Stop services
docker-compose down
```

---

## Troubleshooting

### Backend Won't Start

```bash
# Check logs
sudo journalctl -u wros-backend.service -n 100

# Verify database connection
psql -U app_user -d wros_prod -c "SELECT 1;"

# Verify Redis
redis-cli ping

# Manual start for debugging
cd /home/HRMS/WROS-Master/backend
/home/HRMS/WROS-Master/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### Celery Not Processing Tasks

```bash
# Check if running
sudo systemctl status wros-celery-worker.service

# Verify Redis
redis-cli PING

# Check queue depth
redis-cli LLEN celery
```

### Service Crashes Repeatedly

```bash
# Check system resources
free -h
df -h
top

# View error logs
tail -100 /var/log/wros/backend-error.log
tail -100 /var/log/wros/celery-worker-error.log
```

---

## Performance Configuration

### Increase Uvicorn Workers

Edit `/etc/systemd/system/wros-backend.service`:

```bash
# Change --workers parameter from 4 to 8
ExecStart=... --workers 8

# Apply changes
sudo systemctl daemon-reload
sudo systemctl restart wros-backend.service
```

### Increase Celery Concurrency

Edit `/etc/systemd/system/wros-celery-worker.service`:

```bash
# Change --concurrency from 4 to 8
ExecStart=... --concurrency=8

# Apply changes
sudo systemctl daemon-reload
sudo systemctl restart wros-celery-worker.service
```

---

## Production Checklist

Before going live:

- [ ] Environment configured in `/etc/wros/backend.env`
- [ ] PostgreSQL 15+ running
- [ ] Redis 7+ running
- [ ] Nginx configured to proxy to backend
- [ ] HTTPS/TLS installed
- [ ] `production-deploy.sh` runs successfully
- [ ] Health checks passing
- [ ] Services enabled (`systemctl enable wros-*.service`)
- [ ] Logging and monitoring setup
- [ ] Database backups configured

---

**Last Updated:** 2026-09-15
**Status:** ✅ Production-Ready
