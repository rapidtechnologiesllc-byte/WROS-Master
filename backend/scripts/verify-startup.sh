#!/bin/bash
# Production Startup Health Verification Script
# Usage: ./verify-startup.sh

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}WROS Production Health Check${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

FAILED=0

# Test PostgreSQL
echo -n "PostgreSQL Connection: "
if sudo -u postgres psql -c "SELECT 1" &>/dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
    FAILED=$((FAILED + 1))
fi

# Test Redis
echo -n "Redis Connection: "
if redis-cli -p 6379 ping 2>/dev/null | grep -q "PONG"; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
    FAILED=$((FAILED + 1))
fi

# Test Backend Health
echo -n "Backend API Health: "
if curl -s http://localhost:8080/health | grep -q "healthy"; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
    FAILED=$((FAILED + 1))
fi

# Test Backend Root
echo -n "Backend Root Endpoint: "
status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/)
if [ "$status" = "200" ] || [ "$status" = "307" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED (HTTP $status)${NC}"
    FAILED=$((FAILED + 1))
fi

# Test Celery
echo -n "Celery Worker Status: "
if pgrep -f "celery.*worker" > /dev/null; then
    echo -e "${GREEN}RUNNING${NC}"
else
    echo -e "${YELLOW}NOT RUNNING${NC}"
fi

# Test Celery Beat
echo -n "Celery Beat Status: "
if pgrep -f "celery.*beat" > /dev/null; then
    echo -e "${GREEN}RUNNING${NC}"
else
    echo -e "${YELLOW}NOT RUNNING${NC}"
fi

echo ""
echo -e "${BLUE}Service Status:${NC}"
echo ""

# Show backend logs (last 5 lines)
if command -v journalctl &> /dev/null; then
    echo "Backend (last 5 lines):"
    sudo journalctl -u wros-backend.service -n 5 --no-pager 2>/dev/null || echo "  (logs unavailable)"
    echo ""

    echo "Celery Worker (last 5 lines):"
    sudo journalctl -u wros-celery.service -n 5 --no-pager 2>/dev/null || echo "  (logs unavailable)"
    echo ""

    echo "Celery Beat (last 5 lines):"
    sudo journalctl -u wros-celery-beat.service -n 5 --no-pager 2>/dev/null || echo "  (logs unavailable)"
else
    echo "systemd journal not available"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All checks passed!${NC}"
else
    echo -e "${RED}$FAILED check(s) failed${NC}"
fi
echo -e "${BLUE}========================================${NC}"

exit $FAILED
