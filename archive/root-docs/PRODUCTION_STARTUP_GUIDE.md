# WROS Production Startup Guide for Ubuntu/Linux

## Overview
This guide covers automated startup, systemd service management, and health verification for production deployments.

## Part 1: Systemd Service Files

### 1.1 Redis Service (`/etc/systemd/system/redis-server.service`)
```ini
[Unit]
Description=Redis Key-Value Store
After=network.target
Documentation=https://redis.io/documentation

[Service]
Type=notify
ExecStart=/usr/bin/redis-server /etc/redis/redis.conf
ExecStop=/usr/bin/redis-cli -p 6379 shutdown
Restart=always
RestartSec=10
User=redis
Group=redis
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 1.2 PostgreSQL Service (Pre-installed)
```bash
# Already managed by Ubuntu/Debian package
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

### 1.3 WROS Backend Service (`/etc/systemd/system/wros-backend.service`)
```ini
[Unit]
Description=WROS FastAPI Backend
After=network.target postgresql.service redis-server.service
Requires=postgresql.service redis-server.service
Documentation=https://github.com/yourorg/wros

[Service]
Type=notify
WorkingDirectory=/opt/wros/backend
User=wros
Group=wros

# Environment configuration
EnvironmentFile=/opt/wros/backend/.env.production
Environment="PYTHONUNBUFFERED=1"
Environment="ENVIRONMENT=production"

# Start backend with gunicorn
ExecStart=/usr/bin/python3 -m gunicorn \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  app.main:app

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=60s
StartLimitBurst=3

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=wros-backend

[Install]
WantedBy=multi-user.target
```

### 1.4 Celery Worker Service (`/etc/systemd/system/wros-celery.service`)
```ini
[Unit]
Description=WROS Celery Worker
After=network.target redis-server.service
Requires=redis-server.service
Documentation=https://docs.celeryproject.io/

[Service]
Type=forking
WorkingDirectory=/opt/wros/backend
User=wros
Group=wros

# Environment configuration
EnvironmentFile=/opt/wros/backend/.env.production
Environment="PYTHONUNBUFFERED=1"
Environment="ENVIRONMENT=production"

# Start celery worker
ExecStart=/usr/bin/python3 -m celery -A app.celery_app worker \
  --loglevel=info \
  --concurrency=4 \
  --max-tasks-per-child=1000 \
  --time-limit=3600

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=60s
StartLimitBurst=3

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=wros-celery

[Install]
WantedBy=multi-user.target
```

### 1.5 Celery Beat Service (`/etc/systemd/system/wros-celery-beat.service`)
```ini
[Unit]
Description=WROS Celery Beat Scheduler
After=network.target redis-server.service
Requires=redis-server.service
Documentation=https://docs.celeryproject.io/

[Service]
Type=simple
WorkingDirectory=/opt/wros/backend
User=wros
Group=wros

# Environment configuration
EnvironmentFile=/opt/wros/backend/.env.production
Environment="PYTHONUNBUFFERED=1"
Environment="ENVIRONMENT=production"

# Start celery beat
ExecStart=/usr/bin/python3 -m celery -A app.celery_app beat \
  --loglevel=info \
  --scheduler celery_beat.schedulers:PersistentScheduler \
  --pidfile=/var/run/celery-beat.pid

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=60s
StartLimitBurst=3

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=wros-celery-beat

[Install]
WantedBy=multi-user.target
```

## Part 2: Production Environment Setup

### 2.1 Prerequisites
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y \
  python3.11 \
  python3-pip \
  postgresql-15 \
  postgresql-client-15 \
  redis-server \
  git \
  curl \
  supervisor \
  nginx \
  certbot \
  python3-certbot-nginx

# Create wros user
sudo useradd -m -s /bin/bash wros
sudo usermod -aG sudo wros
```

### 2.2 Directory Structure
```bash
# Create application directories
sudo mkdir -p /opt/wros/{backend,frontend}
sudo mkdir -p /var/log/wros
sudo mkdir -p /var/run/wros
sudo mkdir -p /etc/wros

# Set permissions
sudo chown -R wros:wros /opt/wros
sudo chown -R wros:wros /var/log/wros
sudo chown -R wros:wros /var/run/wros
sudo chown -R wros:wros /etc/wros

# Create log rotation config
sudo tee /etc/logrotate.d/wros > /dev/null <<'EOF'
/var/log/wros/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    create 0640 wros wros
    sharedscripts
    postrotate
        systemctl reload wros-backend wros-celery > /dev/null 2>&1 || true
    endscript
}
EOF
```

### 2.3 Production Environment File
Create `/opt/wros/backend/.env.production`:

```bash
# Database
DATABASE_URL=postgresql://app_user:${DB_PASSWORD}@localhost:5432/wros_prod
ENVIRONMENT=production

# Redis
REDIS_URL=redis://localhost:6379/0

# API Configuration
BACKEND_PORT=8080
BACKEND_HOST=0.0.0.0
LOG_LEVEL=info

# Security
SECRET_KEY=${GENERATED_SECRET_KEY}
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=${SMTP_USERNAME}
SMTP_PASSWORD=${SMTP_PASSWORD}

# Monitoring
SENTRY_DSN=${SENTRY_DSN}
```

### 2.4 Generate Secrets
```bash
# Generate strong secret key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Store in GitHub Secrets or environment management system
```

## Part 3: Installation & Deployment

### 3.1 Clone & Setup Repository
```bash
cd /opt/wros
sudo -u wros git clone https://github.com/yourorg/WROS-Master.git .

# Install Python dependencies
cd /opt/wros/backend
sudo -u wros python3 -m pip install --upgrade pip
sudo -u wros pip3 install -r requirements.txt

# Install gunicorn
sudo -u wros pip3 install gunicorn uvicorn
```

### 3.2 Database Setup
```bash
# Create PostgreSQL user and database
sudo -u postgres psql << EOF
CREATE USER app_user WITH PASSWORD 'secure_password_here';
CREATE DATABASE wros_prod OWNER app_user;
GRANT ALL PRIVILEGES ON DATABASE wros_prod TO app_user;
EOF

# Run migrations
cd /opt/wros/backend
sudo -u wros python3 -m alembic upgrade head
```

### 3.3 Initialize Systemd Services
```bash
# Copy service files
sudo cp /opt/wros/backend/config/systemd/*.service /etc/systemd/system/

# Reload daemon
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable redis-server.service
sudo systemctl enable postgresql.service
sudo systemctl enable wros-backend.service
sudo systemctl enable wros-celery.service
sudo systemctl enable wros-celery-beat.service

# Start all services
sudo systemctl start redis-server.service
sudo systemctl start postgresql.service
sudo systemctl start wros-backend.service
sudo systemctl start wros-celery.service
sudo systemctl start wros-celery-beat.service
```

## Part 4: Health Checks & Monitoring

### 4.1 Startup Verification Script
```bash
#!/bin/bash
# /opt/wros/scripts/verify-startup.sh

echo "=== WROS Production Health Check ==="

# Check PostgreSQL
echo -n "PostgreSQL: "
sudo -u postgres psql -c "SELECT 1" &>/dev/null && echo "OK" || echo "FAILED"

# Check Redis
echo -n "Redis: "
redis-cli ping 2>/dev/null | grep -q "PONG" && echo "OK" || echo "FAILED"

# Check Backend
echo -n "Backend API: "
curl -s http://localhost:8080/health | grep -q "healthy" && echo "OK" || echo "FAILED"

# Check services
echo ""
echo "=== Service Status ==="
systemctl status wros-backend.service --no-pager
echo ""
systemctl status wros-celery.service --no-pager
echo ""
systemctl status wros-celery-beat.service --no-pager
```

### 4.2 View Logs
```bash
# Backend logs
sudo journalctl -u wros-backend.service -f

# Celery worker logs
sudo journalctl -u wros-celery.service -f

# Celery beat logs
sudo journalctl -u wros-celery-beat.service -f

# All WROS services
sudo journalctl -u wros-*.service -f
```

### 4.3 Monitoring with Nginx
```nginx
# /etc/nginx/sites-available/wros

upstream backend {
    server 127.0.0.1:8080;
}

server {
    listen 80;
    server_name wros.yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name wros.yourdomain.com;

    # SSL certificates (managed by certbot)
    ssl_certificate /etc/letsencrypt/live/wros.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/wros.yourdomain.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;

    # Proxy configuration
    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://backend;
        access_log off;
    }
}
```

Enable and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/wros /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Part 5: Production Checklist

- [ ] PostgreSQL 15+ installed and running
- [ ] Redis 8.10+ installed and running
- [ ] Application code deployed to `/opt/wros`
- [ ] `.env.production` configured with secrets
- [ ] Database migrations applied (`alembic upgrade head`)
- [ ] Systemd services created and enabled
- [ ] Services started and verified healthy
- [ ] Nginx reverse proxy configured
- [ ] SSL certificates installed (certbot)
- [ ] Log rotation configured
- [ ] Monitoring/alerts configured (Sentry, DataDog, etc.)
- [ ] Backup scripts configured (PostgreSQL, Redis)
- [ ] Emergency contact info documented

## Part 6: Startup Command Summary

### First-Time Startup (Fresh Deploy)
```bash
# 1. Verify all prerequisites installed
sudo systemctl status postgresql.service

# 2. Start core services
sudo systemctl start postgresql.service
sudo systemctl start redis-server.service

# 3. Run database migrations
cd /opt/wros/backend
sudo -u wros python3 -m alembic upgrade head

# 4. Start application services
sudo systemctl start wros-backend.service
sudo systemctl start wros-celery.service
sudo systemctl start wros-celery-beat.service

# 5. Verify health
curl http://localhost:8080/health
redis-cli ping
```

### Normal Startup (Restart Services)
```bash
sudo systemctl start wros-backend.service
sudo systemctl start wros-celery.service
sudo systemctl start wros-celery-beat.service
```

### Shutdown (Graceful)
```bash
sudo systemctl stop wros-backend.service
sudo systemctl stop wros-celery.service
sudo systemctl stop wros-celery-beat.service
```

### Status Check
```bash
sudo systemctl status wros-*.service
```

---

## Key Differences: Windows Local vs. Ubuntu Production

| Aspect | Windows Local | Ubuntu Production |
|--------|---------------|-------------------|
| **Database** | PostgreSQL (localhost) | PostgreSQL (managed by systemd) |
| **Redis** | Manual start (redis-server.exe) | systemd service (auto-restart) |
| **Backend** | Manual python -m uvicorn | systemd service (auto-restart, process pooling) |
| **Celery Worker** | Manual python -m celery | systemd service (concurrency=4, max-tasks-per-child) |
| **Startup** | Manual commands in terminal | Automatic on server boot |
| **Restarts** | Manual restart required | Automatic with systemd Restart=always |
| **Logging** | Console/terminal output | Systemd journal (journalctl) |
| **Process Management** | Running foreground processes | Background services with supervisors |
| **Environment Secrets** | `.env` file (local only) | GitHub Secrets → systemd EnvironmentFile |
| **Updates** | Manual git pull + restart | CI/CD pipeline with zero-downtime deploy |

This ensures that when the production Ubuntu server reboots, all services automatically start in the correct order and stay running with automatic restarts on failure.
