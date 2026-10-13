# Message Queue Testing - Quick Start Guide

**Get the message queue working in 15-20 minutes**

---

## TL;DR - Run These 4 Commands (in 4 separate terminals)

### Terminal 1: Setup Redis
```powershell
cd C:\dev\WROS-Master
./redis-setup.ps1
```
**Wait for:** "✅ REDIS READY TO USE"

---

### Terminal 2: Start Backend
```powershell
cd C:\dev\WROS-Master
./backend-startup-complete.ps1
```
**Wait for:** "Application startup complete"

**Keep this open!** (Don't close it)

---

### Terminal 3: Run Tests
```powershell
cd C:\dev\WROS-Master\backend
python test_queue_verification.py
```
**Wait for:** All tests to pass with checkmarks

---

### Terminal 4: Monitor Dashboard
Open in browser:
```
http://localhost:3000/queue-dashboard
```
**Watch for:** Queue items flowing from PENDING → COMPLETED

---

## What Should Happen

### Immediately After Starting (0-5 seconds)
- Redis script should verify Redis is running
- Backend script should show Celery worker starting
- Tests should connect to database

### During Tests (5-15 seconds)
- Tests create 3 test candidates
- Tests create 3 queue items
- Dashboard shows 3 PENDING items
- API endpoints responding

### After Tests (15-30 seconds)
- Celery worker processes queue items
- Items transition: PENDING → PROCESSING → COMPLETED
- Dashboard updates automatically
- All items marked COMPLETED

---

## Success Indicators

✅ **Terminal 1:** "✅ Redis PING successful"
✅ **Terminal 2:** "Application startup complete" + no errors
✅ **Terminal 3:** "✅ Total 3+ queue items in system"
✅ **Terminal 4:** Dashboard shows COMPLETED count ≥ 3

---

## If Something Goes Wrong

### Problem: "Command not found" or "script execution disabled"
```powershell
# Run this once to enable scripts:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Problem: "Redis is not found"
- Install from https://www.memurai.com/
- Or use Docker: `docker run -d -p 6379:6379 redis:latest`
- Rerun `./redis-setup.ps1`

### Problem: "Port 8080 already in use"
```powershell
netstat -ano | findstr :8080
taskkill /PID <PID> /F
```

### Problem: "Database connection failed"
- Make sure PostgreSQL is running
- Check `.env` file has correct DATABASE_URL

### Problem: Dashboard shows no data
- Hard refresh browser: Ctrl+Shift+R
- Check backend terminal (Terminal 2) for errors
- Verify API: `curl http://localhost:8080/queues/stats`

---

## Full Documentation

For detailed information:
- **Complete Setup Guide:** See `LOCAL_TESTING.md`
- **Verification Checklist:** See `VERIFY_QUEUE_WORKS.md`
- **Troubleshooting:** See `LOCAL_TESTING.md` → Troubleshooting section

---

## Architecture Overview

```
                    ┌─────────────┐
                    │   Redis     │ (Port 6379)
                    └──────▲──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   ┌─────────┐        ┌────────────┐    ┌─────────────┐
   │ FastAPI │        │   Celery   │    │ PostgreSQL  │
   │ Backend │◄──────►│   Worker   │◄──►│  Database   │
   │ (8080)  │        │            │    │             │
   └────▲────┘        └────────────┘    └─────────────┘
        │
        ▼
   ┌──────────────┐
   │  Dashboard   │ ← Watch queue items here
   │ (localhost   │
   │   :3000)     │
   └──────────────┘
```

**Flow:**
1. Tests create candidates in database
2. Tests create queue items (PENDING)
3. Celery worker picks them up
4. Worker marks as PROCESSING
5. Worker completes processing
6. Worker marks as COMPLETED
7. Dashboard shows real-time updates

---

## File References

| Script | Purpose | Terminal |
|--------|---------|----------|
| `redis-setup.ps1` | Setup & verify Redis | 1 |
| `backend-startup-complete.ps1` | Start FastAPI + Celery | 2 |
| `test_queue_verification.py` | Create test data | 3 |
| Dashboard | Monitor in real-time | 4 |

---

## Estimated Timings

| Step | Time | Status |
|------|------|--------|
| Redis Setup | 2-5 min | Wait for checkmark |
| Backend Start | 2-3 min | Wait for "startup complete" |
| Run Tests | 3-5 min | Wait for all tests to pass |
| Dashboard Check | 30 sec | Verify items are COMPLETED |
| **Total** | **15-20 min** | ✅ Ready to test |

---

## Quick Verification Commands

Test from any terminal to verify system health:

```powershell
# Check Redis
redis-cli ping
# Expected: PONG

# Check Backend
curl http://localhost:8080/docs
# Expected: HTML page (FastAPI docs)

# Check Queue Stats
curl http://localhost:8080/queues/stats
# Expected: JSON with queue statistics

# Check Database
cd backend
python -c "from app.core.database import SessionLocal; from app.models.channel_queue import ChannelQueueItem; db = SessionLocal(); print(f'Queue items: {db.query(ChannelQueueItem).count()}')"
# Expected: "Queue items: N" (N > 0)
```

---

## Common Issues & Quick Fixes

| Symptom | Fix |
|---------|-----|
| "Command not found: redis-cli" | Install Redis (Memurai) |
| "Port 8080 in use" | `taskkill /IM python.exe /F` |
| "Database connection failed" | Check PostgreSQL running |
| "Tests hang" | Ctrl+C, check all 3 services |
| "Dashboard empty" | Ctrl+Shift+R (hard refresh) |

---

## Next Steps After Verification

1. **Keep Everything Running**
   - Don't close the 3 terminals
   - Dashboard stays open for monitoring

2. **Test with More Data**
   ```powershell
   # Rerun tests multiple times
   cd backend
   python test_queue_verification.py
   ```

3. **Watch Real-Time Processing**
   - Keep dashboard open
   - See items flow from PENDING → COMPLETED

4. **Check Logs**
   ```powershell
   # See what Celery is doing
   type backend\celery-worker.log | tail -20
   ```

5. **Load Testing** (Optional)
   ```python
   # Modify test script to create 100+ items
   # Watch system performance
   ```

---

## Support & Troubleshooting

**For issues:**
1. Check `VERIFY_QUEUE_WORKS.md` checklist
2. See `LOCAL_TESTING.md` troubleshooting section
3. Check logs:
   - Backend Terminal 2
   - `backend/celery-worker.log`
   - Browser DevTools (F12)

---

**You're ready to test!** 🚀

Run the 4 commands above and watch the magic happen.
