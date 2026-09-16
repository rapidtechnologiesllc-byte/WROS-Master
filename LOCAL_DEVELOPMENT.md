# Local Development Setup (Without Docker)

For development when using VPN or if Docker networking is problematic.

## Option 1: Native Local Setup (Recommended for VPN)

### Prerequisites

- **Python 3.10+** - `python --version`
- **PostgreSQL 15+** - Download from [postgresql.org](https://www.postgresql.org/download/)
- **Redis 7+** - Download from [redis.io](https://redis.io/download) or use WSL on Windows
- **Node.js 18+** - `node --version`
- **Git** - `git --version`

### Setup Steps

#### 1. PostgreSQL Setup

```bash
# Windows: Use PostgreSQL installer
# After installation, PostgreSQL runs as a service on localhost:5432

# Verify connection
psql -U postgres -c "SELECT 1;"

# Create development database
psql -U postgres -c "CREATE USER app_user WITH PASSWORD 'P7kQmR9xL2wJnV5sT8pM';"
psql -U postgres -c "CREATE DATABASE wros_dev OWNER app_user;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE wros_dev TO app_user;"

# Test connection
psql -U app_user -d wros_dev -c "SELECT 1;"
```

#### 2. Redis Setup (Windows)

**Option A: WSL2 (Windows Subsystem for Linux)**

```bash
# In WSL2 terminal
sudo apt-get update
sudo apt-get install redis-server

# Start Redis
redis-server

# In another terminal, verify
redis-cli ping
# Expected: PONG
```

**Option B: Windows Native**

Download Redis for Windows from: https://github.com/microsoftarchive/redis/releases

```bash
# Extract and run
redis-server.exe
```

#### 3. Backend Setup

```bash
# Navigate to backend
cd backend

# Create and activate Python venv
python -m venv venv

# Windows: Activate venv
venv\Scripts\activate

# Linux/Mac: Activate venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from app.core.db_contract import initialize_database; initialize_database()"

# Start backend server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8081
```

Backend runs at: http://localhost:8081

#### 4. Frontend Setup

```bash
# In new terminal, navigate to frontend
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

Frontend runs at: http://localhost:3000

#### 5. Celery Worker (Background Tasks)

```bash
# In new terminal, navigate to backend
cd backend

# Activate venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Start Celery worker
celery -A app.celery_app worker --loglevel=info
```

### Running Locally (Quick Start)

**Terminal 1: PostgreSQL** (if not running as service)
```bash
# WSL
redis-server
```

**Terminal 2: Backend**
```bash
cd backend
source venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8081
```

**Terminal 3: Celery**
```bash
cd backend
source venv/bin/activate
celery -A app.celery_app worker --loglevel=info
```

**Terminal 4: Frontend**
```bash
cd frontend
npm start
```

### Verify Everything Works

```bash
# Backend health check
curl http://localhost:8081/health

# Expected response:
# {
#   "status": "healthy",
#   "database": "connected",
#   "redis": "connected"
# }

# Frontend should load at http://localhost:3000
```

---

## Option 2: Docker Compose with VPN Workarounds

If you want to use Docker Compose despite VPN:

### Docker Compose Network Fixes

Edit `docker-compose.yml` to add VPN-friendly network configuration:

```yaml
services:
  postgres:
    networks:
      - wros
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      # ... existing config ...

  redis:
    networks:
      - wros
    extra_hosts:
      - "host.docker.internal:host-gateway"

  backend:
    networks:
      - wros
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      # Use 'host.docker.internal' if services are on host
      DATABASE_URL: postgresql://app_user:password@postgres:5432/wros_dev
      REDIS_URL: redis://redis:6379/0

networks:
  wros:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.name: br_wros
      # Disable userland proxy if having VPN issues
      com.docker.driver.mtu: 1450  # Adjust if needed for VPN
```

### Start Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop all services
docker-compose down
```

### If Docker Still Has Issues

**Disable Docker Desktop VPN integration:**
1. Open Docker Desktop Settings
2. Go to Resources → Network
3. Disable "Use VPN-friendly networking" if present
4. Restart Docker

**Or run containers individually:**

```bash
# PostgreSQL only
docker run -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:15

# Redis only
docker run -p 6379:6379 redis:7

# Backend
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8081

# Frontend
cd frontend
npm start
```

---

## Environment Variables (.env)

### Backend (.env)

Create `backend/.env`:

```bash
DATABASE_URL=postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/wros_dev
REDIS_URL=redis://localhost:6379/0
ENVIRONMENT=development
PYTHONUNBUFFERED=1
```

### Frontend (.env)

Create `frontend/.env`:

```bash
REACT_APP_API_URL=http://localhost:8081
REACT_APP_ENV=development
```

---

## Troubleshooting

### PostgreSQL Connection Issues

```bash
# Check if PostgreSQL is running
# Windows: Services → postgres
# Linux: sudo systemctl status postgresql

# Test connection
psql -U app_user -d wros_dev -c "SELECT 1;"

# If connection refused on localhost:5432
# Check PostgreSQL is listening
psql -U postgres -l

# Reset password if needed
psql -U postgres -c "ALTER USER app_user WITH PASSWORD 'P7kQmR9xL2wJnV5sT8pM';"
```

### Redis Connection Issues

```bash
# Check if Redis is running
redis-cli ping
# Expected: PONG

# If connection refused
# Windows: Check redis-server.exe is running
# Linux: sudo systemctl status redis-server
# WSL: redis-server is running in WSL terminal

# Verify Redis can be accessed from host
redis-cli -h 127.0.0.1 ping
```

### Backend Won't Connect to Database

```bash
# Verify DATABASE_URL in backend/.env
cat backend/.env

# Test connection manually
python -c "
from sqlalchemy import create_engine
engine = create_engine('postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/wros_dev')
print(engine.connect())
"

# Check database exists
psql -U app_user -l
```

### Celery Tasks Not Processing

```bash
# Verify Redis is running
redis-cli PING

# Check queue depth
redis-cli LLEN celery

# Verify Celery worker is running
# Check terminal where celery command is running

# View active tasks
celery -A app.celery_app inspect active

# Check Celery logs for errors
```

### Frontend Can't Reach Backend API

```bash
# Verify backend is running
curl http://localhost:8081/health

# Check frontend .env
cat frontend/.env
# REACT_APP_API_URL should be http://localhost:8081

# Clear browser cache and hard refresh (Ctrl+Shift+R)

# Check browser console for CORS errors
# Open DevTools → Console → Check for errors
```

---

## Recommended Setup for VPN Users

Use **Option 1: Native Local Setup** because:

✅ No Docker networking issues with VPN  
✅ Services run on localhost directly  
✅ Easier to debug and monitor  
✅ Better performance (no Docker overhead)  
✅ Simpler to manage  

### Quick Start Script (Windows PowerShell)

Create `start-dev.ps1`:

```powershell
# Start Redis (in WSL or native)
Write-Host "Starting Redis..." -ForegroundColor Green
redis-cli ping > $null 2>&1
if ($?) { Write-Host "✓ Redis is running" } else { Write-Host "✗ Redis not found - start it manually" }

# Start Backend
Write-Host "Starting Backend..." -ForegroundColor Green
Start-Job -ScriptBlock {
    cd backend
    .\venv\Scripts\Activate.ps1
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8081
} -Name "backend"

# Start Frontend
Write-Host "Starting Frontend..." -ForegroundColor Green
Start-Job -ScriptBlock {
    cd frontend
    npm start
} -Name "frontend"

# Wait for services
Start-Sleep -Seconds 5
Write-Host ""
Write-Host "✓ Services started!" -ForegroundColor Green
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "Backend: http://localhost:8081" -ForegroundColor Cyan
Write-Host "Backend Health: curl http://localhost:8081/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop services: Stop-Job -Name backend, frontend" -ForegroundColor Yellow
```

Run with:
```powershell
.\start-dev.ps1
```

---

## Production Still Uses Systemd

Remember:
- **Local Development:** Use native setup (no Docker)
- **Production Deployment:** Uses systemd services (production-deploy.sh)

The systemd setup is independent of local development choice.

---

**Last Updated:** 2026-09-15  
**Recommended for VPN:** Native Local Setup (Option 1)
