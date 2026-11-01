param(
    [string]$Version = (Get-Date -Format "yyyyMMdd-HHmm"),
    [switch]$KeepStaging
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StagingRoot = Join-Path $Root "_package-staging"
$PackageName = "creator-control-center-$Version"
$Staging = Join-Path $StagingRoot $PackageName
$Archive = Join-Path $Root "$PackageName.zip"

$ExcludedDirs = @(
    ".git", ".data", ".ui-audit", "_package-staging", "node_modules",
    ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".runtime", ".pnpm-store", ".uv-cache", ".next",
    "dist", "dist-electron", "build", "release", "coverage", "htmlcov",
    "output", "outputs", "exports", "renders", "projects", "uploads",
    "tmp", "cache", "storage", ".hyperframes", ".thumbnails"
)
$ExcludedNames = @(".env", "config.toml", ".coverage", "Thumbs.db", ".DS_Store", "desktop.ini")
$ExcludedExtensions = @(
    ".pyc", ".pyo", ".log", ".tmp", ".temp", ".bak", ".key", ".pem", ".pfx",
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v",
    ".mp3", ".m4a", ".aac", ".wav", ".flac"
)

if (Test-Path $StagingRoot) { Remove-Item $StagingRoot -Recurse -Force }
if (Test-Path $Archive) { Remove-Item $Archive -Force }
New-Item -ItemType Directory -Path $Staging | Out-Null

$RootPrefix = $Root.TrimEnd("\") + "\"
Get-ChildItem -LiteralPath $Root -File -Recurse -Force | ForEach-Object {
    $relative = $_.FullName.Substring($RootPrefix.Length)
    $parts = $relative -split "[\\/]"
    $isGeneratedArchive = $_.DirectoryName -eq $Root -and $_.Name -like "creator-control-center-*.zip"
    $isEnvVariant = $_.Name -like ".env*" -and $_.Name -ne ".env.example"
    $excluded = $isGeneratedArchive -or $isEnvVariant -or
        ($parts | Where-Object { $_ -in $ExcludedDirs }) -or
        ($_.Name -in $ExcludedNames) -or
        ($_.Extension.ToLowerInvariant() -in $ExcludedExtensions)
    if (-not $excluded) {
        $destination = Join-Path $Staging $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $destination
    }
}

$forbidden = Get-ChildItem -LiteralPath $Staging -File -Recurse -Force | Where-Object {
    ($_.Name -like ".env*" -and $_.Name -ne ".env.example") -or
    $_.Name -eq "config.toml" -or
    $_.Extension.ToLowerInvariant() -in @(".key", ".pem", ".pfx", ".mp4", ".mp3", ".wav") -or
    $_.FullName -match "[\\/](node_modules|\.venv|\.data|__pycache__)[\\/]"
}
if ($forbidden) {
    $forbidden | ForEach-Object { Write-Error "File terlarang masuk staging: $($_.FullName)" }
    throw "Validasi paket gagal."
}

Compress-Archive -LiteralPath $Staging -DestinationPath $Archive -CompressionLevel Optimal
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Archive).Hash
$size = [math]::Round((Get-Item $Archive).Length / 1MB, 2)
Write-Host "Paket bersih selesai: $Archive"
Write-Host "Ukuran: $size MB"
Write-Host "SHA256: $hash"

if (-not $KeepStaging) { Remove-Item $StagingRoot -Recurse -Force }
