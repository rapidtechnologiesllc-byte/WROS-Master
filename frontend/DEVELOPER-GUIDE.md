# WROS Monorepo - Developer Guide

Welcome to the WROS (Workforce Revenue Operating System) monorepo! This guide covers everything you need to get started, whether you're working on backend, frontend, or careers services.

## Table of Contents
1. [Quick Start (5 minutes)](#quick-start)
2. [Full Setup (30 minutes)](#full-setup)
3. [Working with Services](#working-with-services)
4. [Git Workflow](#git-workflow)
5. [Testing & Deployment](#testing--deployment)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### For Everyone: Clone & Install

```bash
# Clone the repo
git clone https://github.com/rapidtechnologiesllc-byte/WROS-Master.git
cd WROS-Master

# Copy environment template
cp .env.example .env

# Install your service (choose one or do all)
```

### Backend Developers Only
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
# Backend ready at http://localhost:8080
# API docs at http://localhost:8080/docs
```

### Frontend Developers Only
```bash
cd frontend
npm install
npm start
# Frontend ready at http://localhost:3000
# Auto-connects to backend at http://localhost:8080
```

### Careers Developers Only
```bash
cd careers
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 5000
# Careers ready at http://localhost:5000
```

---

## Full Setup

### Prerequisites
- **Git** (with SSH key configured for GitHub)
- **Python 3.11+** (for backend & careers)
- **Node.js 18+** (for frontend)
- **PostgreSQL 18** (local or Docker)

### Step 1: Database Setup

**Option A: Local PostgreSQL**
```bash
# Create database
psql -U postgres -c "CREATE DATABASE onboarding_prod;"

# Create user
psql -U postgres -c "CREATE USER app_user WITH PASSWORD 'P7kQmR9xL2wJnV5sT8pM';"

# Grant permissions
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE onboarding_prod TO app_user;"

# Verify connection
psql -U app_user -d onboarding_prod -c "SELECT 1;"
```

**Option B: Docker PostgreSQL**
```bash
docker run -d \
  --name wros-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=onboarding_prod \
  -p 5432:5432 \
  postgres:18
```

### Step 2: Clone Repository

```bash
git clone https://github.com/rapidtechnologiesllc-byte/WROS-Master.git
cd WROS-Master
cp .env.example .env
```

### Step 3: Backend Setup (for all developers)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
python -m alembic upgrade head

# Verify setup
python -c "from app.main import app; print('✅ Backend imports successful')"
```

### Step 4: Frontend Setup (for all developers)

```bash
cd ../frontend

# Install dependencies
npm install

# Verify setup
npm run build --dry-run
echo "✅ Frontend setup successful"
```

### Step 5: Verify Everything

```bash
# Terminal 1: Backend
cd backend
python -m uvicorn app.main:app --reload

# Terminal 2: Frontend
cd frontend
npm start

# Terminal 3: Test API
curl http://localhost:8080/health
# Expected: {"status": "healthy"}

# Open browser
open http://localhost:3000
```

---

## Working with Services

### Service Boundaries

Each service owns its directory and dependencies:

**Backend** (`backend/`)
- Language: Python 3.11
- Framework: FastAPI
- Owns: API logic, database models, migrations
- Port: 8080
- Database: PostgreSQL (app_user)

**Frontend** (`frontend/`)
- Language: TypeScript/React 18
- Owns: UI, routing, state management
- Port: 3000
- Communicates with: Backend API at `:8080`

**Careers** (`careers/`)
- Language: Python 3.11
- Owns: Public careers portal, job listings
- Port: 5000
- Communicates with: Backend API

### Code Organization

```
backend/
├── app/
│   ├── main.py          # FastAPI app initialization
│   ├── models/          # SQLAlchemy models
│   ├── services/        # Business logic
│   ├── routes/          # API endpoints
│   └── core/            # Configuration, auth
├── alembic/             # Database migrations
├── tests/               # Regression test suite
└── requirements.txt     # Dependencies

frontend/
├── src/
│   ├── components/      # React components
│   ├── pages/           # Page routes
│   ├── services/        # API calls
│   ├── hooks/           # Custom hooks
│   └── App.tsx          # Root component
├── public/              # Static assets
└── package.json         # Dependencies

careers/
├── app/
│   ├── main.py          # FastAPI app
│   ├── models/          # Data models
│   ├── routes/          # API endpoints
│   └── services/        # Business logic
├── tests/               # Tests
└── requirements.txt     # Dependencies
```

---

## Git Workflow

### 1. Create a Feature Branch

```bash
# For backend work
git checkout -b feature/backend-add-user-endpoint

# For frontend work
git checkout -b feature/frontend-add-dashboard

# For careers work
git checkout -b feature/careers-job-listings
```

**Branch naming convention:**
- `feature/backend-<description>` - Backend changes
- `feature/frontend-<description>` - Frontend changes
- `feature/careers-<description>` - Careers changes
- `bugfix/<description>` - Bug fixes
- `docs/<description>` - Documentation

### 2. Make Changes

```bash
# Edit files in your service directory
# Example: backend/app/routes/users.py

# Commit frequently (small, logical commits)
git add backend/app/routes/users.py
git commit -m "feat: Add get_user endpoint"
```

### 3. Push & Create PR

```bash
git push origin feature/backend-add-user-endpoint

# Create pull request on GitHub
# Title should be descriptive, not long
# Description: explain WHAT and WHY
```

### 4. Code Review

**What to expect:**
- Team assignment is automatic (CODEOWNERS)
  - Backend changes → @backend-team reviews
  - Frontend changes → @frontend-team reviews
  - Careers changes → @careers-team reviews
- Must have approval before merge
- CI/CD runs tests automatically

### 5. Merge & Deploy

Once approved:
```bash
# GitHub: Click "Merge pull request"
# CI/CD automatically:
# 1. Runs tests for your service only
# 2. If tests pass, deploys to production
# 3. If tests fail, blocks deployment
# 4. Auto-rolls back on failure
```

---

## Testing & Deployment

### Local Testing (Before Pushing)

**Backend:**
```bash
cd backend
pytest tests/regression_suite.py -v
# Must pass before creating PR
```

**Frontend:**
```bash
cd frontend
npm test
npm run build  # Verify production build works
```

**Careers:**
```bash
cd careers
pytest tests/ -v
```

### Automated Testing (On Push)

When you push, GitHub Actions automatically:
1. Detects which services you changed
2. Runs tests for ONLY those services
3. If all tests pass → deploys
4. If tests fail → blocks merge

**Example:**
```
Push with backend/ changes
├─ ✅ Backend tests run
├─ ⏭️  Frontend tests SKIPPED (no changes)
├─ ⏭️  Careers tests SKIPPED (no changes)
└─ Deploy backend only (frontend/careers untouched)
```

### Manual Deployment (Rarely Needed)

Production server: `46.224.149.7` (SSH port 22587)

```bash
# Deployment happens automatically via CI/CD
# But if you need to manually:

ssh -p 22587 HRMS@46.224.149.7
cd /home/HRMS/WROS-Master
git pull origin main

# Services auto-restart
# Check status:
curl http://46.224.149.7:8080/health
```

---

## Common Tasks

### Backend: Add a New API Endpoint

1. Create route file: `backend/app/routes/new_feature.py`
   ```python
   from fastapi import APIRouter
   router = APIRouter()
   
   @router.get("/new-endpoint")
   def get_new_endpoint():
       return {"status": "success"}
   ```

2. Register in `backend/app/main.py`
   ```python
   from app.routes.new_feature import router
   app.include_router(router)
   ```

3. Test locally:
   ```bash
   curl http://localhost:8080/new-endpoint
   ```

4. Add test in `backend/tests/`
5. Push and create PR

### Backend: Add Database Migration

1. Create model in `backend/app/models/`
2. Create migration:
   ```bash
   cd backend
   python -m alembic revision --autogenerate -m "Add new_table table"
   ```

3. Review generated migration in `backend/alembic/versions/`
4. Test locally:
   ```bash
   python -m alembic upgrade head
   ```

5. Push and PR

### Frontend: Add a New Page

1. Create component: `frontend/src/pages/NewPage.tsx`
2. Add route in `frontend/src/App.tsx`
3. Test locally:
   ```bash
   npm start
   # Navigate to new page in browser
   ```

4. Push and PR

### Frontend: Add API Call

1. Create service: `frontend/src/services/newFeatureService.ts`
   ```typescript
   const BASE_URL = process.env.REACT_APP_API_BASE_URL;
   
   export const getNewFeature = async () => {
     const response = await fetch(`${BASE_URL}/new-endpoint`);
     return response.json();
   };
   ```

2. Use in component:
   ```typescript
   import { getNewFeature } from '../services/newFeatureService';
   
   useEffect(() => {
     getNewFeature().then(setData);
   }, []);
   ```

3. Test with backend running
4. Push and PR

---

## Troubleshooting

### Backend Won't Start

```bash
cd backend

# Check Python version
python --version  # Should be 3.11+

# Check dependencies
pip list | grep fastapi

# Check database connection
python -c "import os; print(os.getenv('DATABASE_URL'))"

# Manually test connection
psql postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/onboarding_prod -c "SELECT 1;"

# Check migrations
python -m alembic current

# Check for import errors
python -c "from app.main import app; print('OK')"

# Try starting
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### Frontend Build Fails

```bash
cd frontend

# Clear cache
rm -rf node_modules package-lock.json

# Reinstall
npm install

# Try build
npm run build

# Check logs
npm run build -- --verbose
```

### Port Already In Use

```bash
# Find what's using port 8080
lsof -i :8080

# Kill the process
kill -9 <PID>

# Try again
python -m uvicorn app.main:app --reload --port 8080
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
# On Mac/Linux:
ps aux | grep postgres

# On Docker:
docker ps | grep postgres

# Test connection
psql -U app_user -d onboarding_prod -h localhost -c "SELECT 1;"

# If fails, check .env has:
# DATABASE_URL=postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/onboarding_prod
```

### Git/GitHub Issues

```bash
# Check SSH key is configured
ssh -T git@github.com

# If fails, add SSH key:
ssh-keygen -t ed25519 -C "your-email@example.com"
# Then add public key to GitHub Settings → SSH Keys

# Pull latest from main
git fetch origin
git rebase origin/main

# Push your branch
git push origin feature/your-feature
```

---

## Environment Setup Checklist

- [ ] Python 3.11+ installed
- [ ] Node.js 18+ installed
- [ ] PostgreSQL 18 running (local or Docker)
- [ ] SSH key configured for GitHub
- [ ] Repository cloned
- [ ] `.env` file created (from `.env.example`)
- [ ] Backend: `pip install -r requirements.txt`
- [ ] Backend: `python -m alembic upgrade head`
- [ ] Frontend: `npm install`
- [ ] Backend test: `curl http://localhost:8080/health` → ✅ healthy
- [ ] Frontend test: `npm start` → ✅ runs on :3000
- [ ] CI/CD secrets configured on GitHub (PROD_SERVER_HOST, PROD_USER, PROD_SSH_KEY)

---

## Getting Help

### For Backend Questions
- Slack: #wros-backend
- Docs: `/backend/README.md`
- API Docs: http://localhost:8080/docs

### For Frontend Questions
- Slack: #wros-frontend
- Component Library: Storybook (if configured)

### For Careers Questions
- Slack: #wros-careers
- Docs: `/careers/README.md`

### For DevOps/CI-CD Questions
- Slack: #devops
- Docs: This guide + `.github/workflows/test-and-deploy.yml`

---

## Quick Reference

| Task | Command |
|------|---------|
| Start backend | `cd backend && python -m uvicorn app.main:app --reload` |
| Start frontend | `cd frontend && npm start` |
| Run backend tests | `cd backend && pytest tests/ -v` |
| Run frontend tests | `cd frontend && npm test` |
| Database migrations | `cd backend && python -m alembic upgrade head` |
| Create migration | `cd backend && python -m alembic revision --autogenerate -m "message"` |
| Build frontend | `cd frontend && npm run build` |
| Check API docs | Visit `http://localhost:8080/docs` |
| Check test coverage | `cd backend && pytest --cov=app` |

---

**Welcome to WROS! Happy coding! 🚀**

For updates to this guide or to report issues, please create a PR to `DEVELOPER-GUIDE.md`.

Last updated: 2026-08-22
