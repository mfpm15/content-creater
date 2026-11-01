@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 goto :missing_uv
where node >nul 2>nul
if errorlevel 1 goto :missing_node
where npm >nul 2>nul
if errorlevel 1 goto :missing_node
where ffmpeg >nul 2>nul
if errorlevel 1 goto :missing_ffmpeg
where ffprobe >nul 2>nul
if errorlevel 1 goto :missing_ffmpeg
node -e "process.exit(Number(process.versions.node.split('.')[0])>=22?0:1)"
if errorlevel 1 goto :missing_node

echo [1/4] Dashboard, artikel, Analytics dan review...
if not exist "creator-dashboard\.venv\Scripts\python.exe" (
  uv venv --python 3.12 "creator-dashboard\.venv"
  if errorlevel 1 goto :failed
)
uv pip install --python "creator-dashboard\.venv\Scripts\python.exe" -r "creator-dashboard\requirements-review.txt"
if errorlevel 1 goto :failed

echo [2/4] ClipperCuan...
if not exist "clippercuan\app\.venv\Scripts\python.exe" (
  uv venv --python 3.12 "clippercuan\app\.venv"
  if errorlevel 1 goto :failed
)
uv pip install --python "clippercuan\app\.venv\Scripts\python.exe" -r "clippercuan\app\requirements.txt"
if errorlevel 1 goto :failed

echo [3/4] HyperFrames dari lockfile...
set "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1"
set "PUPPETEER_SKIP_DOWNLOAD=1"
set "HYPERFRAMES_NO_TELEMETRY=1"
pushd "creator-dashboard\apps\hyperframes"
call npm ci --no-audit --no-fund
if errorlevel 1 (popd & goto :failed)
popd

echo [4/4] Environment suara Opuscar...
if not exist "creator-dashboard\apps\lemo-opuscar\.venv\Scripts\python.exe" (
  uv venv --python 3.12 "creator-dashboard\apps\lemo-opuscar\.venv"
  if errorlevel 1 goto :failed
)
uv pip install --python "creator-dashboard\apps\lemo-opuscar\.venv\Scripts\python.exe" numpy soundfile edge-tts
if errorlevel 1 goto :failed
"creator-dashboard\.venv\Scripts\python.exe" -c "import sys; sys.path.insert(0,'creator-dashboard'); from runtime_config import find_browser; print('Browser:', find_browser() or 'Install Chrome atau Edge untuk render/review')"
if errorlevel 1 goto :failed
echo.
echo Setup inti selesai. Jalankan start-dashboard.bat.
echo Lottie + mode Naskah sendiri dapat berjalan tanpa API key.
echo TTS daring dan riset web tetap memerlukan akses layanan masing-masing.
exit /b 0
:missing_uv
echo [ERROR] Install uv dari https://docs.astral.sh/uv/
exit /b 1
:missing_node
echo [ERROR] Install Node.js 22 atau lebih baru, beserta npm.
exit /b 1
:missing_ffmpeg
echo [ERROR] FFmpeg dan FFprobe harus tersedia di PATH.
exit /b 1
:failed
echo [ERROR] Setup inti gagal. Periksa pesan di atas; jangan kirim API key di chat.
exit /b 1
