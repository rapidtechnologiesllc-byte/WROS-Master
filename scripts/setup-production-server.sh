#!/bin/bash
# Production server setup script - Run this ONCE on the production server
# This configures everything needed for CI/CD deployments to work smoothly

set -e

echo "🚀 Setting up production server for WROS HRMS deployment..."

# 1. Ensure directories exist
echo "📁 Creating directories..."
mkdir -p /home/HRMS/WROS-Master/frontend/build
mkdir -p /tmp/backend-backups

# 2. Configure sudo NOPASSWD for deployment commands
echo "🔐 Configuring sudo permissions..."
sudo bash -c 'cat > /etc/sudoers.d/hrms-deploy << EOF
# Allow HRMS user to run deployment commands without password
HRMS ALL=(ALL) NOPASSWD: /usr/bin/sed
HRMS ALL=(ALL) NOPASSWD: /usr/bin/systemctl
HRMS ALL=(ALL) NOPASSWD: /bin/rm
HRMS ALL=(ALL) NOPASSWD: /bin/chown
HRMS ALL=(ALL) NOPASSWD: /bin/chmod
HRMS ALL=(ALL) NOPASSWD: /bin/mkdir
EOF
'
sudo chmod 440 /etc/sudoers.d/hrms-deploy

# 3. Verify sudo configuration
echo "✅ Verifying sudo configuration..."
sudo -l | grep -E "sed|systemctl|rm|chown|chmod|mkdir" || echo "⚠️  Check sudo manually"

# 4. Set initial permissions
echo "🔒 Setting initial file permissions..."
sudo chown -R www-data:www-data /home/HRMS/WROS-Master/frontend/build 2>/dev/null || true
sudo chmod -R 755 /home/HRMS/WROS-Master/frontend/build 2>/dev/null || true

# 5. Verify Nginx configuration
echo "🔄 Checking Nginx configuration..."
if grep -q "root /home/HRMS/WROS-Master/frontend/build/build" /etc/nginx/sites-available/wros-hrms-frontend.conf; then
    echo "✅ Nginx config is correct"
else
    echo "⚠️  Update Nginx config manually: root should be /home/HRMS/WROS-Master/frontend/build/build"
fi

# 6. Reload Nginx
echo "🔄 Reloading Nginx..."
sudo systemctl reload nginx

echo ""
echo "✅ Server setup complete!"
echo ""
echo "From now on, deployments will be fully automated via CI/CD."
echo "No more manual fixes needed! 🚀"
