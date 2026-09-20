#requires -Version 5
# Local dev launcher: shared Postgres (docker) + uvicorn (--reload) + vite frontend.
#
# Ported from travel/dev.ps1, changed only where food's arrangement differs:
# this app has no docker-compose.yml of its own - the container is
# cg1618-dev-db, owned by the PLATFORM's compose project, with a `food`
# database created inside it by the platform's provisioning (see
# .env.example). So this script brings that project up rather than owning a
# compose file of its own, and never touches its volume.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$dbContainer = 'cg1618-dev-db'
$backendPort = 8001
$frontendUrl = 'http://localhost:5174/'

# --- Guard: a leftover backend on :8001 makes the new uvicorn die with WinError 10048,
# --- which surfaces only as vite "ECONNREFUSED 127.0.0.1:8001" proxy errors. Ports are
# --- box-wide (see apps.yml) - this must abort rather than fall back to another port,
# --- or it would silently take a slot another app on this laptop owns.
$stale = Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue
if ($stale) {
    $owner = Get-Process -Id $stale[0].OwningProcess -ErrorAction SilentlyContinue
    Write-Host "==> Port $backendPort is already in use by $($owner.ProcessName) (PID $($stale[0].OwningProcess))." -ForegroundColor Yellow
    Write-Host '    Close that uvicorn window first, or run:' -ForegroundColor Yellow
    Write-Host "      Stop-Process -Id $($stale[0].OwningProcess) -Force" -ForegroundColor Yellow
    throw "Backend port $backendPort is occupied - aborting so the new server does not fail to bind."
}

# --- Guard: a native PostgreSQL service binds 5432 too and usually wins the race
# --- against the container. Everything below would still report success - the
# --- pg_isready check runs *inside* the container - while uvicorn silently talks
# --- to the native server's separate, usually empty database.
$nativeSvc = @(Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue |
               Where-Object { $_.Status -eq 'Running' })
$nativeProc = @(Get-NetTCPConnection -LocalPort 5432 -State Listen -ErrorAction SilentlyContinue |
                ForEach-Object { Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue } |
                Where-Object { $_.ProcessName -eq 'postgres' })
if ($nativeSvc -or $nativeProc) {
    Write-Host '==> A native PostgreSQL server is running on this machine.' -ForegroundColor Yellow
    foreach ($s in $nativeSvc) { Write-Host "      service: $($s.Name) ($($s.Status))" -ForegroundColor Yellow }
    foreach ($p in $nativeProc) { Write-Host "      process: $($p.ProcessName) (PID $($p.Id)) listening on 5432" -ForegroundColor Yellow }
    Write-Host '    It will shadow the docker container on port 5432, and the app' -ForegroundColor Yellow
    Write-Host '    would run against the wrong database without saying so. Stop it from an' -ForegroundColor Yellow
    Write-Host '    elevated PowerShell:' -ForegroundColor Yellow
    if ($nativeSvc) {
        $names = ($nativeSvc | ForEach-Object { $_.Name }) -join ', '
        Write-Host "      Stop-Service $names -Force" -ForegroundColor Yellow
        Write-Host "      Set-Service $names -StartupType Manual" -ForegroundColor Yellow
    }
    throw 'A native PostgreSQL server would shadow the container - aborting.'
}

# --- The development database belongs to the PLATFORM, not to any app. One
# --- server holds one database per app, and it lives in the platform's own
# --- compose project so that `docker compose down` in an app's tree cannot
# --- remove the server every other app is using. It used to be
# --- anime_site_postgres_db inside media's project, which is exactly how that
# --- happened. See the platform's docs/registry.md.
$platformDir = Split-Path $root -Parent
$dbCompose = Join-Path $platformDir 'docker-compose.dev-db.yml'
if (-not (Test-Path $dbCompose)) {
    throw "Not found: $dbCompose. This checkout is expected to sit inside the platform checkout as cg1618\<app>. If it does not, start the database yourself with the platform's .\dev-db.cmd and re-run this."
}

Write-Host "==> Starting PostgreSQL ($dbContainer)" -ForegroundColor Cyan
# --- `up -d`, not `docker start`: it CREATES the container when it is absent,
# --- which is the state on a fresh machine and after the platform's
# --- dev-db.cmd -Down. `docker start` fails there with "no such container",
# --- which reads as a broken script rather than an absent container.
docker compose -f $dbCompose up -d | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Could not start $dbContainer - is Docker Desktop running, and are POSTGRES_USER, POSTGRES_PASSWORD and POSTGRES_DB set in the platform's .env?"
}

# --- Wait for Postgres to accept connections. create_engine is lazy, so nothing
# --- touches the database at import time and uvicorn binds its port whether the
# --- container is up or not - the failure surfaces per request instead, as an
# --- /health that answers 503 until the database is ready. Waiting here is
# --- what makes the first page load work rather than look broken.
Write-Host '==> Waiting for PostgreSQL to accept connections' -NoNewline -ForegroundColor Cyan
$dbReady = $false
foreach ($i in 1..60) {
    docker exec $dbContainer pg_isready -q 2>$null
    if ($LASTEXITCODE -eq 0) { $dbReady = $true; break }
    Write-Host '.' -NoNewline
    Start-Sleep -Milliseconds 500
}
Write-Host ''
if (-not $dbReady) { throw "PostgreSQL ($dbContainer) did not become ready within 30s." }

Write-Host '==> Opening dev window: uvicorn | vite' -ForegroundColor Cyan
$uvicorn = "& '$root\venv\Scripts\uvicorn.exe' app.main:app --reload --reload-dir app --port $backendPort"

wt.exe new-tab -d "$root" --title uvicorn powershell -NoExit -Command $uvicorn `; split-pane -V -d "$root\frontend" --title frontend powershell -NoExit -Command "npm run dev"

# --- Don't report ready until the backend actually holds its port, otherwise opening
# --- the site too early produces a page full of failed /api requests.
Write-Host "==> Waiting for backend on http://127.0.0.1:$backendPort" -NoNewline -ForegroundColor Cyan
$apiReady = $false
foreach ($i in 1..120) {
    try {
        Invoke-WebRequest "http://127.0.0.1:$backendPort/health" -UseBasicParsing -TimeoutSec 2 | Out-Null
        $apiReady = $true; break
    } catch {
        if ($_.Exception.Response) { $apiReady = $true; break }  # responding, just non-2xx
    }
    Write-Host '.' -NoNewline
    Start-Sleep -Milliseconds 500
}
Write-Host ''
if ($apiReady) {
    Write-Host "==> Ready: $frontendUrl" -ForegroundColor Green
} else {
    Write-Host '==> Backend did not respond within 60s - check the uvicorn pane for errors.' -ForegroundColor Red
}
