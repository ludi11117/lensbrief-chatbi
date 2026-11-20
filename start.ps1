param(
    [ValidateRange(1024, 65535)][int]$Port = 8080,
    [string]$CacheRoot = 'D:\CodexWork\cache',
    [string]$TempRoot = 'D:\CodexWork\temp'
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

Push-Location $PSScriptRoot
try {
    New-Item -ItemType Directory -Force $CacheRoot,$TempRoot | Out-Null
    $env:TEMP = $TempRoot
    $env:TMP = $TempRoot
    $env:npm_config_cache = Join-Path $CacheRoot 'npm'
    $env:PIP_CACHE_DIR = Join-Path $CacheRoot 'pip'
    $python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $python)) { python -m venv .venv }
    & $python -m pip install -q -r backend/requirements.txt

    Push-Location frontend
    try {
        npm.cmd ci --no-audit --no-fund
        npm.cmd run build
    } finally { Pop-Location }

    $env:LENSBRIEF_FRONTEND_DIST = Join-Path $PSScriptRoot 'frontend/dist'
    & $python -m alembic -c backend/alembic.ini upgrade head
    & $python -m backend.scripts.seed
    & $python -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port $Port
} finally { Pop-Location }
