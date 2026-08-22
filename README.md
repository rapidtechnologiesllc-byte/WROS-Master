# WROS - Workforce Revenue Operating System
## Master Repository

Monorepo containing the complete WROS system for BlitzenX.

### Structure

```
├── /backend       - FastAPI/Python backend (uvicorn) - 54+ APIs
├── /frontend      - React 18+ frontend (Nginx/static)
├── /career        - Career portal (React/Nginx)
└── .github/workflows/ - CI/CD pipelines
```

### Quick Start

```bash
# Clone the repository
git clone https://github.com/blitzenx25/WROS-Master.git
cd WROS-Master

# Setup and run
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
cd ../frontend && npm install && npm start
cd ../career && npm install && npm start
```

### Deployment

Automated CI/CD pipelines handle:
1. Frontend/Career build (Node.js → static files)
2. Backend build (Python → Docker image)
3. Deployment to production (Nginx + backend servers)

See `.github/workflows/deploy.yml` for details.

### Documentation

- **Backend**: `/backend/README.md`
- **Frontend**: `/frontend/README.md`
- **Career**: `/career/README.md`

### Tech Stack

- **Backend**: Python 3.x, FastAPI, PostgreSQL 18, SQLAlchemy
- **Frontend**: React 18+, JavaScript
- **Career**: React, JavaScript
- **Deployment**: Docker, Nginx, uvicorn

### License

BlitzenX Internal Use Only
