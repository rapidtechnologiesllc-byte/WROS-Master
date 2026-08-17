# Database Configuration Guide - Phase 2 Compliance

**Zero-Hardcoding Principle:** All database configuration must be environment-driven. No hardcoded connection strings, credentials, or database details in code.

---

## Quick Start

### Development Environment
```bash
# .env.local (never commit this file)
DATABASE_URL=postgresql://postgres:password@localhost:5432/wros_dev
```

### Staging Environment
```bash
# Set via environment variable
export DATABASE_URL=postgresql://user:password@staging-db.company.com:5432/wros_staging
python -m uvicorn app.main:app
```

### Production Environment
```bash
# Set via deployment platform (systemd, Docker, Kubernetes, etc.)
# NEVER hardcode in .env files
# Use secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)

# systemd example:
# /etc/systemd/system/wros-backend.service
# Environment="DATABASE_URL=postgresql://user:password@prod-db.company.com:5432/wros_prod"

# Docker example:
# docker run -e DATABASE_URL="postgresql://..." image_name

# Kubernetes example:
# kubectl set env deployment/wros DATABASE_URL="postgresql://..."
```

---

## Database Configuration Rules

### Rule 1: Environment Variable Only
**✅ DO:**
```python
DATABASE_URL = os.getenv("DATABASE_URL")
```

**❌ DON'T:**
```python
DATABASE_URL = "postgresql://localhost:5432/db"  # Hardcoding
DATABASE_URL = "postgresql://user:password@prod-db.com/db"  # Credentials in code
```

### Rule 2: PostgreSQL Only
**✅ ACCEPT:**
```
postgresql://username:password@host:5432/database
```

**❌ REJECT:**
```
sqlite:///./local.db           # SQLite not supported
mssql+pyodbc://server/db       # SQL Server not supported
mysql://user:pass@host/db      # MySQL not supported
```

### Rule 3: Validation at Startup
**Application enforces:**
- DATABASE_URL must be set (error if missing)
- Must start with `postgresql://` (error if different)
- Must be valid SQLAlchemy connection string

### Rule 4: No .env Files in Git
**.gitignore enforcement:**
```
.env
.env.local
.env.*.local
```

**Repository contains:**
```
✅ .env.production.template  (example only, NO credentials)
✅ README with setup instructions
✅ Documentation on how to set DATABASE_URL

❌ .env files with actual credentials
❌ Hardcoded connection strings
❌ Example databases with real passwords
```

---

## Environment-Specific Configuration

### Development Setup

**File:** `.env.local` (don't commit)
```bash
DATABASE_URL=postgresql://postgres:dev_password@localhost:5432/wros_dev
DEBUG=True
LOG_LEVEL=DEBUG
```

**Setup script:**
```bash
#!/bin/bash
# setup-dev-db.sh

# Create development database
psql -U postgres -c "CREATE DATABASE wros_dev;"
psql -U postgres -c "CREATE USER wros WITH PASSWORD 'dev_password';"
psql -U postgres -c "ALTER USER wros SUPERUSER;"

# Load schema
python -m alembic upgrade head

# Seed initial data (if applicable)
python scripts/seed_database.py
```

### Staging Deployment

**Via environment variable:**
```bash
# Deploy to staging
export DATABASE_URL="postgresql://staging_user:secure_password@staging-pg.company.com:5432/wros_staging"
export APP_ENV=staging
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Via Docker:**
```dockerfile
FROM python:3.12

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app/ app/

# DATABASE_URL must be provided at runtime
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Run:**
```bash
docker run -e DATABASE_URL="postgresql://..." image_name
```

### Production Deployment

**Via systemd:**
```ini
[Unit]
Description=WROS Backend Service
After=network.target postgresql.service

[Service]
Type=notify
User=wros
WorkingDirectory=/opt/wros
EnvironmentFile=/opt/wros/secrets/wros.env
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

[Install]
WantedBy=multi-user.target
```

**Secrets file** `/opt/wros/secrets/wros.env` (restricted permissions):
```bash
# chmod 600 /opt/wros/secrets/wros.env
DATABASE_URL=postgresql://prod_user:very_secure_password@prod-pg-1.company.com:5432/wros_prod
```

**Via Kubernetes:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: wros-db-secret
type: Opaque
stringData:
  database-url: postgresql://prod_user:password@prod-pg.company.com:5432/wros_prod

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: wros-backend
spec:
  template:
    spec:
      containers:
      - name: backend
        image: wros-backend:latest
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: wros-db-secret
              key: database-url
```

---

## Connection String Format

### Standard Format
```
postgresql://username:password@host:port/database_name
```

### With SSL
```
postgresql://username:password@host:port/database_name?sslmode=require
```

### With Connection Options
```
postgresql://username:password@host:port/database_name?
  sslmode=require&
  connect_timeout=10&
  application_name=wros_backend
```

### Examples

**Local development:**
```
postgresql://postgres:password@localhost:5432/wros_dev
```

**AWS RDS:**
```
postgresql://wros_user:secure_password@wros-db.c123abc.us-east-1.rds.amazonaws.com:5432/wros_prod
```

**Google Cloud SQL:**
```
postgresql://wros_user:secure_password@10.0.0.5/wros_prod
```

**Azure Database for PostgreSQL:**
```
postgresql://wros_user@wros:secure_password@wros.postgres.database.azure.com:5432/wros_prod
```

---

## Validation & Error Handling

### Startup Validation
```python
# In app/core/database.py

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable not set. "
        "Set it in .env or .env.local file. "
        "Format: postgresql://username:password@host:port/database_name"
    )

if not DATABASE_URL.startswith("postgresql://"):
    raise ValueError(
        f"Invalid DATABASE_URL: '{DATABASE_URL[:30]}...'. "
        "Only PostgreSQL is supported. "
        "Format: postgresql://username:password@host:port/database_name"
    )
```

### Connection Testing
```bash
# Test connection
psql "$(echo $DATABASE_URL | sed 's/postgresql:\/\///')"
# Should connect successfully or show clear error

# Via Python
python -c "from app.core.database import engine; engine.connect(); print('Connection OK')"
```

---

## Security Best Practices

### 1. Credentials Management
- ✅ Use secrets manager (AWS Secrets, Azure Key Vault, Vault)
- ✅ Rotate credentials regularly
- ✅ Use strong passwords (min 16 chars, mixed case, numbers, symbols)
- ✅ Use separate credentials for dev/staging/production

### 2. Network Security
- ✅ Use SSL/TLS for all connections
- ✅ Use private networks/VPCs (not internet-exposed)
- ✅ Restrict database access by IP/security group
- ✅ Use IAM roles when possible

### 3. Access Control
- ✅ Principle of least privilege
- ✅ Read-only replicas for reporting
- ✅ Separate users for different services
- ✅ Audit database access logs

### 4. Never in Code/Config
- ❌ No connection strings in .env files (except dev)
- ❌ No credentials in code comments
- ❌ No example with real passwords
- ❌ No git history with secrets

---

## Migration & Backup

### Running Migrations
```bash
# Development
DATABASE_URL="postgresql://..." python -m alembic upgrade head

# Production (use wrapper for safety)
./scripts/migrate-prod.sh
```

### Backup & Recovery
```bash
# Backup
pg_dump "postgresql://user:pass@host:5432/wros_prod" > backup.sql

# Restore
psql "postgresql://user:pass@host:5432/wros_prod" < backup.sql
```

---

## Troubleshooting

### Error: DATABASE_URL not set
**Solution:**
```bash
# Check if variable is set
echo $DATABASE_URL

# If empty, set it
export DATABASE_URL="postgresql://..."

# Or create .env.local (development only)
echo 'DATABASE_URL=postgresql://...' > .env.local
```

### Error: Invalid connection string
**Solution:**
Check format:
```
postgresql://username:password@host:port/database_name
              ↑        ↑         ↑   ↑    ↑
       required required required req req
```

### Error: Connection refused
**Solution:**
```bash
# Check if PostgreSQL is running
pg_isready -h localhost -p 5432

# Check firewall/security groups
nc -zv hostname 5432
```

---

## Phase 2 Compliance Summary

**Zero-Hardcoding Achievement:**
- ✅ All database configuration via DATABASE_URL environment variable
- ✅ No hardcoded connection strings in code
- ✅ No embedded credentials
- ✅ PostgreSQL only (no SQLite, no SQL Server)
- ✅ Proper validation at startup
- ✅ Clear error messages for misconfiguration
- ✅ .env files in .gitignore (no secrets in git)
- ✅ Template provided for production configuration

**100% Environment-Driven Database Configuration**
