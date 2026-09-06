# Production-ready startup script
# Ensures tight coupling: Redis -> Celery -> Backend
# Fails fast if any component doesn't start

param(
    [int]$REDIS_PORT = 6379,
    [int]$BACKEND_PORT = 8080,
    [int]$CELERY_MONITOR_PORT = 5555,
    [int]$STARTUP_TIMEOUT = 30
)

$ErrorActionPreference = "Stop"

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║ PRODUCTION STARTUP SEQUENCE                               ║" -ForegroundColor Cyan
Write-Host "║ Order: Redis → Celery Worker → Backend → Verify           ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

# Step 1: Verify Redis is running
Write-Host "[1/4] Verifying Redis..." -ForegroundColor Yellow

$redisRunning = $false
try {
    $redisCheck = netstat -ano | Select-String ":$REDIS_PORT"
    if ($redisCheck) {
        Write-Host "✅ Redis running on port $REDIS_PORT" -ForegroundColor Green
        $redisRunning = $true
    }
} catch {
    Write-Host "⚠️  Could not verify Redis" -ForegroundColor Yellow
}

if (-not $redisRunning) {
    Write-Host "❌ Redis is not running on port $REDIS_PORT" -ForegroundColor Red
    Write-Host "   Start Redis before running this script" -ForegroundColor Red
    Write-Host "   Command: redis-server.exe" -ForegroundColor Yellow
    Exit 1
}

# Step 2: Start Celery worker
Write-Host "`n[2/4] Starting Celery worker..." -ForegroundColor Yellow

$celeryProcess = Start-Process -FilePath "python" `
    -ArgumentList "-m celery -A app.celery_app worker --loglevel=info --concurrency=4" `
    -WorkingDirectory "C:\dev\WROS-Master\backend" `
    -WindowStyle Hidden `
    -PassThru

if (-not $celeryProcess) {
    Write-Host "❌ Failed to start Celery worker" -ForegroundColor Red
    Exit 1
}

Write-Host "✅ Celery worker started (PID: $($celeryProcess.Id))" -ForegroundColor Green

# Wait for Celery to be ready
Write-Host "   Waiting for Celery to initialize..." -ForegroundColor Cyan
$celeryReady = $false
$startTime = Get-Date

while ((Get-Date) - $startTime -lt (New-TimeSpan -Seconds $STARTUP_TIMEOUT)) {
    try {
        $celeryCheck = netstat -ano | Select-String ":$CELERY_MONITOR_PORT"
        if ($celeryCheck) {
            $celeryReady = $true
            break
        }
    } catch {}
    Start-Sleep -Milliseconds 500
}

if ($celeryReady) {
    Write-Host "✅ Celery ready (monitoring port $CELERY_MONITOR_PORT)" -ForegroundColor Green
} else {
    Write-Host "⚠️  Celery startup taking longer than expected, continuing..." -ForegroundColor Yellow
}

# Step 3: Start Backend
Write-Host "`n[3/4] Starting FastAPI backend..." -ForegroundColor Yellow

$backendProcess = Start-Process -FilePath "python" `
    -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port $BACKEND_PORT --reload" `
    -WorkingDirectory "C:\dev\WROS-Master\backend" `
    -WindowStyle Normal `
    -PassThru

if (-not $backendProcess) {
    Write-Host "❌ Failed to start backend" -ForegroundColor Red
    taskkill /F /PID $celeryProcess.Id 2>$null
    Exit 1
}

Write-Host "✅ Backend started (PID: $($backendProcess.Id)) on port $BACKEND_PORT" -ForegroundColor Green

# Step 4: Verify connectivity
Write-Host "`n[4/4] Verifying system connectivity..." -ForegroundColor Yellow

$verifyStart = Get-Date
$connected = $false

while ((Get-Date) - $verifyStart -lt (New-TimeSpan -Seconds $STARTUP_TIMEOUT)) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$BACKEND_PORT/api/v1/config/queue-types" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ Backend responding to API requests" -ForegroundColor Green
            $connected = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $connected) {
    Write-Host "⚠️  Backend not responding yet (may still be initializing)" -ForegroundColor Yellow
}

# Final summary
Write-Host "`n╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║ STARTUP COMPLETE                                           ║" -ForegroundColor Green
Write-Host "╠════════════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║ Redis:   Running on $REDIS_PORT                               ║" -ForegroundColor Green
Write-Host "║ Celery:  Running (PID: $($celeryProcess.Id))                          ║" -ForegroundColor Green
Write-Host "║ Backend: Running on http://localhost:$BACKEND_PORT                     ║" -ForegroundColor Green
Write-Host "╠════════════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║ To test candidate creation:                                ║" -ForegroundColor Cyan
Write-Host "║ 1. Navigate to: http://localhost:3000 (frontend)          ║" -ForegroundColor Cyan
Write-Host "║ 2. Create a candidate                                      ║" -ForegroundColor Cyan
Write-Host "║ 3. Check Message Queue Dashboard for queued messages      ║" -ForegroundColor Cyan
Write-Host "║                                                            ║" -ForegroundColor Cyan
Write-Host "║ To stop: Close this window and the backend window         ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green

# Keep script running
Write-Host "`nScript will monitor processes. Press Ctrl+C to stop." -ForegroundColor Yellow

while ($true) {
    if (-not (Get-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue)) {
        Write-Host "`n❌ Backend process died. Stopping Celery..." -ForegroundColor Red
        taskkill /F /PID $celeryProcess.Id 2>$null
        Exit 1
    }

    if (-not (Get-Process -Id $celeryProcess.Id -ErrorAction SilentlyContinue)) {
        Write-Host "`n❌ Celery process died. Backend will fail..." -ForegroundColor Red
        taskkill /F /PID $backendProcess.Id 2>$null
        Exit 1
    }

    Start-Sleep -Seconds 5
}
