# Redis Setup & Verification Script for Windows
# Detects Redis installation, provides guidance, and verifies Redis is working
# Usage: ./redis-setup.ps1

Write-Host "==================== REDIS SETUP & VERIFICATION ====================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if Redis is already running
Write-Host "[STEP 1] Checking if Redis is already running..." -ForegroundColor Yellow

$redisRunning = $false
try {
    $netStat = netstat -ano | Select-String ":6379"
    if ($netStat) {
        Write-Host "✅ Redis is already running on port 6379" -ForegroundColor Green
        $redisRunning = $true
    }
} catch {
    # netstat might not show Redis yet
}

if ($redisRunning) {
    Write-Host ""
    Write-Host "==================== REDIS READY TO USE ====================" -ForegroundColor Green
    Write-Host "Redis is running and ready for backend connection."
    Write-Host ""
    exit 0
}

# Step 2: Check if Redis is installed (Memurai on Windows)
Write-Host "[STEP 2] Checking if Redis is installed..." -ForegroundColor Yellow

$redisPath = $null
$possiblePaths = @(
    "C:\Program Files\Redis\redis-server.exe",
    "C:\Program Files (x86)\Redis\redis-server.exe",
    "C:\redis\redis-server.exe",
    "$env:ProgramFiles\Redis\redis-server.exe"
)

foreach ($path in $possiblePaths) {
    if (Test-Path $path) {
        $redisPath = $path
        Write-Host "✅ Found Redis at: $redisPath" -ForegroundColor Green
        break
    }
}

if (-not $redisPath) {
    Write-Host "❌ Redis not found in standard locations" -ForegroundColor Red
    Write-Host ""
    Write-Host "INSTALLATION OPTIONS:" -ForegroundColor Magenta
    Write-Host ""
    Write-Host "Option 1: Use Memurai (Recommended for Windows)" -ForegroundColor Cyan
    Write-Host "  Download: https://www.memurai.com/" -ForegroundColor Cyan
    Write-Host "  Steps:" -ForegroundColor Cyan
    Write-Host "    1. Download Memurai Community Edition" -ForegroundColor Cyan
    Write-Host "    2. Run installer (keep defaults)" -ForegroundColor Cyan
    Write-Host "    3. Rerun this script after installation" -ForegroundColor Cyan
    Write-Host ""

    Write-Host "Option 2: Use Chocolatey" -ForegroundColor Cyan
    Write-Host "  Steps:" -ForegroundColor Cyan
    Write-Host "    1. choco install redis-64" -ForegroundColor Cyan
    Write-Host "    2. Rerun this script after installation" -ForegroundColor Cyan
    Write-Host ""

    Write-Host "Option 3: Use Windows Subsystem for Linux (WSL2)" -ForegroundColor Cyan
    Write-Host "  Steps:" -ForegroundColor Cyan
    Write-Host "    1. wsl" -ForegroundColor Cyan
    Write-Host "    2. sudo apt-get install redis-server" -ForegroundColor Cyan
    Write-Host "    3. redis-server &  (run in background)" -ForegroundColor Cyan
    Write-Host "    4. Exit WSL and rerun this script" -ForegroundColor Cyan
    Write-Host ""

    Write-Host "Option 4: Use Docker" -ForegroundColor Cyan
    Write-Host "  Steps:" -ForegroundColor Cyan
    Write-Host "    1. docker run -d -p 6379:6379 redis:latest" -ForegroundColor Cyan
    Write-Host "    2. Rerun this script" -ForegroundColor Cyan
    Write-Host ""

    exit 1
}

# Step 3: Start Redis
Write-Host ""
Write-Host "[STEP 3] Starting Redis..." -ForegroundColor Yellow
Write-Host ""

try {
    # Kill any existing redis-server processes
    Get-Process redis-server -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500

    # Start Redis in background
    $processInfo = New-Object System.Diagnostics.ProcessStartInfo
    $processInfo.FileName = $redisPath
    $processInfo.UseShellExecute = $false
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    $processInfo.CreateNoWindow = $true

    $process = [System.Diagnostics.Process]::Start($processInfo)
    Write-Host "✅ Redis process started (PID: $($process.Id))" -ForegroundColor Green

    # Wait for Redis to start
    Start-Sleep -Seconds 2

    # Verify Redis is listening
    $redisListening = $false
    for ($i = 0; $i -lt 10; $i++) {
        try {
            $netStat = netstat -ano | Select-String ":6379"
            if ($netStat) {
                $redisListening = $true
                break
            }
        } catch {}
        Start-Sleep -Milliseconds 500
    }

    if (-not $redisListening) {
        Write-Host "⚠️  Redis process started but not listening on port 6379" -ForegroundColor Yellow
        Write-Host "    This might mean Redis is still initializing or encountered an error" -ForegroundColor Yellow
        Write-Host "    Wait a few seconds and rerun this script" -ForegroundColor Yellow
        exit 1
    }

    Write-Host "✅ Redis is listening on port 6379" -ForegroundColor Green

} catch {
    Write-Host "❌ Failed to start Redis: $_" -ForegroundColor Red
    exit 1
}

# Step 4: Test Redis connectivity
Write-Host ""
Write-Host "[STEP 4] Testing Redis connectivity..." -ForegroundColor Yellow

$testCommand = {
    # Simple ping test using PowerShell TCP client
    $tcp = New-Object Net.Sockets.TcpClient
    try {
        $tcp.Connect("127.0.0.1", 6379)
        $stream = $tcp.GetStream()

        # Send PING command
        $bytes = [System.Text.Encoding]::ASCII.GetBytes("PING`r`n")
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush()

        # Read response
        $reader = New-Object System.IO.StreamReader($stream)
        $response = $reader.ReadLine()

        $stream.Close()
        $tcp.Close()

        return $response -like "*PONG*"
    } catch {
        return $false
    }
}

$connectionWorks = & $testCommand

if ($connectionWorks) {
    Write-Host "✅ Redis PING successful - connection verified" -ForegroundColor Green
    Write-Host ""
    Write-Host "==================== REDIS READY TO USE ====================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Redis is running and ready for backend services!"
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Run: ./backend-startup-complete.ps1" -ForegroundColor Cyan
    Write-Host ""
    exit 0
} else {
    Write-Host "⚠️  Could not verify Redis connection via PING" -ForegroundColor Yellow
    Write-Host "    Attempting to connect via redis-cli..." -ForegroundColor Yellow

    # Try using redis-cli if available
    $redisCli = Join-Path (Split-Path $redisPath) "redis-cli.exe"
    if (Test-Path $redisCli) {
        try {
            $output = & $redisCli ping
            if ($output -eq "PONG") {
                Write-Host "✅ Redis PING successful (via redis-cli)" -ForegroundColor Green
                Write-Host ""
                Write-Host "==================== REDIS READY TO USE ====================" -ForegroundColor Green
                exit 0
            }
        } catch {}
    }

    Write-Host "❌ Could not verify Redis connectivity" -ForegroundColor Red
    Write-Host "    Try waiting a few seconds for Redis to fully start and rerun this script" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Magenta
    Write-Host "  - Check if port 6379 is already in use: netstat -ano | findstr :6379" -ForegroundColor Magenta
    Write-Host "  - Check Redis logs in: C:\Program Files\Redis\redis-server.exe" -ForegroundColor Magenta
    Write-Host "  - Try restarting: taskkill /IM redis-server.exe /F" -ForegroundColor Magenta
    exit 1
}
