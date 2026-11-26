<#
.SYNOPSIS
    Safe local/staging deployment script for GO BEYOND.
.DESCRIPTION
    Validates .env configuration, verifies Docker Compose YAML, builds images cleanly
    (never deleting volumes or executing destructive migrations), starts all 8 containers,
    and waits for health_check.ps1 to confirm readiness across all subsystems.
#>
[CmdletBinding()]
param(
    [ValidateSet("local", "staging", "production")]
    [string]$Mode = "local",
    [string]$EnvFile = ".env",
    [int]$HealthTimeoutSeconds = 120,
    [switch]$NoBuild,
    [switch]$ProdOverlay
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-NativeChecked([scriptblock]$ScriptBlock, [string]$ErrorMessage) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $ScriptBlock
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $prev
    }
    if ($code -ne 0) {
        throw "$ErrorMessage (exit code $code)"
    }
}

Write-Host "=== GO BEYOND Deployment Automation (Mode=$Mode, ProdOverlay=$ProdOverlay) ===" -ForegroundColor Cyan

if (-not (Test-Path $EnvFile)) {
    throw "Environment file '$EnvFile' not found. Copy .env.example (local), .env.staging.example, or .env.production.example to .env first."
}

# 1. Validate environment configuration without printing secrets
$pythonExe = if (Test-Path "backend\.venv\Scripts\python.exe") { "backend\.venv\Scripts\python.exe" } else { "python" }
Invoke-NativeChecked { & $pythonExe "scripts\validate_env.py" --env-file $EnvFile --mode $Mode } "Environment validation failed"

# 2. Verify Docker daemon & Compose configuration
Invoke-NativeChecked { cmd /c "docker info >nul 2>&1" } "Docker daemon is not reachable"

$composeFiles = @("-f", "docker-compose.yml")
if ($ProdOverlay) {
    $composeFiles += @("-f", "docker-compose.prod.yml")
}

Invoke-NativeChecked { docker compose @composeFiles config --quiet } "Docker Compose configuration validation failed"

# 3. Build images (unless -NoBuild) and start stack safely without removing volumes
if (-not $NoBuild) {
    Write-Host "[DEPLOY] Building backend & frontend images..." -ForegroundColor Cyan
    Invoke-NativeChecked { docker compose @composeFiles build } "Docker build failed"
}

Write-Host "[DEPLOY] Starting / updating containers safely..." -ForegroundColor Cyan
Invoke-NativeChecked { docker compose @composeFiles up -d } "docker compose up -d failed"
Invoke-NativeChecked { docker compose @composeFiles restart nginx } "docker compose restart nginx failed"

# 4. Run full health, migration, heartbeat, NGINX, and monitoring verification
& "$PSScriptRoot\health_check.ps1" -WaitSeconds $HealthTimeoutSeconds
if ($LASTEXITCODE -ne 0) {
    throw "Post-deployment health verification failed."
}

Write-Host "=== Deployment Status ===" -ForegroundColor Green
Invoke-NativeChecked { docker compose @composeFiles ps --format "table {{.Name}}`t{{.Status}}`t{{.Ports}}" } "docker compose ps failed"
