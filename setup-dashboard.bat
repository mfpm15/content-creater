@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo Creator Control Center - Dependency Setup
echo ============================================================
echo.

where uv >nul 2>nul
if errorlevel 1 (
  echo [ERROR] uv belum tersedia. Install dari https://docs.astral.sh/uv/
  goto :failed
)

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js belum tersedia. OpenCreator memerlukan Node.js 22+.
  goto :failed
)

echo [1/4] Menyiapkan MoneyPrinterTurbo...
pushd creator-dashboard\apps\moneyprinterturbo
uv sync --frozen
if errorlevel 1 (popd & goto :failed)
popd

echo [2/4] Menyiapkan Podcastfy dengan Python 3.11...
pushd creator-dashboard\apps\podcastfy
if not exist .venv\Scripts\python.exe (
  uv venv --python 3.11 .venv
  if errorlevel 1 (popd & goto :failed)
)
rem Gunakan metadata pyproject.toml. requirements.txt upstream berisi pin lama
rem yang tidak dapat diselesaikan oleh package index saat ini.
uv pip install --python .venv\Scripts\python.exe -e .
if errorlevel 1 (popd & goto :failed)
rem Endpoint dashboard memakai modul API opsional yang belum tercantum dalam
rem dependency utama pyproject.toml.
uv pip install --python .venv\Scripts\python.exe fastapi==0.103.0 uvicorn==0.23.2 pyyaml==6.0.2 playwright
if errorlevel 1 (popd & goto :failed)
popd

echo [3/4] Menyiapkan AI YouTube Shorts Generator dengan Python 3.11...
pushd creator-dashboard\apps\ai-youtube-shorts-generator
if not exist .venv\Scripts\python.exe (
  uv venv --python 3.11 .venv
  if errorlevel 1 (popd & goto :failed)
)
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
if errorlevel 1 (popd & goto :failed)
echo     Dependensi local-mode bersifat opsional dan cukup besar.
popd

echo [4/4] Menyiapkan aplikasi Node.js...
rem Buat shim pnpm lokal untuk script workspace OpenCreator. Corepack dapat
rem dijalankan tanpa hak administrator, sementara lifecycle script tetap
rem menemukan perintah pnpm melalui PATH workspace.
if not exist creator-dashboard\bin mkdir creator-dashboard\bin
>creator-dashboard\bin\pnpm.cmd echo @echo off
>>creator-dashboard\bin\pnpm.cmd echo corepack pnpm %%*
set "PATH=%CD%\creator-dashboard\bin;%PATH%"
pushd creator-dashboard\apps\opencreator
call corepack pnpm install --frozen-lockfile
if errorlevel 1 (popd & goto :failed)
popd
pushd creator-dashboard\apps\short-video-factory
call corepack pnpm install --frozen-lockfile
if errorlevel 1 (popd & goto :failed)
popd

echo.
echo ============================================================
echo Setup dasar selesai.
echo Jalankan start-dashboard.bat untuk membuka dashboard.
echo Isi API key masing-masing repository sebelum membuat konten.
echo ============================================================
exit /b 0

:failed
echo.
echo [ERROR] Setup berhenti. Periksa pesan error di atas.
exit /b 1
