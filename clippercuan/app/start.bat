@echo off
setlocal
title ClipperCuan
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" 2>nul
if errorlevel 1 (
  echo Python 3.10+ belum terpasang.
  echo Unduh dari https://www.python.org/downloads/  ^(centang "Add Python to PATH"^), lalu jalankan file ini lagi.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo [1/2] Menyiapkan lingkungan pertama kali, mohon tunggu beberapa menit...
  %PY% -m venv .venv || goto :fail
  ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
)
echo Memeriksa dependency ClipperCuan...
".venv\Scripts\python.exe" -c "import fastapi,uvicorn,yt_dlp,numpy,cv2,faster_whisper" >nul 2>nul
if errorlevel 1 (
  echo Dependency belum lengkap. Memasang requirements ke environment ClipperCuan...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
)
echo Memperbarui pengunduh video...
".venv\Scripts\python.exe" -m pip install -q -U yt-dlp || echo Peringatan: yt-dlp tidak dapat diperbarui; versi terpasang tetap dipakai.
echo [2/2] Membuka ClipperCuan...
".venv\Scripts\python.exe" -m clipper %*
exit /b 0
:fail
echo.
echo Instalasi gagal. Periksa koneksi internet lalu coba lagi.
pause
exit /b 1
