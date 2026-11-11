#Requires -Version 5.1
<#
.SYNOPSIS
    Starts (or stops) VISTIQ's backend and frontend dev servers locally.

.DESCRIPTION
    Convenience script only - it does not create, modify, or regenerate
    .env, the SQLite database, the backend virtual environment, or
    node_modules. It expects everything to already be set up (see
    docs/virtual-tryon.md and the root README's "How to run" sections for
    first-time setup). It never contains or prints any credential.

    Backend:  http://127.0.0.1:8000
    Frontend: http://127.0.0.1:5173

    Both bind to 127.0.0.1 specifically (not "localhost") - the frontend's
    session cookie is SameSite-scoped, and localhost/127.0.0.1 are treated
    as different sites by the browser, which silently breaks login if the
    two servers don't agree on which one to use.

.PARAMETER Stop
    Stops VISTIQ's backend and frontend dev servers (identified by the
    ports they listen on) instead of starting them. Safe: it only targets
    processes actually LISTENING on 127.0.0.1:8000 / 127.0.0.1:5173, never
    a blanket process-name kill.

.EXAMPLE
    .\start-vistiq.ps1
.EXAMPLE
    .\start-vistiq.ps1 -Stop
#>

param(
    [switch]$Stop
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot 'vistiq-backend'
$FrontendDir = Join-Path $ProjectRoot 'vistiq-frontend'
$BackendPort = 8000
$FrontendPort = 5173

function ConvertTo-SingleQuotedLiteral {
    # Wraps a path in single quotes for safe embedding inside a PowerShell
    # command string passed to a new process - single-quoted strings treat
    # backslashes literally, so a Windows path round-trips exactly as-is.
    param([string]$Value)
    return "'" + ($Value -replace "'", "''") + "'"
}

function Get-ListeningProcessId {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalAddress -eq '127.0.0.1' -or $_.LocalAddress -eq '0.0.0.0' } |
        Select-Object -First 1
    if ($conn) { return $conn.OwningProcess }
    return $null
}

if ($Stop) {
    Write-Host 'Stopping VISTIQ dev servers...' -ForegroundColor Cyan
    $targets = @(
        @{ Name = 'backend (FastAPI)'; Port = $BackendPort },
        @{ Name = 'frontend (Vite)'; Port = $FrontendPort }
    )
    foreach ($entry in $targets) {
        $procId = Get-ListeningProcessId -Port $entry.Port
        if ($null -eq $procId) {
            Write-Host ('  {0}: nothing listening on port {1}.' -f $entry.Name, $entry.Port) -ForegroundColor DarkGray
            continue
        }
        try {
            Stop-Process -Id $procId -Confirm:$false -ErrorAction Stop
            Write-Host ('  {0}: stopped process {1} on port {2}.' -f $entry.Name, $procId, $entry.Port) -ForegroundColor Green
        } catch {
            Write-Host ('  {0}: failed to stop process {1}: {2}' -f $entry.Name, $procId, $_.Exception.Message) -ForegroundColor Red
        }
    }
    return
}

Write-Host 'VISTIQ local startup' -ForegroundColor Cyan
Write-Host ('Project root: {0}' -f $ProjectRoot)

# --- Preconditions - fail fast with a clear message rather than half-start ---
$activateScript = Join-Path $BackendDir '.venv\Scripts\Activate.ps1'
if (-not (Test-Path $activateScript)) {
    Write-Host ('Backend virtual environment not found at: {0}' -f $activateScript) -ForegroundColor Red
    Write-Host 'First-time setup (run once):' -ForegroundColor Yellow
    Write-Host ('  cd {0}; python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt' -f $BackendDir)
    exit 1
}

$envFile = Join-Path $BackendDir '.env'
if (-not (Test-Path $envFile)) {
    Write-Host ('Warning: {0} not found - the backend will start with every' -f $envFile) -ForegroundColor Yellow
    Write-Host 'optional setting at its default (Virtual Try-On will report honestly' -ForegroundColor Yellow
    Write-Host 'unavailable until a worker URL/token is configured). Copy .env.example' -ForegroundColor Yellow
    Write-Host 'to .env and fill it in if you need Try-On working.' -ForegroundColor Yellow
}

$nodeModulesDir = Join-Path $FrontendDir 'node_modules'
if (-not (Test-Path $nodeModulesDir)) {
    Write-Host ('Frontend dependencies not installed at: {0}' -f $nodeModulesDir) -ForegroundColor Red
    Write-Host ('Run once: cd {0}; npm install' -f $FrontendDir) -ForegroundColor Yellow
    exit 1
}

# --- Backend ---
$existingBackendPid = Get-ListeningProcessId -Port $BackendPort
if ($existingBackendPid) {
    Write-Host ('Backend already running (process {0} on port {1}) - not starting a second one.' -f $existingBackendPid, $BackendPort) -ForegroundColor Yellow
} else {
    Write-Host ('Starting backend on http://127.0.0.1:{0} ...' -f $BackendPort) -ForegroundColor Cyan
    $backendCommand = 'Set-Location -LiteralPath {0}; & {1}; python -m uvicorn app.main:app --host 127.0.0.1 --port {2}' -f
        (ConvertTo-SingleQuotedLiteral $BackendDir), (ConvertTo-SingleQuotedLiteral $activateScript), $BackendPort
    try {
        Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendCommand -ErrorAction Stop
    } catch {
        Write-Host ('Failed to start backend: {0}' -f $_.Exception.Message) -ForegroundColor Red
        exit 1
    }
}

# --- Frontend ---
$existingFrontendPid = Get-ListeningProcessId -Port $FrontendPort
if ($existingFrontendPid) {
    Write-Host ('Frontend already running (process {0} on port {1}) - not starting a second one.' -f $existingFrontendPid, $FrontendPort) -ForegroundColor Yellow
} else {
    Write-Host ('Starting frontend on http://127.0.0.1:{0} ...' -f $FrontendPort) -ForegroundColor Cyan
    $frontendCommand = 'Set-Location -LiteralPath {0}; npm run dev -- --host 127.0.0.1 --port {1}' -f
        (ConvertTo-SingleQuotedLiteral $FrontendDir), $FrontendPort
    try {
        Start-Process powershell -ArgumentList '-NoExit', '-Command', $frontendCommand -ErrorAction Stop
    } catch {
        Write-Host ('Failed to start frontend: {0}' -f $_.Exception.Message) -ForegroundColor Red
        exit 1
    }
}

Write-Host ''
Write-Host ('Backend:  http://127.0.0.1:{0}  (health check: http://127.0.0.1:{0}/health)' -f $BackendPort) -ForegroundColor Green
Write-Host ('Frontend: http://127.0.0.1:{0}' -f $FrontendPort) -ForegroundColor Green
Write-Host ''
Write-Host 'Each server runs in its own new PowerShell window - close those windows, or run' -ForegroundColor DarkGray
Write-Host '  .\start-vistiq.ps1 -Stop' -ForegroundColor DarkGray
Write-Host 'to stop them from here instead.' -ForegroundColor DarkGray
Write-Host ''
Write-Host 'The CatVTON GPU worker (Colab) is separate and not managed by this script -' -ForegroundColor DarkGray
Write-Host 'see docs/virtual-tryon.md sections 6 and 9 to connect it.' -ForegroundColor DarkGray
