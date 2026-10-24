@echo off
setlocal
cd /d "%~dp0"
set "DASHBOARD_HOST=127.0.0.1"
set "DASHBOARD_PORT=3210"

where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py"
) else (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
  echo [ERROR] Python tidak ditemukan. Install Python 3.11 atau lebih baru.
  pause
  exit /b 1
)

echo.
echo  Creator Control Center
echo  http://%DASHBOARD_HOST%:%DASHBOARD_PORT%
echo.
set "CREATOR_DASHBOARD_HOST=%DASHBOARD_HOST%"
set "CREATOR_DASHBOARD_PORT=%DASHBOARD_PORT%"
%PYTHON_CMD% creator-dashboard\server.py

if errorlevel 1 (
  echo.
  echo [ERROR] Dashboard berhenti dengan error.
  pause
)
