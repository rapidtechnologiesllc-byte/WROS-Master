#!/bin/bash
################################################################################
# WROS Production Deployment Script
#
# This script handles the complete production deployment of WROS backend,
# including database initialization, systemd service setup, and health checks.
#
# Usage:
#   sudo bash production-deploy.sh [--verify-only]
#
# Requirements:
#   - Run as root or with sudo
#   - systemd-based Linux system
#   - PostgreSQL running
#   - Redis running
################################################################################

set -euo pipefail

# Configuration
APP_HOME="/home/HRMS/WROS-Master"
BACKEND_HOME="$APP_HOME/backend"
VENV_BIN="$APP_HOME/venv/bin"
PYTHON="$VENV_BIN/python"
LOG_DIR="/var/log/wros"
SYSTEMD_SRC="$BACKEND_HOME/systemd"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

die() {
    log_error "$1"
    exit 1
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        die "This script must be run as root or with sudo"
    fi
}

create_log_directory() {
    log_info "Creating log directory..."
    mkdir -p "$LOG_DIR"
    touch "$LOG_DIR/backend.log"
    touch "$LOG_DIR/backend-error.log"
    touch "$LOG_DIR/celery-worker.log"
    touch "$LOG_DIR/celery-worker-error.log"

    # Set permissions for hrms user
    chown -R hrms:hrms "$LOG_DIR"
    chmod 755 "$LOG_DIR"
    chmod 644 "$LOG_DIR"/*.log
}

validate_environment() {
    log_info "Validating production environment..."

    # Check Python
    if ! command -v "$PYTHON" &> /dev/null; then
        die "Python not found at $PYTHON"
    fi

    # Check PostgreSQL connection
    if ! psql -U postgres -c "SELECT 1" &> /dev/null; then
        die "Cannot connect to PostgreSQL"
    fi

    # Check Redis connection
    if ! redis-cli ping &> /dev/null; then
        die "Cannot connect to Redis"
    fi

    log_info "✓ Environment validation passed"
}

initialize_database() {
    log_info "Initializing database..."

    cd "$BACKEND_HOME"

    # Run database initialization from db_contract.py
    $PYTHON -c "
from app.core.db_contract import initialize_database
try:
    initialize_database()
    print('✓ Database initialized successfully')
except Exception as e:
    print(f'✗ Database initialization failed: {e}')
    exit(1)
"

    if [ $? -ne 0 ]; then
        die "Database initialization failed"
    fi
}

install_systemd_services() {
    log_info "Installing systemd services..."

    # Copy service files
    cp "$SYSTEMD_SRC/wros-backend.service" /etc/systemd/system/
    cp "$SYSTEMD_SRC/wros-celery-worker.service" /etc/systemd/system/

    # Create optional monitoring service for health checks
    cat > /etc/systemd/system/wros-backend-health-check.service <<'EOF'
[Unit]
Description=WROS Backend Health Check
After=wros-backend.service

[Service]
Type=oneshot
User=hrms
ExecStart=/home/HRMS/WROS-Master/venv/bin/python -c "import requests; requests.get('http://localhost:8080/health', timeout=5)"
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd configuration
    systemctl daemon-reload

    log_info "✓ Systemd services installed"
}

start_services() {
    log_info "Starting services..."

    # Enable on boot
    systemctl enable wros-backend.service wros-celery-worker.service

    # Kill any old processes first
    pkill -f "uvicorn app.main" || true
    pkill -f "celery.*app.celery_app" || true
    sleep 2

    # Start services
    systemctl start wros-backend.service
    systemctl start wros-celery-worker.service

    sleep 3

    log_info "✓ Services started"
}

health_check() {
    log_info "Running health checks..."

    # Check backend health
    for i in {1..15}; do
        if curl -s http://localhost:8080/health &> /dev/null; then
            log_info "✓ Backend health check passed"
            break
        fi
        if [ $i -eq 15 ]; then
            log_error "Backend health check failed after 15 attempts"
            systemctl status wros-backend.service || true
            return 1
        fi
        echo "  Attempt $i/15..."
        sleep 2
    done

    # Check Celery worker
    if pgrep -f "celery.*app.celery_app" > /dev/null; then
        log_info "✓ Celery worker is running"
    else
        log_warn "⚠ Celery worker not found - checking logs..."
        tail -20 "$LOG_DIR/celery-worker-error.log" || true
        return 1
    fi

    return 0
}

show_status() {
    log_info "=== Service Status ==="
    systemctl status wros-backend.service --no-pager || true
    echo
    systemctl status wros-celery-worker.service --no-pager || true
    echo
    log_info "=== Recent Logs ==="
    echo "--- Backend (last 10 lines) ---"
    tail -10 "$LOG_DIR/backend.log" || echo "No logs yet"
    echo
    echo "--- Celery Worker (last 10 lines) ---"
    tail -10 "$LOG_DIR/celery-worker.log" || echo "No logs yet"
}

verify_deployment() {
    log_info "=== Deployment Verification ==="
    echo

    # Check services are enabled
    if systemctl is-enabled wros-backend.service > /dev/null; then
        log_info "✓ wros-backend.service is enabled"
    else
        log_error "✗ wros-backend.service is NOT enabled"
        return 1
    fi

    if systemctl is-enabled wros-celery-worker.service > /dev/null; then
        log_info "✓ wros-celery-worker.service is enabled"
    else
        log_error "✗ wros-celery-worker.service is NOT enabled"
        return 1
    fi

    # Check services are running
    if systemctl is-active wros-backend.service > /dev/null; then
        log_info "✓ wros-backend.service is running"
    else
        log_error "✗ wros-backend.service is NOT running"
        return 1
    fi

    if systemctl is-active wros-celery-worker.service > /dev/null; then
        log_info "✓ wros-celery-worker.service is running"
    else
        log_error "✗ wros-celery-worker.service is NOT running"
        return 1
    fi

    # Check logs for errors
    if grep -i "error\|critical" "$LOG_DIR/backend-error.log" 2>/dev/null | head -1; then
        log_warn "⚠ Errors found in backend logs"
    else
        log_info "✓ No critical errors in logs"
    fi

    echo
    log_info "=== Deployment Complete ==="
    log_info "Backend: http://localhost:8080"
    log_info "Logs: $LOG_DIR/"
    log_info "Status: systemctl status wros-backend.service"
    log_info "Logs: journalctl -u wros-backend.service -f"

    return 0
}

# Main execution
main() {
    log_info "=== WROS Production Deployment ==="
    echo

    check_root
    validate_environment
    create_log_directory
    initialize_database
    install_systemd_services
    start_services

    if health_check; then
        show_status
        if verify_deployment; then
            exit 0
        fi
    fi

    log_error "Deployment verification failed - check logs above"
    show_status
    exit 1
}

# Run main function
main "$@"
