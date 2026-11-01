param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')]
    [string]$Version = (Get-Date -Format "yyyyMMdd-HHmm"),
    [switch]$KeepStaging
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExecutable = Join-Path $Root "creator-dashboard\.venv\Scripts\python.exe"
$PackageArguments = @((Join-Path $Root "creator-dashboard\package_source.py"), "--version", $Version)
if (-not (Test-Path -LiteralPath $PythonExecutable)) {
    $Launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($Launcher) {
        $PythonExecutable = $Launcher.Source
        $PackageArguments = @("-3") + $PackageArguments
    } else {
        $Launcher = Get-Command python.exe -ErrorAction SilentlyContinue
        if (-not $Launcher) { throw "Python 3.11+ tidak ditemukan. Jalankan setup-core.bat dahulu." }
        $PythonExecutable = $Launcher.Source
    }
}
if ($KeepStaging) { $PackageArguments += "--keep-staging" }
& $PythonExecutable @PackageArguments
if ($LASTEXITCODE -ne 0) { throw "Pembuatan paket gagal; arsip belum siap dibagikan." }
