# Production Deployment Guide

## What Changed

**Latest Deployment (2026-08-19):**
- Navigation now shows **all 175 database resources** (previously only 10 hardcoded)
- Dynamic filtering by user RBAC permissions
- All 10 modules properly displayed
- Backend verification script ensures deployment succeeded

## How Deployment Works

### GitHub Actions CI/CD Pipeline

When code is pushed to `main` branch:

1. **Backend Tests** → Run pytest on all changes
2. **Backend Deploy** → SSH to production, pull latest, restart backend
3. **Backend Verification** → Run `verify_deployment.py` to confirm 175+ resources loaded
4. **Frontend Deploy** → Build and deploy static files
5. **Frontend Verification** → Ensure backend is responding

### What Gets Deployed

**Backend** (`/home/HRMS/OnboardingModule-Backend`):
- FastAPI app running on `localhost:8080` (port 8080)
- Nginx reverse proxy at `http://46.224.149.7:8080`
- PostgreSQL database at `localhost:5432`

**Frontend** (`/home/HRMS/HRMS-FE-V1/OnboardingModule-Frontend`):
- React app (static build files)
- Nginx serving at `https://hrms.blitzenx.com`
- Points to backend at `http://46.224.149.7:8080`

## Verification Commands

### Check Backend Health

```bash
curl http://46.224.149.7:8080/health
# Expected: {"status": "healthy", "app": "WROS", "version": "..."}
```

### Check Navigation Endpoint

```bash
# Login first to get JWT token
curl -X POST http://46.224.149.7:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "super_user@test.com", "password": "SuperUser123!"}'

# Then call navigation (replace TOKEN with JWT)
curl http://46.224.149.7:8080/hr/me/navigation \
  -H "Authorization: Bearer TOKEN"

# Expected: 10 modules with 175+ total resources
```

### Run Verification Script on Production

```bash
ssh -p 22587 user@46.224.149.7
cd /home/HRMS/OnboardingModule-Backend
python3 scripts/verify_deployment.py
# Expected: "SUCCESS: Deployment verified - production has dynamic navigation with 175+ resources"
```

## Troubleshooting

### Issue: 500 Internal Server Error

**Cause:** Backend crashed or not running

**Solution:**
```bash
ssh -p 22587 user@46.224.149.7
ps aux | grep uvicorn
# If no process: backend crashed
# Restart:
pkill -f uvicorn
sleep 1
cd /home/HRMS/OnboardingModule-Backend
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 > /tmp/backend.log 2>&1 &
# Check logs:
tail -f /tmp/backend.log
```

### Issue: Navigation shows only 10 items

**Cause:** Old code deployed (before Phase 2 dynamic navigation)

**Solution:**
```bash
ssh -p 22587 user@46.224.149.7
cd /home/HRMS/OnboardingModule-Backend
git log --oneline | head -1
# Should show: "feat: Add deployment verification..." or later
# If not, force redeploy:
git fetch origin
git reset --hard origin/main
python3 scripts/verify_deployment.py
```

### Issue: Frontend shows 404 or can't reach backend

**Cause:** Nginx not configured or backend URL wrong

**Solution:**
```bash
ssh -p 22587 user@46.224.149.7
# Check nginx config
cat /etc/nginx/sites-enabled/default | grep -A5 "api.blitzenx.com"
# Should point to: http://46.224.149.7:8080
# Or: http://localhost:8080 (if on same server)

# Check if nginx is running
systemctl status nginx
# Restart if needed:
systemctl restart nginx
```

## Deployment Checklist

- [ ] Code pushed to main branch on GitHub
- [ ] CI/CD workflow completes successfully
- [ ] Backend health check passes (`/health` endpoint responds)
- [ ] Verification script passes (175+ resources loaded)
- [ ] Frontend deploys successfully
- [ ] Frontend can reach backend (no 502 Bad Gateway)
- [ ] Super user can login and see all 10 modules in navigation
- [ ] Navigation shows 175+ resources (not 10 hardcoded items)

## Expected Results After Deployment

### For Super User (super_user@test.com)

**Navigation should show:**
- Admin (18 resources)
- Engagement (5 resources)
- Executive (4 resources)
- Finance (31 resources)
- Project Management (11 resources)
- Recruitment (41 resources)
- Reporting (13 resources)
- Sales (12 resources)
- System (14 resources)
- Workforce (28 resources)

**Total: 177 resources across 10 modules**

### For Other Roles

- Finance Manager: 6 modules (filtered by RBAC)
- Recruiter: 3 modules (filtered by RBAC)
- Employee: 2 modules (filtered by RBAC)

## Contact for Issues

- Deployment failures: Check GitHub Actions logs
- Backend errors: SSH and check `/tmp/backend.log`
- Navigation issues: Run `verify_deployment.py` script
- Database issues: Check PostgreSQL is running on `:5432`

## Version Info

- Backend: FastAPI with PostgreSQL
- Frontend: React with Nginx
- Database: PostgreSQL 18
- Deployment: GitHub Actions CI/CD
- Last Updated: 2026-08-19
