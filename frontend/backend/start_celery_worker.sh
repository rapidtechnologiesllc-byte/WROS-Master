#!/bin/bash
# Start Celery Worker
# ====================
#
# Usage:
#   ./start_celery_worker.sh                    # Start with default settings
#   ./start_celery_worker.sh -c 4               # Start with 4 concurrent workers
#   ./start_celery_worker.sh -l info            # Enable debug logging
#
# Requirements:
#   - Redis server running on localhost:6379
#   - Celery installed: pip install celery[redis]
#   - Backend installed: pip install -r requirements.txt

# Get number of concurrent workers (default: CPU count)
CONCURRENCY=${1:-$(nproc)}

echo "🚀 Starting Celery Worker"
echo "   Concurrency: $CONCURRENCY"
echo "   Broker: redis://localhost:6379/0"
echo "   Backend: redis://localhost:6379/1"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start Celery worker
celery -A app.core.celery_app worker \
    --loglevel=info \
    --concurrency=$CONCURRENCY \
    --prefetch-multiplier=1 \
    --task-events \
    --without-gossip \
    --without-mingle \
    --without-heartbeat
