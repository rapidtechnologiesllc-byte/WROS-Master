# Production Deployment Summary

## What Was Broken

The old deployment had critical production flaws:

```bash
# Old deploy.yml (broken approach):
nohup /path/to/python -m uvicorn app.main:app --port 8080 > /tmp/backend.log 2>&1 &

❌ Backend crashes → NOTHING restarts it
❌ System reboot → services don't start
❌ No process monitoring
❌ Logs deleted on reboot
❌ No Celery management
❌ Production immediate failure
```

---

## What's Fixed Now

### 1. Systemd Service Management

**Backend Service**
- ✅ Starts automatically on system boot
- ✅ Restarts on crash (rate limited)
- ✅ Centralized logging to `/var/log/wros/`
- ✅ Resource limits enforced
- ✅ Runs as non-root user

**Celery Worker Service**
- ✅ Starts automatically on system boot
- ✅ Restarts on crash
- ✅ 4 worker processes (configurable)
- ✅ Centralized logging
- ✅ Resource limits enforced

### 2. Automated Deployment

GitHub Actions now:
1. Builds frontend
2. Runs tests
3. SSH to production
4. Runs `production-deploy.sh` which:
   - Validates environment
   - Initializes database
   - Installs systemd services
   - Starts services
   - Verifies health

### 3. Database Initialization

Uses `db_contract.initialize_database()`:
- Creates all tables
- Initializes admin user
- Sets up RBAC roles & permissions
- Idempotent (safe every deployment)

---

## Deployment Comparison

| Feature | Before | After |
|---------|--------|-------|
| Auto-Start | ❌ No | ✅ Yes |
| Auto-Restart | ❌ No | ✅ Yes |
| System Reboot | ❌ Manual | ✅ Automatic |
| Logging | ❌ /tmp | ✅ /var/log/wros |
| Celery | ❌ Unmanaged | ✅ Managed |
| Health Checks | ❌ Manual | ✅ Automated |
| Monitoring | ❌ None | ✅ systemd |

---

## Production Setup Steps

### One-Time Setup

```bash
# 1. Create environment config
sudo mkdir -p /etc/wros
sudo nano /etc/wros/backend.env
# Add: DATABASE_URL, REDIS_URL, API keys, etc.

# 2. Create log directory
sudo mkdir -p /var/log/wros
sudo chown hrms:hrms /var/log/wros
sudo chmod 755 /var/log/wros

# 3. Verify PostgreSQL and Redis are running
psql -U app_user -d wros_prod -c "SELECT 1;"
redis-cli ping
```

### Deployment

Push to `main` branch:

```bash
git push origin main
```

GitHub Actions will:
1. Build and test
2. SSH to production server
3. Run `sudo bash production-deploy.sh`
4. Services will start/restart with new code

---

## Service Management

### Check Status

```bash
sudo systemctl status wros-backend.service
sudo systemctl status wros-celery-worker.service
```

### View Logs

```bash
# Real-time
sudo journalctl -u wros-backend.service -f

# Recent errors
tail -50 /var/log/wros/backend-error.log
```

### Restart

```bash
sudo systemctl restart wros-backend.service
```

### Stop

```bash
sudo systemctl stop wros-backend.service
sudo systemctl disable wros-backend.service
```

---

## Health Monitoring

### Backend Health Endpoint

```bash
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

### Check if Enabled

```bash
sudo systemctl is-enabled wros-backend.service
# Output: enabled
```

### Monitor Restart Count

```bash
sudo systemctl status wros-backend.service | grep "Restart"

# High count = crash loop
# Check logs: sudo journalctl -u wros-backend.service -n 100
```

---

## Troubleshooting

### Backend Won't Start

```bash
# Check logs
sudo journalctl -u wros-backend.service -n 100

# Verify database
psql -U app_user -d wros_prod -c "SELECT 1;"

# Verify Redis
redis-cli PING

# Manual run for debugging
cd /home/HRMS/WROS-Master/backend
/home/HRMS/WROS-Master/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### Celery Tasks Not Processing

```bash
# Check if running
sudo systemctl status wros-celery-worker.service

# Check queue
redis-cli LLEN celery

# View active tasks
celery -A app.celery_app inspect active
```

### Service Crashes Repeatedly

```bash
# Check resources
free -h
df -h

# Check error logs
tail -100 /var/log/wros/backend-error.log
```

---

## Performance Tuning

### More Backend Workers

Edit `/etc/systemd/system/wros-backend.service`:

```bash
sudo nano /etc/systemd/system/wros-backend.service

# Change: --workers 8

sudo systemctl daemon-reload
sudo systemctl restart wros-backend.service
```

### More Celery Workers

Edit `/etc/systemd/system/wros-celery-worker.service`:

```bash
sudo nano /etc/systemd/system/wros-celery-worker.service

# Change: --concurrency 8

sudo systemctl daemon-reload
sudo systemctl restart wros-celery-worker.service
```

---

## Local Development

For VPN users, use native setup (no Docker):

From `LOCAL_DEVELOPMENT.md`:

1. PostgreSQL on localhost:5432
2. Redis on localhost:6379
3. Backend: `python -m uvicorn app.main:app --reload --port 8081`
4. Frontend: `npm start`
5. Celery: `celery -A app.celery_app worker --loglevel=info`

---

## Deployment Files

### On Production Server

```
/etc/systemd/system/wros-backend.service
/etc/systemd/system/wros-celery-worker.service
/etc/wros/backend.env
/var/log/wros/
/home/HRMS/WROS-Master/backend/
```

### In Repository

```
backend/systemd/wros-backend.service
backend/systemd/wros-celery-worker.service
backend/scripts/production-deploy.sh
.github/workflows/deploy.yml
DEPLOYMENT.md
LOCAL_DEVELOPMENT.md
docker-compose.yml
PRODUCTION_SUMMARY.md (this file)
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Check status | `sudo systemctl status wros-backend.service` |
| View logs | `sudo journalctl -u wros-backend.service -f` |
| Restart | `sudo systemctl restart wros-backend.service` |
| Stop | `sudo systemctl stop wros-backend.service` |
| Health check | `curl http://localhost:8080/health` |
| Error logs | `tail /var/log/wros/backend-error.log` |
| Restart count | `systemctl status wros-backend.service \| grep Restart` |

---

**Status:** ✅ Production-Ready  
**Commit:** 28f5cec8  
**Last Updated:** 2026-09-15
