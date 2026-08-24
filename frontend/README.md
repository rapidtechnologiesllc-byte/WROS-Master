# WROS - Workforce Revenue Operating System

**WROS** (Workforce Revenue Operating System) is BlitzenX's unified platform for managing recruitment, staffing, and resource allocation with integrated AI capabilities.

## Monorepo Structure

This is a **monorepo** containing all WROS services in a single repository:

```
WROS-Master/
├── backend/           # Python FastAPI - Core business logic & APIs (port 8080)
├── frontend/          # React - Web UI & Dashboard (port 3000 via Nginx)
├── careers/           # Careers service - Candidate portal & integration
├── .github/workflows/ # CI/CD automation (GitHub Actions)
└── .github/CODEOWNERS # Team-based code review routing
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 18
- Docker (optional)

### Local Development

#### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m alembic upgrade head  # Run migrations
python -m uvicorn app.main:app --reload  # Start server on :8080
```

#### Frontend Setup
```bash
cd frontend
npm install
REACT_APP_API_BASE_URL=http://localhost:8080 npm start  # Runs on :3000
```

#### Careers Setup
```bash
cd careers
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload  # Runs on :5000
```

### Database Setup

```bash
# Create database and user
psql -U postgres -c "CREATE DATABASE onboarding_prod;"
psql -U postgres -c "CREATE USER app_user WITH PASSWORD 'P7kQmR9xL2wJnV5sT8pM';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE onboarding_prod TO app_user;"

# Run migrations
cd backend
python -m alembic upgrade head
```

## Services

### Backend (port 8080)
- **Language:** Python 3.11
- **Framework:** FastAPI
- **Database:** PostgreSQL 18
- **Key features:**
  - 54+ RESTful APIs
  - Database migrations (Alembic)
  - JWT authentication
  - Role-based access control
  - Thunder AI integration

**Endpoints:**
- Health check: `GET /health`
- API docs: `GET /docs`

### Frontend (port 3000)
- **Language:** TypeScript/React 18
- **Framework:** React
- **UI Library:** Material-UI
- **Key features:**
  - Candidate portal
  - Interview scheduling
  - Resume management
  - Dashboard & analytics
  - Thunder AI integration

### Careers (port 5000)
- **Language:** Python 3.11
- **Integration:** Integrated with backend
- **Key features:**
  - Public job listings
  - Candidate conversations
  - Application tracking

## Deployment

### CI/CD Pipeline
Automated deployment on every push to `main`:
- Runs tests for changed services only
- Detects which services changed (smart deployment)
- Deploys backend, frontend, or careers independently
- Automatic health checks
- Automatic rollback on failure

### Production Deployment
Production server: `46.224.149.7:22587`

```bash
# Automated via GitHub Actions on push to main
git push origin main

# Or manual deployment
ssh -p 22587 HRMS@46.224.149.7
cd /home/HRMS/WROS-Master
git pull origin main
# Services auto-restart via CI/CD
```

## Code Isolation & Reviews

### Team Assignment (CODEOWNERS)
- Changes to `backend/` → assigned to `@backend-team`
- Changes to `frontend/` → assigned to `@frontend-team`
- Changes to `careers/` → assigned to `@careers-team`

### Branch Protection
Each service has independent branch protection:
- ✅ Require code review from Code Owners
- ✅ Require all status checks to pass
- ✅ Require branches up to date before merge

### Smart Deployment
Only changed services are tested and deployed:
```
Push with backend/ changes  → Backend tests & deploys, frontend/careers skip
Push with frontend/ changes → Frontend tests & deploys, backend/careers skip
Push with all changes       → All services test & deploy
```

## Testing

### Backend Tests
```bash
cd backend
pytest tests/regression_suite.py -v --cov=app
```

### Frontend Tests
```bash
cd frontend
npm test
```

### Careers Tests
```bash
cd careers
pytest tests/ -v
```

## Environment Variables

### Backend (.env or set via CI/CD)
```
DATABASE_URL=postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/onboarding_prod
BACKEND_PORT=8080
BACKEND_HOST=0.0.0.0
```

### Frontend (.env)
```
REACT_APP_API_BASE_URL=http://46.224.149.7:8080
```

### Careers (.env)
```
CAREERS_PORT=5000
DATABASE_URL=postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/onboarding_prod
```

## Troubleshooting

### Backend not starting
```bash
cd backend
# Check database connection
python -c "from sqlalchemy import create_engine; print(create_engine(os.getenv('DATABASE_URL')))"
# Check migrations
python -m alembic current
```

### Frontend build fails
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

### Port conflicts
```bash
# Check what's using ports
lsof -i :8080  # Backend
lsof -i :3000  # Frontend
lsof -i :5000  # Careers

# Kill if needed
kill -9 <PID>
```

## Documentation

- **[Hosting Provider Changes](./docs/HOSTING-PROVIDER-CHANGES.md)** - Infrastructure setup guide
- **[Code Isolation](./docs/MONOREPO-CODE-ISOLATION.md)** - Preventing cross-service merges
- **[CI/CD Pipeline](./docs/CI-CD-GUIDE.md)** - Deployment automation

## Contributing

1. **Create a feature branch:** `git checkout -b feature/your-feature`
2. **Make changes** in the appropriate service directory
3. **Run tests locally** before pushing
4. **Push and create PR:** `git push origin feature/your-feature`
5. **Wait for code review** from appropriate team (auto-assigned via CODEOWNERS)
6. **Merge when approved** - CI/CD runs tests and deploys automatically

## API Documentation

After backend is running, visit:
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

## Support

- **Issues:** Create GitHub issues in this repository
- **Discussions:** Use GitHub Discussions
- **Emergency:** Contact DevOps team on Slack

---

**Last Updated:** 2026-08-22  
**Maintainers:** BlitzenX DevOps Team
