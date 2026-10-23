# Complete Backend Startup Script - Redis, Celery, FastAPI
# Starts all 3 services with health checks
# Usage: ./backend-startup-complete.ps1

Write-Host "==================== BACKEND STARTUP - COMPLETE STACK ====================" -ForegroundColor Cyan
Write-Host ""

# Global configuration
$backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path | Join-Path -ChildPath "backend"
$backendPort = 8080
$redisPort = 6379
$celeryLogFile = Join-Path $backendDir "celery-worker.log"

if (-not (Test-Path $backendDir)) {
    Write-Host "❌ Backend directory not found: $backendDir" -ForegroundColor Red
    exit 1
}

# Step 1: Verify Redis is running
Write-Host "[STEP 1] Verifying Redis is running on port $redisPort..." -ForegroundColor Yellow

$redisRunning = $false
try {
    $netStat = netstat -ano | Select-String ":$redisPort"
    if ($netStat) {
        Write-Host "✅ Redis is running" -ForegroundColor Green
        $redisRunning = $true
    }
} catch {}

if (-not $redisRunning) {
    Write-Host "❌ Redis is not running on port $redisPort" -ForegroundColor Red
    Write-Host "   Run: ./redis-setup.ps1" -ForegroundColor Yellow
    exit 1
}

# Step 2: Kill any existing processes on port 8080 and Celery workers
Write-Host ""
Write-Host "[STEP 2] Cleaning up existing processes..." -ForegroundColor Yellow

try {
    # Kill FastAPI on port 8080
    $port8080 = netstat -ano | Select-String ":$backendPort"
    if ($port8080) {
        $pid = $port8080 -split '\s+' | Select-Object -Last 1
        Write-Host "   Killing FastAPI on port 8080 (PID: $pid)..." -ForegroundColor Gray
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
} catch {}

try {
    # Kill Celery workers
    Get-Process celery -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*celery*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "✅ Previous processes cleaned up" -ForegroundColor Green
} catch {}

Start-Sleep -Seconds 1

# Step 3: Start Celery Worker
Write-Host ""
Write-Host "[STEP 3] Starting Celery worker..." -ForegroundColor Yellow

Push-Location $backendDir

# Check if celery is installed
$celeryCheck = python -c "import celery; print('ok')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Celery not installed. Run: pip install celery redis" -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "   Launching Celery worker (logging to: $celeryLogFile)..." -ForegroundColor Gray

# Start Celery in a separate process with output redirect
$celeryArgs = @(
    '-m', 'celery',
    '-A', 'app',
    'worker',
    '--loglevel=info',
    '--concurrency=4',
    '--pool=prefork'
)

$processInfo = New-Object System.Diagnostics.ProcessStartInfo
$processInfo.FileName = "python"
$processInfo.Arguments = $celeryArgs -join " "
$processInfo.UseShellExecute = $false
$processInfo.RedirectStandardOutput = $true
$processInfo.RedirectStandardError = $true
$processInfo.CreateNoWindow = $true
$processInfo.WorkingDirectory = $backendDir

$celeryProcess = [System.Diagnostics.Process]::Start($processInfo)
Write-Host "✅ Celery worker started (PID: $($celeryProcess.Id))" -ForegroundColor Green

# Redirect Celery output to log file
$celeryOutput = $celeryProcess.StandardOutput
$celeryError = $celeryProcess.StandardError

# Start background jobs to capture output
$null = Start-Job -ScriptBlock {
    param($reader, $file)
    while ($null -ne ($line = $reader.ReadLine())) {
        Add-Content $file "$(Get-Date -Format 'HH:mm:ss') $line"
    }
} -ArgumentList $celeryOutput, $celeryLogFile

$null = Start-Job -ScriptBlock {
    param($reader, $file)
    while ($null -ne ($line = $reader.ReadLine())) {
        Add-Content $file "ERROR: $line"
    }
} -ArgumentList $celeryError, $celeryLogFile

Write-Host "   Logs: $celeryLogFile" -ForegroundColor Gray
Start-Sleep -Seconds 3

# Step 4: Start FastAPI Backend
Write-Host ""
Write-Host "[STEP 4] Starting FastAPI backend on port $backendPort..." -ForegroundColor Yellow

$uvicornArgs = @(
    'app.main:app',
    '--reload',
    '--host', '127.0.0.1',
    '--port', $backendPort
)

Write-Host "   Launching: uvicorn $($uvicornArgs -join ' ')" -ForegroundColor Gray

# Start uvicorn in current process (foreground)
# This allows us to see logs in real-time
python -m uvicorn @uvicornArgs

Pop-Location
