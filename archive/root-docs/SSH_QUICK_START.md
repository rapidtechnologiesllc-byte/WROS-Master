# Quick SSH Connection Reference

## Connect to Your VPS

```bash
# Basic SSH connection (custom port 22587)
ssh username@46.224.149.7 -p 22587

# Example with root:
ssh root@46.224.149.7 -p 22587
```

## First Time Setup

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install Python 3.10
sudo apt install python3.10 python3.10-venv python3-pip -y

# 3. Install ODBC Driver
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt update
sudo ACCEPT_EULA=Y apt install -y msodbcsql18

# 4. Create app directory
sudo mkdir -p /var/www/onboarding-backend
sudo chown -R $USER:$USER /var/www/onboarding-backend
cd /var/www/onboarding-backend

# 5. Clone repository
git clone https://github.com/blitzenx25/OnboardingModule-Backend.git .

# 6. Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 7. Install dependencies
pip install -r requirements.txt

# 8. Create .env file
cp .env.example .env
nano .env  # Edit with your production settings

# 9. Run migrations
python migrate.py --upgrade

# 10. Test run
python -m app.main
```

## Edit Code on VPS

### Option 1: VS Code Remote SSH (Recommended)
1. Install "Remote - SSH" extension in VS Code
2. Press F1 → "Remote-SSH: Connect to Host"
3. Enter: `ssh username@46.224.149.7 -p 22587`
4. Edit files directly in VS Code!

### Option 2: Terminal Editor
```bash
nano app/main.py  # Simple editor
vim app/main.py   # Advanced editor
```

### Option 3: Edit Locally, Deploy via Git
```bash
# On local machine:
git add .
git commit -m "Update"
git push

# On VPS:
git pull
sudo systemctl restart onboarding-api
```

## Run as Service

```bash
# Create service file
sudo nano /etc/systemd/system/onboarding-api.service
```

Paste this (replace `your-username`):
```ini
[Unit]
Description=Onboarding API
After=network.target

[Service]
Type=notify
User=your-username
WorkingDirectory=/var/www/onboarding-backend
Environment="PATH=/var/www/onboarding-backend/.venv/bin"
ExecStart=/var/www/onboarding-backend/.venv/bin/gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable onboarding-api
sudo systemctl start onboarding-api
sudo systemctl status onboarding-api
```

## Common Commands

```bash
# Connect to VPS
ssh username@46.224.149.7 -p 22587

# Go to project
cd /var/www/onboarding-backend

# Activate environment
source .venv/bin/activate

# Update code
git pull

# Restart service
sudo systemctl restart onboarding-api

# View logs
sudo journalctl -u onboarding-api -f
tail -f logs/app_*.log

# Check status
sudo systemctl status onboarding-api
```

## Update Application

```bash
cd /var/www/onboarding-backend
git pull
source .venv/bin/activate
pip install -r requirements.txt
python migrate.py --upgrade
sudo systemctl restart onboarding-api
```

---

For detailed instructions, see [VPS_DEPLOYMENT.md](./VPS_DEPLOYMENT.md)
