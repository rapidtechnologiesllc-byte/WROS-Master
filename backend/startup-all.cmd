@echo off
REM Complete startup script - initializes RBAC, creates test users, and starts both servers

setlocal enabledelayedexpansion

echo.
echo ========================================
echo WROS COMPLETE STARTUP
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.9+
    exit /b 1
)

REM Check if npm is available
npm --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm not found. Please install Node.js
    exit /b 1
)

REM Kill any existing processes on ports 8080 and 3000
echo [STEP 1] Cleaning up old processes...
netstat -ano | findstr :8080 >nul
if %errorlevel% equ 0 (
    echo  - Found process on port 8080, killing...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8080') do taskkill /pid %%a /f >nul 2>&1
)

netstat -ano | findstr :3000 >nul
if %errorlevel% equ 0 (
    echo  - Found process on port 3000, killing...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000') do taskkill /pid %%a /f >nul 2>&1
)

timeout /t 2 /nobreak

REM Initialize RBAC system
echo.
echo [STEP 2] Initializing RBAC system...
cd /d "OnboardingModule-Backend"
python init_rbac.py
if errorlevel 1 (
    echo [ERROR] RBAC initialization failed
    cd ..
    exit /b 1
)
echo [OK] RBAC initialized

REM Create test users
echo.
echo [STEP 3] Creating test users...
python setup_test_users.py
if errorlevel 1 (
    echo [WARNING] Test user creation had issues (they may already exist)
)
echo [OK] Test users configured

cd ..

REM Start backend in new window
echo.
echo [STEP 4] Starting backend server (port 8080)...
start "WROS Backend" cmd /k "cd OnboardingModule-Backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload"

timeout /t 3 /nobreak

REM Start frontend in new window
echo.
echo [STEP 5] Starting frontend server (port 3000)...
start "WROS Frontend" cmd /k "cd OnboardingModule-Frontend-main && npm start"

echo.
echo ========================================
echo STARTUP COMPLETE
echo ========================================
echo.
echo Backend:  http://localhost:8080
echo Frontend: http://localhost:3000
echo.
echo Test Credentials:
echo   CEO:     am@blitzenx.com / Am@123
echo   CFO:     cfotest@blitzenx.com / CFO@123
echo   Partner: partnertest@blitzenx.com / Partner@123
echo.
echo Press Ctrl+C to stop either server window, or close them manually.
echo ========================================
echo.

pause
