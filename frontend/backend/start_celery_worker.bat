@echo off
REM Start Celery Worker on Windows
REM ===============================
REM
REM Requirements:
REM   - Redis server running on localhost:6379
REM   - Celery installed: pip install celery[redis]
REM   - All dependencies: pip install -r requirements.txt

echo.
echo 🚀 Starting Celery Worker
echo    Broker: redis://localhost:6379/0
echo    Backend: redis://localhost:6379/1
echo.
echo Press Ctrl+C to stop
echo.

REM Start Celery worker
REM Note: Windows requires eventlet for concurrency
celery -A app.core.celery_app worker ^
    --loglevel=info ^
    --pool=solo ^
    --task-events ^
    --without-gossip ^
    --without-mingle ^
    --without-heartbeat

pause
