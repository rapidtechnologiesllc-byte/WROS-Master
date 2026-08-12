@echo off
REM Alternate-port launcher for running a second WROS frontend session
REM alongside another Claude Code chat's server, without touching
REM start-dev.cmd or .env.development (both shared with that session).
cd /d "%~dp0"
set "PATH=C:\Program Files\nodejs;%PATH%"
set "PORT=3010"
set "REACT_APP_API_BASE_URL=http://localhost:8090"
call "C:\Program Files\nodejs\npm.cmd" start
