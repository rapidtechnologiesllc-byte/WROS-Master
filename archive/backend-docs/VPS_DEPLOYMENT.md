# VPS Deployment Guide - HRMS Full Stack

Quick deployment guide for FastAPI backend and Next.js frontend on VPS.

**Server Details:**
- **VPS IP**: `46.224.149.7`
- **SSH Port**: `22587`
- **Backend**: http://46.224.149.7:8080
- **Frontend**: http://46.224.149.7:3005

---

## First Connection

```bash
# Connect to VPS
ssh root@46.224.149.7 -p 22587
```

---

## Initial Setup

```bash
# Update system
apt update && apt upgrade -y

# Install required packages
apt install -y python3.10 python3.10-venv python3-pip build-essential git curl wget nodejs npm nginx

# Install ODBC Driver for SQL Server
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | tee /etc/apt/sources.list.d/mssql-release.list
apt update
ACCEPT_EULA=Y apt install -y msodbcsql18 unixodbc-dev

# Create HRMS directory
mkdir -p /home/HRMS
cd /home/HRMS
```

---

## GitHub Setup

```bash
# Generate SSH key for GitHub
ssh-keygen -t ed25519 -C "your_email@example.com" -f ~/.ssh/github_key

# Display public key (copy this to GitHub)
cat ~/.ssh/github_key.pub
```

**Add to GitHub**: Go to https://github.com/settings/keys → New SSH key → Paste key

```bash
# Configure SSH
nano ~/.ssh/config
```

Add:
```
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_key
```

```bash
chmod 600 ~/.ssh/config ~/.ssh/github_key

# Test connection
ssh -T git@github.com
```

---

## Backend Deployment

```bash
# Clone repository
cd /home/HRMS
git clone git@github.com:blitzenx25/OnboardingModule-Backend.git HRMS-D-V1
cd HRMS-D-V1

# Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Create .env file
nano .env
```

Add your configuration, then:

```bash
# Create HRMS user
useradd -r -s /bin/false HRMS
chown -R HRMS:HRMS /home/HRMS/HRMS-D-V1

# Create systemd service
nano /etc/systemd/system/hrms.service
```

Add:
```ini
[Unit]
Description=HRMS FastAPI Backend
After=network.target

[Service]
User=HRMS
Group=HRMS
WorkingDirectory=/home/HRMS/HRMS-D-V1
Environment="PATH=/home/HRMS/HRMS-D-V1/venv/bin"
ExecStart=/home/HRMS/HRMS-D-V1/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Start backend service
systemctl daemon-reload
systemctl enable hrms.service
systemctl start hrms.service
systemctl status hrms.service
```

---

## Frontend Deployment

```bash
# Clone repository
cd /home/HRMS
git clone git@github.com:blitzenx25/OnboardingModule-Frontend.git HRMS-FE-V1
cd HRMS-FE-V1

# Install and build
npm install
npm run build

# Create nginx configuration
nano /etc/nginx/sites-available/hrms-frontend
```

Add:
```nginx
server {
    listen 3005;
    server_name 46.224.149.7;

    root /home/HRMS/HRMS-FE-V1/build;
    index index.html;

    location / {
        try_files $uri /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Enable site
ln -s /etc/nginx/sites-available/hrms-frontend /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

---

## Firewall Setup

```bash
ufw allow 22587/tcp  # SSH
ufw allow 8080/tcp   # Backend
ufw allow 3005/tcp   # Frontend
ufw enable
```

---

## Updating Applications

### Update Backend
```bash
cd /home/HRMS/HRMS-D-V1
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
deactivate
systemctl restart hrms.service
```

### Update Frontend
```bash
cd /home/HRMS/HRMS-FE-V1
git pull origin main
npm install
npm run build
systemctl restart nginx
```

---

## Quick Commands

```bash
# Check backend status
systemctl status hrms.service
journalctl -u hrms.service -f

# Check frontend status
systemctl status nginx
tail -f /var/log/nginx/error.log

# Restart services
systemctl restart hrms.service
systemctl restart nginx
```

---

## Troubleshooting

```bash
# Backend not starting
journalctl -u hrms.service -n 50
lsof -i :8080

# Frontend not loading
nginx -t
tail -f /var/log/nginx/error.log

# GitHub connection issues
ssh -T git@github.com
```

---

**Last Updated**: February 2026
