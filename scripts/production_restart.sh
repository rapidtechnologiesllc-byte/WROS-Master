#!/bin/bash
# Production Restart Script
# Use this to restart the backend service on production

echo "=========================================="
echo "PRODUCTION BACKEND RESTART"
echo "=========================================="
echo ""

cd /home/HRMS/OnboardingModule-Backend || exit 1

echo "1. Stopping backend service..."
pkill -f "uvicorn app.main:app"
sleep 2

echo "2. Pulling latest code..."
git fetch origin
git reset --hard origin/main
sleep 1

echo "3. Installing dependencies..."
python3 -m pip install -q -r requirements.txt

echo "4. Starting backend service..."
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 > /tmp/backend.log 2>&1 &
sleep 3

echo "5. Verifying service started..."
if pgrep -f "uvicorn app.main:app" > /dev/null; then
    echo "✓ Backend process started"
else
    echo "✗ Backend process failed to start"
    echo "Check logs: tail -f /tmp/backend.log"
    exit 1
fi

echo ""
echo "6. Testing health endpoint..."
for i in {1..10}; do
    if curl -s http://localhost:8080/health | grep -q "healthy"; then
        echo "✓ Health endpoint responding"
        curl -s http://localhost:8080/health
        break
    else
        echo "  Attempt $i: waiting for health endpoint..."
        sleep 1
    fi
done

echo ""
echo "7. Running deployment verification..."
python3 scripts/verify_deployment.py

echo ""
echo "=========================================="
echo "BACKEND RESTART COMPLETE"
echo "=========================================="
