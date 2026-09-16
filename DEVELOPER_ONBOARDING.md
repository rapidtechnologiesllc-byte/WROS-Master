# WROS Developer Onboarding Guide

Welcome to WROS development! This guide will get you up and running in 5 minutes.

## Quick Start (5 minutes)

### Prerequisites

Ensure you have installed:
- **Python 3.10+** - [Download](https://www.python.org/downloads/)
- **PostgreSQL 15+** - [Download](https://www.postgresql.org/download/)
- **Node.js 18+** - [Download](https://nodejs.org/)

### Start Local Environment

```powershell
# PowerShell (Windows)
cd C:\Users\YourName\Documents\Claude\WROS-Master
.\scripts\start-dev-local.ps1
```

This will:
1. ✅ Verify all prerequisites are installed
2. ✅ Create Python virtual environment (if needed)
3. ✅ Install dependencies
4. ✅ Start 2 services in separate terminal windows:
   - Backend (FastAPI on port 8081)
   - Frontend (React on port 3000)

**Access:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8081
- Health Check: http://localhost:8081/health

## Configuration

### Backend Environment (.env.local)

Copy `.env.local.template` to `.env.local`:

```bash
cd backend
cp .env.local.template .env.local
```

Edit `.env.local` to customize:
```bash
# Database
DATABASE_URL=postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/wros_dev

# Environment
ENVIRONMENT=development
```

**Important:** Never commit `.env.local` to git (it's in `.gitignore`).

### Frontend Environment (.env)

Frontend reads from `frontend/.env`:
```bash
REACT_APP_API_URL=http://localhost:8081
REACT_APP_ENV=development
```

## Port Configuration Reference

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| Frontend | 3000 | http://localhost:3000 | React web app |
| Backend | 8081 | http://localhost:8081 | FastAPI server |
| PostgreSQL | 5432 | localhost:5432 | Database |

## Manual Startup (Alternative)

If you prefer to start services manually:

**Terminal 1: Backend**
```bash
cd backend
python -m venv venv              # Create once
source venv/Scripts/activate     # Windows: venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8081
```

**Terminal 2: Frontend**
```bash
cd frontend
npm start
```

## Health Checks

### Backend Health Endpoint

```bash
curl http://localhost:8081/health
```

Expected response:
```json
{
    "status": "healthy",
    "app": "Onboarding Auth API",
    "version": "1.0.0"
}
```

### Verify All Services

1. **Frontend:** Open http://localhost:3000 in browser
2. **Backend:** `curl http://localhost:8081/health`
3. **Database:** `psql -U app_user -d wros_dev -c "SELECT 1;"`

## Troubleshooting

### Backend Won't Start

```bash
# Check if Python is installed
python --version

# Check if venv exists
ls backend/venv

# Manually create venv and install
cd backend
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt

# Try starting backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8081
```

### Frontend Won't Start

```bash
# Check if Node.js is installed
node --version

# Clear npm cache and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install
npm start
```

### Can't Connect to Database

```bash
# Verify PostgreSQL is running
# Windows: Check Services for "postgresql-x64-15"
# Linux: sudo systemctl status postgresql

# Test connection
psql -U postgres -c "SELECT 1;"

# Create dev database if missing
psql -U postgres -c "CREATE DATABASE wros_dev OWNER app_user;"
```


### Frontend Can't Reach Backend

1. Verify backend is running: `curl http://localhost:8081/health`
2. Check frontend `.env`: should have `REACT_APP_API_URL=http://localhost:8081`
3. Clear browser cache: Ctrl+Shift+Delete or Cmd+Shift+Delete
4. Hard refresh frontend: Ctrl+Shift+R or Cmd+Shift+R

## Development Workflow

### Make a Code Change

1. **Backend:** Edit file in `backend/app/` → auto-reloads
2. **Frontend:** Edit file in `frontend/src/` → auto-refreshes
3. **Database:** Changes via migrations (advanced)

### Run Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

### Database Migrations

```bash
cd backend

# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# View migration status
alembic current
```


## Git Workflow

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes and commit
git add .
git commit -m "feat: Add new feature"

# Push to remote
git push origin feature/my-feature

# Create Pull Request
# (GitHub UI or gh CLI)
```

## Architecture Overview

```
┌─────────────────────────────────────────┐
│  Frontend (React - localhost:3000)      │
│  - React components                     │
│  - API calls to backend                 │
└────────────┬────────────────────────────┘
             │ HTTP
┌────────────▼────────────────────────────┐
│  Backend (FastAPI - localhost:8081)     │
│  - REST API endpoints                   │
│  - Database queries                     │
│  - Business logic                       │
└────────────┬────────────────────────────┘
             │ SQL
┌────────────▼──────────────────────────┐
│ PostgreSQL (localhost:5432)            │
└────────────────────────────────────────┘
```

## Common Commands

```bash
# Project navigation
cd /path/to/WROS-Master/backend    # Backend directory
cd /path/to/WROS-Master/frontend   # Frontend directory

# Python/Backend
python -m uvicorn app.main:app --reload --port 8081
python -m pytest                                # Run tests
python -m black .                              # Format code
python -m pylint app/                          # Lint code

# JavaScript/Frontend
npm start                                       # Start dev server
npm test                                        # Run tests
npm run build                                   # Production build
npm run lint                                    # Lint code

# Git
git status                                      # Check status
git log --oneline -10                          # View recent commits
git diff                                        # View changes
git branch -a                                   # View branches

# Database
psql -U app_user -d wros_dev -c "SELECT 1;"   # Test connection
```

## IDE Setup (VS Code)

### Recommended Extensions

- Python (Microsoft)
- Pylance (Microsoft)
- ES7+ React/Redux/React-Native snippets (dsznajder)
- Prettier - Code formatter (Prettier)
- SQLTools (Sergio Xalambrí)

### Python Settings (.vscode/settings.json)

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/backend/venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true
}
```

### Launch Configuration (.vscode/launch.json)

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: FastAPI",
            "type": "python",
            "request": "launch",
            "module": "uvicorn",
            "args": ["app.main:app", "--reload", "--port", "8081"],
            "jinja": true,
            "cwd": "${workspaceFolder}/backend"
        }
    ]
}
```

## Getting Help

- **Backend issues:** Check `backend/app/main.py` startup logs
- **Frontend issues:** Check browser console (F12) for errors
- **Database issues:** Check PostgreSQL logs
- **Queue issues:** Check Redis and Celery worker logs

## Next Steps

1. ✅ Start the local environment (`.\scripts\start-dev-local.ps1`)
2. ✅ Verify all services are running
3. ✅ Create a test candidate in the frontend
4. ✅ Read the architecture docs (see DEPLOYMENT.md, LOCAL_DEVELOPMENT.md)
5. ✅ Start making changes!

## Production Deployment

See `DEPLOYMENT.md` for production setup with systemd services.

---

**Last Updated:** 2026-09-16  
**For Issues:** Check project documentation or ask the team
