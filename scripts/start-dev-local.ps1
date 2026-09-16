#!/usr/bin/env pwsh
################################################################################
# WROS Local Development Startup Script
#
# Unified script to start all services for local development
# Checks prerequisites and starts: PostgreSQL, Redis, Backend, Frontend, Celery
#
# Usage:
#   ./scripts/start-dev-local.ps1
#
# Requires:
#   - Python 3.10+
#   - PostgreSQL 15+
#   - Redis 7+
#   - Node.js 18+
#   - Administrator (for service checks)
################################################################################

param(
    [switch]$SkipFrontend = $false
)

# Configuration
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$VenvPath = Join-Path $BackendDir "venv"
$VenvBinPath = Join-Path $VenvPath "Scripts"

# Colors
$Green = "Green"
$Red = "Red"
$Yellow = "Yellow"
$Cyan = "Cyan"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor $Green
Write-Host "║     WROS LOCAL DEVELOPMENT ENVIRONMENT STARTUP                 ║" -ForegroundColor $Green
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor $Green
Write-Host ""

# Verify Python
Write-Host "✓ Checking Python installation..." -ForegroundColor $Cyan
$PythonPath = & where python 2>$null
if (-not $PythonPath) {
    Write-Host "✗ Python not found in PATH" -ForegroundColor $Red
    Write-Host "  Please install Python 3.10+ from https://www.python.org" -ForegroundColor $Yellow
    exit 1
}
$PythonVersion = & python --version 2>&1
Write-Host "  $PythonVersion" -ForegroundColor $Green

# Verify PostgreSQL
Write-Host ""
Write-Host "✓ Checking PostgreSQL..." -ForegroundColor $Cyan
try {
    # Try direct connection
    $pgTest = & psql -U postgres -c "SELECT 1;" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  PostgreSQL running on localhost:5432" -ForegroundColor $Green
        $pgRunning = $true
    } else {
        throw "psql not found"
    }
} catch {
    Write-Host "✗ PostgreSQL not running or psql not in PATH" -ForegroundColor $Red
    Write-Host "  Ensure PostgreSQL 15+ is installed and running" -ForegroundColor $Yellow
    exit 1
}


# Verify Node.js
Write-Host ""
Write-Host "✓ Checking Node.js..." -ForegroundColor $Cyan
$NodePath = & where node 2>$null
if (-not $NodePath) {
    Write-Host "✗ Node.js not found in PATH" -ForegroundColor $Red
    Write-Host "  Please install Node.js 18+ from https://nodejs.org" -ForegroundColor $Yellow
    exit 1
}
$NodeVersion = & node --version 2>&1
Write-Host "  $NodeVersion" -ForegroundColor $Green

# Check Python venv
Write-Host ""
Write-Host "✓ Checking Python venv..." -ForegroundColor $Cyan
if (-not (Test-Path $VenvPath)) {
    Write-Host "✗ Virtual environment not found at $VenvPath" -ForegroundColor $Red
    Write-Host "  Creating venv..." -ForegroundColor $Yellow
    & python -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Failed to create venv" -ForegroundColor $Red
        exit 1
    }
    Write-Host "  Installing dependencies..." -ForegroundColor $Yellow
    & "$VenvBinPath\pip.exe" install -r "$BackendDir\requirements.txt" > $null 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Failed to install dependencies" -ForegroundColor $Red
        exit 1
    }
    Write-Host "  venv created and dependencies installed" -ForegroundColor $Green
} else {
    Write-Host "  venv found at $VenvPath" -ForegroundColor $Green
}

# Check frontend dependencies
Write-Host ""
Write-Host "✓ Checking npm dependencies..." -ForegroundColor $Cyan
$NodeModulesPath = Join-Path $FrontendDir "node_modules"
if (-not (Test-Path $NodeModulesPath)) {
    Write-Host "  Installing npm packages..." -ForegroundColor $Yellow
    Push-Location $FrontendDir
    & npm install > $null 2>&1
    Pop-Location
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Failed to install npm packages" -ForegroundColor $Red
        exit 1
    }
    Write-Host "  npm packages installed" -ForegroundColor $Green
} else {
    Write-Host "  npm packages found" -ForegroundColor $Green
}

# Kill existing processes
Write-Host ""
Write-Host "✓ Cleaning up stale processes..." -ForegroundColor $Cyan
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "uvicorn" } | ForEach-Object {
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    Write-Host "  Killed Python process (PID: $($_.Id))" -ForegroundColor $Yellow
}
Get-Process node -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    Write-Host "  Killed Node process (PID: $($_.Id))" -ForegroundColor $Yellow
}
Start-Sleep -Seconds 1

# Display startup instructions
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor $Green
Write-Host "║     SERVICES READY TO START                                   ║" -ForegroundColor $Green
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor $Green
Write-Host ""

Write-Host "🚀 Starting services in the background..." -ForegroundColor $Green
Write-Host ""

# Start backend
Write-Host "1️⃣  BACKEND (FastAPI + Uvicorn)" -ForegroundColor $Cyan
Write-Host "   Opening in new terminal window..." -ForegroundColor $Yellow
$backendCmd = @"
cd "$BackendDir"
`$env:PATH = ".\venv\Scripts;`$env:PATH"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8081
"@
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

# Start frontend
if (-not $SkipFrontend) {
    Write-Host ""
    Write-Host "2️⃣  FRONTEND (React)" -ForegroundColor $Cyan
    Write-Host "   Opening in new terminal window..." -ForegroundColor $Yellow
    $frontendCmd = @"
cd "$FrontendDir"
npm start
"@
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd
}


# Wait for services to start
Write-Host ""
Write-Host "⏳ Waiting for services to start (30 seconds)..." -ForegroundColor $Yellow
Start-Sleep -Seconds 10

# Health check
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor $Green
Write-Host "║     HEALTH CHECK                                              ║" -ForegroundColor $Green
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor $Green
Write-Host ""

# Test backend
Write-Host "Testing backend health..." -ForegroundColor $Cyan
$backendHealthUrl = "http://localhost:8081/health"
try {
    $response = Invoke-WebRequest -Uri $backendHealthUrl -TimeoutSec 5 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Backend responding on http://localhost:8081" -ForegroundColor $Green
    }
} catch {
    Write-Host "⏳ Backend still starting..." -ForegroundColor $Yellow
}

# Test frontend
if (-not $SkipFrontend) {
    Write-Host ""
    Write-Host "Testing frontend..." -ForegroundColor $Cyan
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3000" -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ Frontend responding on http://localhost:3000" -ForegroundColor $Green
        }
    } catch {
        Write-Host "⏳ Frontend still starting..." -ForegroundColor $Yellow
    }
}

# Summary
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor $Green
Write-Host "║     DEVELOPMENT ENVIRONMENT READY                             ║" -ForegroundColor $Green
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor $Green
Write-Host ""

Write-Host "📱 Access at:" -ForegroundColor $Cyan
Write-Host "   Frontend:      http://localhost:3000" -ForegroundColor $White
Write-Host "   Backend API:   http://localhost:8081" -ForegroundColor $White
Write-Host "   Health Check:  http://localhost:8081/health" -ForegroundColor $White
Write-Host ""

Write-Host "📝 Services running in separate terminal windows:" -ForegroundColor $Cyan
Write-Host "   - Backend Terminal (FastAPI on port 8081)" -ForegroundColor $White
Write-Host "   - Frontend Terminal (React on port 3000)" -ForegroundColor $White
Write-Host ""

Write-Host "💡 Tips:" -ForegroundColor $Cyan
Write-Host "   - Backend will auto-reload on code changes" -ForegroundColor $White
Write-Host "   - Frontend will auto-refresh on code changes" -ForegroundColor $White
Write-Host "   - Check 'backend/.env.local' for environment configuration" -ForegroundColor $White
Write-Host "   - Database queries use credentials from DATABASE_URL" -ForegroundColor $White
Write-Host ""

Write-Host "🔧 To stop services:" -ForegroundColor $Cyan
Write-Host "   - Close the terminal windows or press Ctrl+C" -ForegroundColor $White
Write-Host ""
