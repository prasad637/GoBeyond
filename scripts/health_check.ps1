<#
.SYNOPSIS
    Comprehensive stack health, migration, worker heartbeat, NGINX, and monitoring verification script.
#>
[CmdletBinding()]
param(
    [int]$WaitSeconds = 30,
    [string]$BaseUrl = "http://localhost",
    [string]$PrometheusUrl = "http://localhost:9090",
    [string]$GrafanaUrl = "http://localhost:3001"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-NativeCapture([scriptblock]$ScriptBlock) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $raw = & $ScriptBlock 2>&1
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $prev
    }
    $lines = @($raw | ForEach-Object { $_.ToString() })
    return @{ Code = $code; Lines = $lines; Text = ($lines -join "`n") }
}

$expectedContainers = @(
    "gobeyond-postgres",
    "gobeyond-redis",
    "gobeyond-backend",
    "gobeyond-worker",
    "gobeyond-frontend",
    "gobeyond-nginx",
    "gobeyond-prometheus",
    "gobeyond-grafana"
)

$deadline = (Get-Date).AddSeconds($WaitSeconds)

Write-Host "[HEALTH] Checking 8 Docker Compose services (timeout ${WaitSeconds}s)..." -ForegroundColor Cyan
while ($true) {
    $psCap = Invoke-NativeCapture { docker compose ps --format json }
    $states = @{}
    foreach ($line in $psCap.Lines) {
        if (-not $line.Trim().StartsWith("{")) { continue }
        $obj = $line | ConvertFrom-Json
        $states[$obj.Name] = $obj
    }

    $pending = @()
    foreach ($name in $expectedContainers) {
        if (-not $states.ContainsKey($name)) {
            $pending += "$name=missing"
            continue
        }
        $item = $states[$name]
        if ($item.State -ne "running" -or $item.Health -ne "healthy") {
            $pending += "$name=$($item.State)/$($item.Health)"
        }
    }

    if ($pending.Count -eq 0) {
        break
    }

    if ((Get-Date) -ge $deadline) {
        Write-Error ("Services failed to become healthy within ${WaitSeconds}s: " + ($pending -join ", "))
        exit 1
    }
    Start-Sleep -Seconds 3
}

Write-Host "[PASS] All 8 containers running and healthy." -ForegroundColor Green

function Get-HttpStatus([string]$Url) {
    try {
        $resp = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
        return @{ Code = [int]$resp.StatusCode; Content = $resp.Content }
    }
    catch {
        if ($_.Exception.Response) {
            return @{ Code = [int]$_.Exception.Response.StatusCode; Content = "" }
        }
        throw
    }
}

$failures = @()

# 1. NGINX & Public Routes
$nginxHealth = Get-HttpStatus "$BaseUrl/nginx-health"
if ($nginxHealth.Code -ne 200) { $failures += "/nginx-health returned $($nginxHealth.Code)" }

$backendHealth = Get-HttpStatus "$BaseUrl/health"
if ($backendHealth.Code -ne 200) { $failures += "/health returned $($backendHealth.Code)" }

$readyResp = Get-HttpStatus "$BaseUrl/health/ready"
if ($readyResp.Code -ne 200) {
    $failures += "/health/ready returned $($readyResp.Code)"
}
else {
    $readyObj = $readyResp.Content | ConvertFrom-Json
    if (-not $readyObj.ready -or $readyObj.components.database -ne "CONNECTED" -or $readyObj.components.redis -ne "CONNECTED") {
        $failures += "/health/ready payload not connected: $($readyResp.Content)"
    }
}

$frontendRoot = Get-HttpStatus "$BaseUrl/"
if ($frontendRoot.Code -ne 200) { $failures += "Frontend / returned $($frontendRoot.Code)" }

$discoveryHome = Get-HttpStatus "$BaseUrl/api/v1/discovery/home?city_slug=hyderabad"
if ($discoveryHome.Code -ne 200) { $failures += "Discovery API returned $($discoveryHome.Code)" }

# 2. NGINX Security Guard (External /metrics & /health/detailed must be 403)
$extMetrics = Get-HttpStatus "$BaseUrl/metrics"
if ($extMetrics.Code -ne 403) { $failures += "External /metrics expected 403, got $($extMetrics.Code)" }

$extDetailed = Get-HttpStatus "$BaseUrl/health/detailed"
if ($extDetailed.Code -ne 403) { $failures += "External /health/detailed expected 403, got $($extDetailed.Code)" }

# 3. Alembic Migration Head Check
$alembicRes = Invoke-NativeCapture { docker exec gobeyond-backend alembic current }
if ($alembicRes.Code -ne 0 -or $alembicRes.Text -notmatch '\(head\)') {
    $failures += "Alembic is not at head: $($alembicRes.Text)"
}

# 4. ARQ Worker Heartbeat Check (wait up to 12s if worker just started)
$hbExists = "0"
for ($i = 0; $i -lt 6; $i++) {
    $hbRes = Invoke-NativeCapture { docker exec gobeyond-redis redis-cli EXISTS gobeyond:worker:heartbeat }
    $hbExists = $hbRes.Text.Trim()
    if ($hbExists -eq "1") { break }
    Start-Sleep -Seconds 2
}
if ($hbExists -ne "1") { $failures += "Worker Redis heartbeat key gobeyond:worker:heartbeat missing" }

# 5. Prometheus Target & Rules Check
$promTargets = Get-HttpStatus "$PrometheusUrl/api/v1/targets"
if ($promTargets.Code -ne 200) {
    $failures += "Prometheus targets returned $($promTargets.Code)"
}
else {
    $tJson = $promTargets.Content | ConvertFrom-Json
    $beTarget = $tJson.data.activeTargets | Where-Object { $_.labels.job -eq "gobeyond-backend" } | Select-Object -First 1
    if (-not $beTarget -or $beTarget.health -ne "up") {
        $failures += "Prometheus backend target not up"
    }
}

$promRules = Get-HttpStatus "$PrometheusUrl/api/v1/rules"
if ($promRules.Code -ne 200) {
    $failures += "Prometheus /api/v1/rules returned $($promRules.Code)"
}
else {
    $rJson = $promRules.Content | ConvertFrom-Json
    $ruleCount = @($rJson.data.groups | ForEach-Object { $_.rules }).Count
    if ($ruleCount -lt 10) {
        $failures += "Prometheus expected >= 10 alert rules, found $ruleCount"
    }
}

# 6. Grafana Health Check
$grafanaHealth = Get-HttpStatus "$GrafanaUrl/api/health"
if ($grafanaHealth.Code -ne 200) {
    $failures += "Grafana /api/health returned $($grafanaHealth.Code)"
}
else {
    $gJson = $grafanaHealth.Content | ConvertFrom-Json
    if ($gJson.database -ne "ok") { $failures += "Grafana database status: $($gJson.database)" }
}

if ($failures.Count -gt 0) {
    Write-Error ("HEALTH CHECK FAILED:`n - " + ($failures -join "`n - "))
    exit 1
}

Write-Host "[PASS] NGINX routing, external /metrics 403 block, DB/Redis readiness, Alembic (head), ARQ worker heartbeat, Prometheus (10 rules), and Grafana all verified." -ForegroundColor Green
exit 0
