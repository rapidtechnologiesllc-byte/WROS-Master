# VPS Deployment Guide - OnboardingModule Backend

Complete guide for deploying your FastAPI backend to a VPS (Virtual Private Server) via SSH.

## Table of Contents

- [Prerequisites](#prerequisites)
- [SSH Connection Setup](#ssh-connection-setup)
- [Initial VPS Setup](#initial-vps-setup)
- [Deploying the Application](#deploying-the-application)
- [Editing Code on VPS](#editing-code-on-vps)
- [Running the Application](#running-the-application)
- [Setting Up as a Service](#setting-up-as-a-service)
- [Updating Your Application](#updating-your-application)
- [Monitoring and Logs](#monitoring-and-logs)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have:

- ✅ VPS server (Ubuntu 20.04+ or similar Linux distribution)
- ✅ VPS IP address (e.g., `46.224.149.7`)
- ✅ SSH credentials (username and password or SSH key)
- ✅ Root or sudo access on the VPS
- ✅ Domain name (optional, for production)

---

## SSH Connection Setup

### Method 1: Connect with Password

```bash
# Basic SSH connection (with custom port 22587)
ssh username@your-vps-ip -p 22587

# Example:
ssh root@46.224.149.7 -p 22587

# Or with specific user:
ssh suresh@46.224.149.7 -p 22587
```

When prompted, enter your password.

### Method 2: Connect with SSH Key (Recommended)

SSH keys are more secure than passwords.

#### Step 1: Generate SSH Key (on your local machine)

```bash
# Generate a new SSH key pair
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# Save to default location: C:\Users\SureshKannan\.ssh\id_rsa
# Set a passphrase (optional but recommended)
```

#### Step 2: Copy SSH Key to VPS

```bash
# Windows (Git Bash or PowerShell)
type C:\Users\SureshKannan\.ssh\id_rsa.pub | ssh username@your-vps-ip -p 22587 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"

# Or manually:
# 1. Display your public key:
cat ~/.ssh/id_rsa.pub

# 2. Copy the output
# 3. SSH into VPS with password
# 4. Add to authorized_keys:
mkdir -p ~/.ssh
echo "your-public-key-here" >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

#### Step 3: Connect with SSH Key

```bash
# Now you can connect without password
ssh username@your-vps-ip -p 22587

# Or specify key explicitly:
ssh -i ~/.ssh/id_rsa username@your-vps-ip -p 22587
```

### Method 3: Using VS Code Remote SSH (Best for Editing)

1. **Install VS Code Extension**
   - Open VS Code
   - Install "Remote - SSH" extension

2. **Add SSH Host**
   - Press `F1` or `Ctrl+Shift+P`
   - Type "Remote-SSH: Connect to Host"
   - Click "Add New SSH Host"
   - Enter: `ssh username@46.224.149.7 -p 22587`
   - Select config file: `C:\Users\SureshKannan\.ssh\config`

3. **Connect**
   - Press `F1` → "Remote-SSH: Connect to Host"
   - Select your VPS from the list
   - VS Code will open a new window connected to your VPS
   - You can now edit files directly on the server!

---

## Initial VPS Setup

Once connected to your VPS, run these commands:

### Step 1: Update System

```bash
# Update package lists
sudo apt update

# Upgrade installed packages
sudo apt upgrade -y
```

### Step 2: Install Python 3.10+

```bash
# Check Python version
python3 --version

# If Python 3.10+ is not installed:
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev -y

# Set Python 3.10 as default (optional)
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1
```

### Step 3: Install Required System Packages

```bash
# Install essential build tools
sudo apt install -y build-essential git curl wget

# Install ODBC Driver for SQL Server
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt update
sudo ACCEPT_EULA=Y apt install -y msodbcsql18 unixodbc-dev

# Verify ODBC driver installation
odbcinst -q -d -n "ODBC Driver 18 for SQL Server"
```

### Step 4: Install pip

```bash
# Install pip for Python 3.10
sudo apt install python3-pip -y

# Upgrade pip
python3 -m pip install --upgrade pip
```

### Step 5: Create Application Directory

```bash
# Create directory for your application
sudo mkdir -p /var/www/onboarding-backend
sudo chown -R $USER:$USER /var/www/onboarding-backend
cd /var/www/onboarding-backend
```

---

## Deploying the Application

### Method 1: Deploy via Git (Recommended)

```bash
# Navigate to application directory
cd /var/www/onboarding-backend

# Clone your repository
git clone https://github.com/blitzenx25/OnboardingModule-Backend.git .

# Or if already cloned, pull latest changes:
git pull origin main
```

### Method 2: Deploy via SCP (File Transfer)

From your **local machine** (Windows):

```bash
# Transfer entire project to VPS
scp -P 22587 -r C:\Users\SureshKannan\projects\onboard\OnboardingModule-Backend username@46.224.149.7:/var/www/onboarding-backend/

# Or use WinSCP (GUI tool):
# Download from: https://winscp.net/
# Connect and drag-drop files
```

### Step 2: Set Up Virtual Environment

```bash
# Navigate to project directory
cd /var/www/onboarding-backend

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Your prompt should now show (.venv)
```

### Step 3: Install Dependencies

```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Verify installation
pip list
```

### Step 4: Configure Environment Variables

```bash
# Create .env file
nano .env

# Or copy from example:
cp .env.example .env
nano .env
```

Add your production configuration:

```env
# Database Configuration
DATABASE_URL=mssql+pyodbc://onboard_user:password@46.224.149.7/onboard1?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes

# JWT Keys
JWT_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----

# Microsoft Authentication
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
REDIRECT_URI=http://46.224.149.7:8080/msgraph/auth/callback
AUTHORITY=https://login.microsoftonline.com/your-tenant-id
SCOPES=https://graph.microsoft.com/.default

# Azure Service Account
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-app-id
AZURE_CLIENT_SECRET=your-client-secret

# SharePoint
SHAREPOINT_SITE_ID=your-site-id
SHAREPOINT_DRIVE_ID=your-drive-id
SHAREPOINT_BASE_FOLDER=candidates/2026

# Google AI
GEMINI_API_KEY=your-api-key

# Production URLs
PRODUCTION_BACKEND_URL=http://46.224.149.7:8080/
PRODUCTION_FRONTEND_URL=http://46.224.149.7:3005/
REDIRECT_RESPONSE=http://46.224.149.7:3005/
```

**Save and exit**: Press `Ctrl+X`, then `Y`, then `Enter`

### Step 5: Run Database Migrations

```bash
# Activate virtual environment if not already
source .venv/bin/activate

# Run migrations
python migrate.py --upgrade

# Or using Alembic directly:
python -m alembic upgrade head
```

### Step 6: Test the Application

```bash
# Test run (development mode)
python -m app.main

# The server should start on http://0.0.0.0:8080
# Press Ctrl+C to stop
```

---

## Editing Code on VPS

### Method 1: Using VS Code Remote SSH (Best Option)

1. **Connect via Remote SSH** (see setup above)
2. **Open folder**: `/var/www/onboarding-backend`
3. **Edit files** directly in VS Code
4. **Changes are saved** directly on the VPS
5. **Use integrated terminal** for running commands

### Method 2: Using Nano (Terminal Editor)

```bash
# Edit a file with nano
nano app/main.py

# Keyboard shortcuts:
# Ctrl+O - Save file
# Ctrl+X - Exit
# Ctrl+K - Cut line
# Ctrl+U - Paste line
# Ctrl+W - Search
```

### Method 3: Using Vim (Advanced)

```bash
# Edit a file with vim
vim app/main.py

# Basic vim commands:
# Press 'i' - Enter insert mode (edit)
# Press 'Esc' - Exit insert mode
# Type ':w' - Save file
# Type ':q' - Quit
# Type ':wq' - Save and quit
# Type ':q!' - Quit without saving
```

### Method 4: Edit Locally and Deploy

```bash
# On your local machine, make changes
# Then push to Git:
git add .
git commit -m "Update code"
git push origin main

# On VPS, pull changes:
cd /var/www/onboarding-backend
git pull origin main

# Restart the application (see below)
```

---

## Running the Application

### Option 1: Development Mode (Testing)

```bash
# Activate virtual environment
source .venv/bin/activate

# Run with uvicorn
python -m app.main

# Or directly with uvicorn:
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### Option 2: Production Mode with Gunicorn

```bash
# Activate virtual environment
source .venv/bin/activate

# Run with Gunicorn (4 workers)
gunicorn app.main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080 \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log \
  --daemon

# Check if running:
ps aux | grep gunicorn

# Stop Gunicorn:
pkill gunicorn
```

### Option 3: Using Screen (Keep Running After Disconnect)

```bash
# Install screen
sudo apt install screen -y

# Start a new screen session
screen -S onboarding-api

# Run your application
source .venv/bin/activate
python -m app.main

# Detach from screen: Press Ctrl+A, then D

# List screen sessions:
screen -ls

# Reattach to session:
screen -r onboarding-api

# Kill session:
screen -X -S onboarding-api quit
```

---

## Setting Up as a Service

Create a systemd service to run your application automatically.

### Step 1: Create Service File

```bash
# Create service file
sudo nano /etc/systemd/system/onboarding-api.service
```

Add the following content:

```ini
[Unit]
Description=Onboarding Module Backend API
After=network.target

[Service]
Type=notify
User=your-username
Group=www-data
WorkingDirectory=/var/www/onboarding-backend
Environment="PATH=/var/www/onboarding-backend/.venv/bin"
ExecStart=/var/www/onboarding-backend/.venv/bin/gunicorn app.main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080 \
  --access-logfile /var/www/onboarding-backend/logs/access.log \
  --error-logfile /var/www/onboarding-backend/logs/error.log
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always

[Install]
WantedBy=multi-user.target
```

**Replace `your-username`** with your actual username (run `whoami` to check).

### Step 2: Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable onboarding-api

# Start service
sudo systemctl start onboarding-api

# Check status
sudo systemctl status onboarding-api

# View logs
sudo journalctl -u onboarding-api -f
```

### Step 3: Service Management Commands

```bash
# Start service
sudo systemctl start onboarding-api

# Stop service
sudo systemctl stop onboarding-api

# Restart service
sudo systemctl restart onboarding-api

# Check status
sudo systemctl status onboarding-api

# View logs (live)
sudo journalctl -u onboarding-api -f

# View last 100 lines
sudo journalctl -u onboarding-api -n 100
```

---

## Updating Your Application

### Method 1: Git Pull (Recommended)

```bash
# Navigate to project directory
cd /var/www/onboarding-backend

# Pull latest changes
git pull origin main

# Activate virtual environment
source .venv/bin/activate

# Install any new dependencies
pip install -r requirements.txt

# Run migrations if needed
python migrate.py --upgrade

# Restart the service
sudo systemctl restart onboarding-api

# Check status
sudo systemctl status onboarding-api
```

### Method 2: Manual File Upload

```bash
# From local machine, upload changed files:
scp -P 22587 app/main.py username@46.224.149.7:/var/www/onboarding-backend/app/

# On VPS, restart service:
sudo systemctl restart onboarding-api
```

---

## Monitoring and Logs

### Application Logs

```bash
# View application logs
tail -f /var/www/onboarding-backend/logs/app_*.log

# View access logs
tail -f /var/www/onboarding-backend/logs/access.log

# View error logs
tail -f /var/www/onboarding-backend/logs/error.log
```

### System Logs

```bash
# View service logs (live)
sudo journalctl -u onboarding-api -f

# View last 50 lines
sudo journalctl -u onboarding-api -n 50

# View logs since today
sudo journalctl -u onboarding-api --since today

# View logs with errors only
sudo journalctl -u onboarding-api -p err
```

### System Monitoring

```bash
# Check CPU and memory usage
htop

# Or use top:
top

# Check disk usage
df -h

# Check memory usage
free -h

# Check running processes
ps aux | grep python
```

---

## Troubleshooting

### Issue: Can't Connect via SSH

**Solutions:**
```bash
# Check if SSH service is running on VPS (from VPS console):
sudo systemctl status ssh

# Start SSH service:
sudo systemctl start ssh

# Check firewall:
sudo ufw status
sudo ufw allow 22587/tcp

# Test connection with verbose output:
ssh -v username@46.224.149.7 -p 22587
```

### Issue: Permission Denied

**Solutions:**
```bash
# Fix file permissions:
sudo chown -R $USER:$USER /var/www/onboarding-backend

# Fix SSH key permissions:
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

### Issue: Port 8080 Already in Use

**Solutions:**
```bash
# Find process using port 8080:
sudo lsof -i :8080

# Kill the process:
sudo kill -9 <PID>

# Or use a different port in .env:
# Update PORT=8081 in your config
```

### Issue: Database Connection Failed

**Solutions:**
```bash
# Test database connection:
python -c "from app.core.database import engine; print(engine.connect())"

# Check if SQL Server is accessible:
telnet 46.224.149.7 1433

# Verify ODBC driver:
odbcinst -q -d
```

### Issue: Module Not Found

**Solutions:**
```bash
# Ensure virtual environment is activated:
source .venv/bin/activate

# Reinstall dependencies:
pip install -r requirements.txt

# Check Python path:
which python
python --version
```

### Issue: Service Won't Start

**Solutions:**
```bash
# Check service status:
sudo systemctl status onboarding-api

# View detailed logs:
sudo journalctl -u onboarding-api -n 100 --no-pager

# Check service file syntax:
sudo systemd-analyze verify /etc/systemd/system/onboarding-api.service

# Reload and restart:
sudo systemctl daemon-reload
sudo systemctl restart onboarding-api
```

---

## Security Best Practices

### 1. Configure Firewall

```bash
# Enable UFW firewall
sudo ufw enable

# Allow SSH (custom port)
sudo ufw allow 22587/tcp

# Allow your application port
sudo ufw allow 8080/tcp

# Allow HTTP/HTTPS (if using nginx)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Check status
sudo ufw status
```

### 2. Disable Root Login

```bash
# Edit SSH config
sudo nano /etc/ssh/sshd_config

# Change these lines:
PermitRootLogin no
PasswordAuthentication no

# Restart SSH
sudo systemctl restart ssh
```

### 3. Keep System Updated

```bash
# Update regularly
sudo apt update && sudo apt upgrade -y

# Enable automatic security updates
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

---

## Quick Reference Commands

```bash
# SSH Connection
ssh username@46.224.149.7 -p 22587

# Navigate to project
cd /var/www/onboarding-backend

# Activate virtual environment
source .venv/bin/activate

# Pull latest code
git pull origin main

# Install dependencies
pip install -r requirements.txt

# Run migrations
python migrate.py --upgrade

# Restart service
sudo systemctl restart onboarding-api

# Check status
sudo systemctl status onboarding-api

# View logs
sudo journalctl -u onboarding-api -f
tail -f logs/app_*.log
```

---

## Additional Tools

### Install Nginx (Reverse Proxy)

```bash
# Install Nginx
sudo apt install nginx -y

# Create Nginx config
sudo nano /etc/nginx/sites-available/onboarding-api

# Add configuration:
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/onboarding-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Install SSL Certificate (Let's Encrypt)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is set up automatically
```

---

**Last Updated**: February 2026  
**Author**: Suresh Kannan (Blitzenx)
