@echo off
setlocal
cd /d "%~dp0"
if not exist "creator-dashboard\.venv\Scripts\python.exe" (
  echo [ERROR] Jalankan setup-core.bat terlebih dahulu.
  exit /b 1
)
"creator-dashboard\.venv\Scripts\python.exe" "creator-dashboard\local_check.py"
exit /b %errorlevel%
