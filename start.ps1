param(
    [ValidateRange(1024, 65535)][int]$Port = 8080,
    [string]$CacheRoot,
    [string]$TempRoot,
    [switch]$Offline
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$runtimeRoot = if (Test-Path -LiteralPath 'D:\') { 'D:\CodexWork' } else { Join-Path $PSScriptRoot '.runtime' }
if (-not $CacheRoot) { $CacheRoot = Join-Path $runtimeRoot 'cache' }
if (-not $TempRoot) { $TempRoot = Join-Path $runtimeRoot 'temp' }

Push-Location $PSScriptRoot
try {
    New-Item -ItemType Directory -Force $CacheRoot,$TempRoot | Out-Null
    $env:TEMP = $TempRoot
    $env:TMP = $TempRoot
    $env:npm_config_cache = Join-Path $CacheRoot 'npm'
    $env:PIP_CACHE_DIR = Join-Path $CacheRoot 'pip'
    $python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if ($Offline) {
        if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath 'frontend/node_modules/.bin/vite.cmd')) {
            throw 'Run start.ps1 once online to install the project dependencies before using -Offline.'
        }
        $env:LENSBRIEF_DRAFT_MODE = 'mock'
        $env:LENSBRIEF_PLANNER_MODE = 'rules'
    } else {
        if (-not (Test-Path -LiteralPath $python)) { python -m venv .venv }
        & $python -m pip install -q -r backend/requirements.txt
    }

    Push-Location frontend
    try {
        if (-not $Offline) { npm.cmd ci --no-audit --no-fund }
        npm.cmd run build
    } finally { Pop-Location }

    $env:LENSBRIEF_FRONTEND_DIST = Join-Path $PSScriptRoot 'frontend/dist'
    & $python -m alembic -c backend/alembic.ini upgrade head
    & $python -m backend.scripts.seed
    & $python -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port $Port
} finally { Pop-Location }
