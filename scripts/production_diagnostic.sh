#!/bin/bash
# Production Diagnostic Script
# Run on production server to diagnose backend issues

echo "=========================================="
echo "PRODUCTION BACKEND DIAGNOSTIC"
echo "=========================================="
echo ""

# Check if backend is running
echo "1. Checking if backend process is running..."
if pgrep -f "uvicorn app.main:app" > /dev/null; then
    echo "✓ Backend process found"
    ps aux | grep uvicorn | grep -v grep
else
    echo "✗ Backend process NOT running"
fi
echo ""

# Check port 8080
echo "2. Checking port 8080..."
if netstat -tuln 2>/dev/null | grep :8080 > /dev/null; then
    echo "✓ Port 8080 is listening"
    netstat -tuln | grep :8080
else
    echo "✗ Port 8080 NOT listening"
fi
echo ""

# Check health endpoint
echo "3. Testing health endpoint..."
HEALTH=$(curl -s http://localhost:8080/health 2>&1)
if echo "$HEALTH" | grep -q "healthy"; then
    echo "✓ Health endpoint responds"
    echo "Response: $HEALTH"
else
    echo "✗ Health endpoint not responding"
    echo "Response: $HEALTH"
fi
echo ""

# Check database connection
echo "4. Testing database connection..."
cd /home/HRMS/OnboardingModule-Backend
python3 -c "
from app.core.database import SessionLocal
try:
    db = SessionLocal()
    result = db.execute('SELECT COUNT(*) FROM \"Resource\"')
    count = result.scalar()
    print(f'✓ Database connected. Resources: {count}')
    db.close()
except Exception as e:
    print(f'✗ Database error: {e}')
" 2>&1
echo ""

# Check recent logs
echo "5. Recent backend logs (last 20 lines)..."
if [ -f /tmp/backend.log ]; then
    tail -20 /tmp/backend.log
else
    echo "No log file found at /tmp/backend.log"
fi
echo ""

# Check deployment status
echo "6. Checking git status..."
cd /home/HRMS/OnboardingModule-Backend
echo "Current commit: $(git log --oneline -1)"
echo "Origin main: $(git log --oneline origin/main -1)"
echo ""

# Verify deployment script
echo "7. Running deployment verification..."
python3 scripts/verify_deployment.py
echo ""

echo "=========================================="
echo "END DIAGNOSTIC"
echo "=========================================="
