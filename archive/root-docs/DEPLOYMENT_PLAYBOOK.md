# WROS Production Deployment Playbook
**Version:** 1.0  
**Last Updated:** 2026-09-07

---

## Quick Reference

### Service Startup Order (Production Ubuntu)
```bash
1. PostgreSQL (system service)
2. Redis (system service)
3. WROS Backend (systemd: wros-backend.service)
4. WROS Celery Worker (systemd: wros-celery.service)
5. WROS Celery Beat (systemd: wros-celery-beat.service)
```

### Service Startup Commands
```bash
# Enable all services to start on boot
sudo systemctl enable postgresql.service
sudo systemctl enable redis-server.service
sudo systemctl enable wros-backend.service
sudo systemctl enable wros-celery.service
sudo systemctl enable wros-celery-beat.service

# Start all services
sudo systemctl start postgresql.service
sudo systemctl start redis-server.service
sudo systemctl start wros-backend.service
sudo systemctl start wros-celery.service
sudo systemctl start wros-celery-beat.service

# Check status
sudo systemctl status wros-*.service

# View logs in real-time
sudo journalctl -u wros-*.service -f
```

### Health Verification
```bash
# Run health check script
/opt/wros/scripts/verify-startup.sh

# Expected output: All checks passed!
# Exit code: 0 (success) or 1+ (failure)
```

---

## Part 1: One-Time Production Setup

### Step 1.1: Create Ubuntu 22.04 LTS Server
- Cloud provider: AWS, Azure, DigitalOcean, or on-premises
- Minimum specs: 2 CPU, 4GB RAM, 20GB disk
- SSH access enabled
- Security group: Allow 443 (HTTPS), 22 (SSH)

### Step 1.2: Install Base Dependencies
```bash
# Connect via SSH
ssh -i your-key.pem ubuntu@your-server.com

# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
  python3.11 \
  python3-pip \
  python3-dev \
  postgresql-15 \
  postgresql-client-15 \
  redis-server \
  git \
  curl \
  wget \
  build-essential \
  libssl-dev \
  libffi-dev

# Verify installations
python3 --version        # Python 3.11+
psql --version           # PostgreSQL 15+
redis-server --version   # Redis 8.10+
```

### Step 1.3: Create Application User
```bash
# Create wros user
sudo useradd -m -s /bin/bash wros
sudo usermod -aG sudo wros

# Create application directories
sudo mkdir -p /opt/wros/{backend,frontend}
sudo mkdir -p /var/log/wros
sudo mkdir -p /var/run/wros

# Set permissions
sudo chown -R wros:wros /opt/wros
sudo chown -R wros:wros /var/log/wros
sudo chown -R wros:wros /var/run/wros

# Create log rotation
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

### Step 1.4: Configure PostgreSQL
```bash
# Set PostgreSQL to start on boot
sudo systemctl enable postgresql.service
sudo systemctl start postgresql.service

# Create database and user
sudo -u postgres psql << 'SQL'
CREATE USER app_user WITH PASSWORD 'STRONG_PASSWORD_HERE';
CREATE DATABASE wros_prod OWNER app_user;

-- Grant necessary privileges
GRANT CONNECT ON DATABASE wros_prod TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT CREATE ON DATABASE wros_prod TO app_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO app_user;

-- Create app_schema
CREATE SCHEMA app_schema AUTHORIZATION app_user;
GRANT ALL PRIVILEGES ON SCHEMA app_schema TO app_user;
SQL

# Test connection
psql -U app_user -d wros_prod -h localhost -c "SELECT 1"
```

### Step 1.5: Configure Redis
```bash
# Redis is already managed by apt
sudo systemctl enable redis-server.service
sudo systemctl start redis-server.service

# Test connection
redis-cli ping  # Should return: PONG

# Verify Redis listens on 6379
sudo netstat -tlnp | grep redis
```

### Step 1.6: Deploy Application Code
```bash
# Clone repository (as wros user)
cd /opt/wros
sudo -u wros git clone https://github.com/yourorg/WROS-Master.git .

# Install Python dependencies (as wros user)
cd /opt/wros/backend
sudo -u wros python3 -m pip install --upgrade pip setuptools wheel
sudo -u wros pip3 install -r requirements.txt
sudo -u wros pip3 install gunicorn uvicorn
```

### Step 1.7: Create Production Environment File
```bash
# Create .env.production (NEVER commit to git)
sudo tee /opt/wros/backend/.env.production > /dev/null <<'EOF'
# Database
DATABASE_URL=postgresql://app_user:STRONG_PASSWORD_HERE@localhost:5432/wros_prod
ENVIRONMENT=production

# Redis
REDIS_URL=redis://localhost:6379/0

# API Configuration
BACKEND_PORT=8080
BACKEND_HOST=0.0.0.0
LOG_LEVEL=info

# Security (generate with: python3 -c "import secrets; print(secrets.token_urlsafe(32))")
SECRET_KEY=YOUR_GENERATED_SECRET_KEY_HERE
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

# CORS (allow only your frontend domain)
ALLOWED_ORIGINS=["https://yourdomain.com", "https://www.yourdomain.com"]

# Email (optional, for notifications)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Monitoring (optional, for error tracking)
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
EOF

# Restrict permissions
sudo chmod 600 /opt/wros/backend/.env.production
sudo chown wros:wros /opt/wros/backend/.env.production
```

### Step 1.8: Copy Systemd Service Files
```bash
# Copy service files to systemd directory
sudo cp /opt/wros/backend/config/systemd/*.service /etc/systemd/system/

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable redis-server.service
sudo systemctl enable postgresql.service
sudo systemctl enable wros-backend.service
sudo systemctl enable wros-celery.service
sudo systemctl enable wros-celery-beat.service
```

### Step 1.9: Run Database Migrations
```bash
# Run Alembic migrations
cd /opt/wros/backend
sudo -u wros python3 -m alembic upgrade head

# Verify database schema
sudo -u postgres psql -d wros_prod -c "\dt app_schema.*" | wc -l  # Should show 164 tables
```

### Step 1.10: Start All Services
```bash
# Start services in order
sudo systemctl start postgresql.service
sudo systemctl start redis-server.service
sudo systemctl start wros-backend.service
sudo systemctl start wros-celery.service
sudo systemctl start wros-celery-beat.service

# Verify status
sudo systemctl status wros-*.service

# Run health check
/opt/wros/scripts/verify-startup.sh
```

---

## Part 2: Configure Reverse Proxy (Nginx)

### Step 2.1: Install and Configure Nginx
```bash
# Install Nginx
sudo apt install -y nginx

# Create config
sudo tee /etc/nginx/sites-available/wros > /dev/null <<'EOF'
upstream backend {
    server 127.0.0.1:8080;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL certificates (managed by certbot)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy configuration
    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }

    # Health check endpoint (for load balancers)
    location /health {
        proxy_pass http://backend;
        access_log off;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/wros /etc/nginx/sites-enabled/

# Test config
sudo nginx -t

# Start Nginx
sudo systemctl enable nginx.service
sudo systemctl start nginx.service
```

### Step 2.2: Install SSL Certificate (LetsEncrypt)
```bash
# Install certbot
sudo apt install -y certbot python3-certbot-nginx

# Get certificate
sudo certbot certonly --nginx -d yourdomain.com -d www.yourdomain.com

# Automatic renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Test renewal
sudo certbot renew --dry-run
```

---

## Part 3: Continuous Deployment (GitHub Actions)

### Step 3.1: Create Deployment Workflow
```yaml
# .github/workflows/deploy-production.yml

name: Deploy to Production

on:
  push:
    branches: [main]
    paths:
      - 'backend/**'
      - '.github/workflows/deploy-production.yml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Run code review gate
        run: npm run lint && pytest
        
      - name: Deploy to production server
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.PROD_SERVER_IP }}
          username: ${{ secrets.PROD_SSH_USER }}
          key: ${{ secrets.PROD_SSH_KEY }}
          script: |
            cd /opt/wros
            git pull origin main
            cd backend
            python3 -m pip install -r requirements.txt
            python3 -m alembic upgrade head
            sudo systemctl restart wros-backend.service
            sudo systemctl restart wros-celery.service
            sleep 5
            /opt/wros/scripts/verify-startup.sh
```

### Step 3.2: Add GitHub Secrets
In your GitHub repository settings, add:
- `PROD_SERVER_IP`: Your Ubuntu server IP
- `PROD_SSH_USER`: ubuntu
- `PROD_SSH_KEY`: Contents of your SSH private key
- `PROD_DATABASE_PASSWORD`: Strong password for app_user
- `PROD_SECRET_KEY`: Generated secret key
- `PROD_SENTRY_DSN`: Sentry error tracking URL

---

## Part 4: Monitoring & Logging

### Step 4.1: View Logs
```bash
# Real-time backend logs
sudo journalctl -u wros-backend.service -f

# Real-time celery worker logs
sudo journalctl -u wros-celery.service -f

# Real-time celery beat logs
sudo journalctl -u wros-celery-beat.service -f

# All logs (combined)
sudo journalctl -u wros-*.service -f

# Search for errors
sudo journalctl -u wros-backend.service | grep ERROR

# Last N lines
sudo journalctl -u wros-backend.service -n 50
```

### Step 4.2: Service Restart Policy
If a service crashes:
1. Waits 10 seconds (RestartSec=10)
2. Restarts automatically
3. Max 3 attempts per 60 seconds (StartLimitBurst=3)
4. Logged to systemd journal

No manual intervention needed for transient failures.

### Step 4.3: Health Monitoring Script
```bash
#!/bin/bash
# Run every 5 minutes via cron

/opt/wros/scripts/verify-startup.sh
if [ $? -ne 0 ]; then
    # Send alert (email, Slack, PagerDuty, etc.)
    curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK \
      -H 'Content-Type: application/json' \
      -d '{"text":"WROS health check FAILED"}'
fi
```

---

## Part 5: Maintenance & Operations

### Scheduled Tasks
- **Daily**: Database backups (PostgreSQL)
- **Weekly**: Log rotation (already configured)
- **Monthly**: Security updates (`sudo apt update && sudo apt upgrade`)
- **Quarterly**: SSL certificate renewal (auto via certbot)

### Database Backups
```bash
# Manual backup
sudo -u postgres pg_dump -d wros_prod > /backups/wros_prod_$(date +%Y%m%d_%H%M%S).sql

# Automated daily backup (add to crontab)
# 0 2 * * * sudo -u postgres pg_dump -d wros_prod | gzip > /backups/wros_prod_$(date +\%Y\%m\%d).sql.gz
```

### Scaling Considerations
- **Vertical Scaling**: Increase worker count in gunicorn (workers=4 → 8, 16, etc.)
- **Horizontal Scaling**: Deploy multiple backend instances with load balancer
- **Database Scaling**: Use PostgreSQL replication for read-heavy workloads
- **Celery Scaling**: Add more Celery workers on separate machines

---

## Part 6: Emergency Procedures

### Service Restart
```bash
# Restart single service
sudo systemctl restart wros-backend.service

# Restart all services
sudo systemctl restart wros-*.service

# Force stop and start
sudo systemctl stop wros-*.service
sudo systemctl start wros-*.service
```

### Troubleshooting
```bash
# Check if port 8080 is in use
sudo lsof -i :8080

# Check system resources
free -h              # Memory usage
df -h                # Disk usage
top -b -n 1          # CPU and process info

# Check database connection
sudo -u postgres psql -d wros_prod -c "SELECT 1"

# Check Redis connection
redis-cli ping
```

### Rollback
```bash
# If deployment broke the system:
cd /opt/wros
git log --oneline -10        # See recent commits
git revert <commit-hash>     # Revert specific commit
git pull origin main         # Or just pull previous stable version

# Reinstall dependencies
cd backend
pip3 install -r requirements.txt

# Run migrations (if needed)
python3 -m alembic downgrade -1

# Restart services
sudo systemctl restart wros-backend.service
```

---

## Part 7: Performance Tuning

### PostgreSQL Tuning (for 4GB RAM server)
```sql
-- Connect as postgres user
sudo -u postgres psql -d wros_prod

-- Add to postgresql.conf
max_connections = 100
shared_buffers = 1GB
effective_cache_size = 2GB
work_mem = 10MB
maintenance_work_mem = 256MB
random_page_cost = 1.1
```

### Gunicorn Tuning (for 4 CPU cores)
```ini
# In wros-backend.service
--workers 4              # 2 + (2 * num_cores)
--worker-class uvicorn.workers.UvicornWorker
--timeout 60             # Increase if tasks take longer
--max-requests 1000      # Restart worker after 1000 requests (memory leak prevention)
```

### Redis Tuning
```bash
# Enable persistence (if needed)
sudo tee -a /etc/redis/redis.conf > /dev/null <<'EOF'
save 900 1              # Save every 15 minutes if 1+ keys changed
save 300 10             # Save every 5 minutes if 10+ keys changed
save 60 10000           # Save every minute if 10000+ keys changed
appendonly yes          # Enable AOF (append-only file)
appendfsync everysec    # Sync to disk every second
EOF
```

---

## Part 8: Backup Strategy

### Database Backup (Daily)
```bash
# /opt/wros/scripts/backup-db.sh
#!/bin/bash
BACKUP_DIR="/backups/wros"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
sudo -u postgres pg_dump -d wros_prod | gzip > $BACKUP_DIR/wros_prod_$TIMESTAMP.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "wros_prod_*.sql.gz" -mtime +30 -delete

# Upload to S3 (optional)
aws s3 cp $BACKUP_DIR/wros_prod_$TIMESTAMP.sql.gz s3://your-backup-bucket/
```

Add to crontab:
```bash
# 2 AM daily
0 2 * * * /opt/wros/scripts/backup-db.sh
```

---

## Checklist: Pre-Production Deployment

- [ ] Ubuntu 22.04 LTS server provisioned
- [ ] PostgreSQL 15 installed and running
- [ ] Redis 8.10+ installed and running
- [ ] Application code cloned to `/opt/wros`
- [ ] `.env.production` created with all secrets
- [ ] Database migrations applied (`alembic upgrade head`)
- [ ] Systemd service files copied to `/etc/systemd/system/`
- [ ] Services enabled and started
- [ ] Health check script returns success
- [ ] Nginx reverse proxy configured
- [ ] SSL certificate installed (LetsEncrypt)
- [ ] Automated backups configured
- [ ] Monitoring/alerts configured
- [ ] GitHub Actions workflow created
- [ ] GitHub Secrets configured
- [ ] Documentation reviewed by ops team

---

## Production Readiness Summary

✅ **Architecture**: Fully documented and tested  
✅ **Deployment**: Automated via GitHub Actions  
✅ **Monitoring**: Systemd logs + optional monitoring tools  
✅ **Scaling**: Load balancer ready, horizontal scaling supported  
✅ **Security**: SSL/TLS, environment secrets, permission system  
✅ **Recovery**: Automatic restart, backup strategy, rollback procedure  

**Status: PRODUCTION READY**

---

**Questions?** Refer to PRODUCTION_STARTUP_GUIDE.md for detailed component setup.
