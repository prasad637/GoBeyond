<#
.SYNOPSIS
    Safe PostgreSQL backup script for GO BEYOND using pg_dump custom compressed format (-Fc).
.DESCRIPTION
    Creates timestamped PostgreSQL backups inside backups/postgres/, writes a SHA-256 checksum,
    verifies archive readability via pg_restore --list, optionally snapshots Redis dump.rdb,
    and prunes expired backups safely while retaining at least -KeepMinimum archives.
    Never prints database passwords or modifies live data.
#>
[CmdletBinding()]
param(
    [string]$EnvFile = ".env",
    [string]$BackupDir = "backups",
    [string]$ContainerName = "gobeyond-postgres",
    [string]$RedisContainerName = "gobeyond-redis",
    [int]$RetentionDays = 14,
    [int]$KeepMinimum = 5,
    [switch]$IncludeRedisRdb
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

function Read-EnvMap([string]$Path) {
    if (-not (Test-Path $Path)) {
        throw "Environment file not found: $Path"
    }
    $map = @{}
    foreach ($rawLine in Get-Content $Path) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { continue }
        $parts = $line -split "=", 2
        $k = $parts[0].Trim()
        $v = $parts[1].Trim().Trim('"').Trim("'")
        $map[$k] = $v
    }
    return $map
}

$envMap = Read-EnvMap -Path $EnvFile
$pgUser = $envMap["POSTGRES_USER"]
$pgDb = $envMap["POSTGRES_DB"]
if (-not $pgUser -or -not $pgDb) {
    throw "POSTGRES_USER and POSTGRES_DB must be set in $EnvFile"
}

$pgInspect = Invoke-NativeCapture { docker inspect -f "{{.State.Running}}" $ContainerName }
if ($pgInspect.Code -ne 0 -or $pgInspect.Text.Trim() -ne "true") {
    throw "PostgreSQL container '$ContainerName' is not running."
}

$pgBackupDir = Join-Path $BackupDir "postgres"
New-Item -ItemType Directory -Force -Path $pgBackupDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dumpFileName = "${pgDb}_${timestamp}.dump"
$hostDumpPath = Join-Path $pgBackupDir $dumpFileName
$containerTmpPath = "/tmp/$dumpFileName"

Write-Host "[BACKUP] Creating PostgreSQL custom-format dump for database '$pgDb'..." -ForegroundColor Cyan

try {
    $dumpRes = Invoke-NativeCapture { docker exec $ContainerName pg_dump -U $pgUser -d $pgDb -Fc -Z 6 --no-owner --no-acl -f $containerTmpPath }
    if ($dumpRes.Code -ne 0) {
        throw "pg_dump exited with code $($dumpRes.Code): $($dumpRes.Text)"
    }

    # Validate archive readability before copying out
    $listRes = Invoke-NativeCapture { docker exec $ContainerName sh -c "pg_restore --list '$containerTmpPath' > /dev/null" }
    if ($listRes.Code -ne 0) {
        throw "Backup archive validation (pg_restore --list) failed: $($listRes.Text)"
    }

    $cpRes = Invoke-NativeCapture { docker cp "${ContainerName}:${containerTmpPath}" $hostDumpPath }
    if ($cpRes.Code -ne 0 -or -not (Test-Path $hostDumpPath)) {
        throw "Failed to copy backup archive from container: $($cpRes.Text)"
    }
}
finally {
    Invoke-NativeCapture { docker exec $ContainerName rm -f $containerTmpPath } | Out-Null
}

$fileInfo = Get-Item $hostDumpPath
if ($fileInfo.Length -le 0) {
    throw "Backup file is empty: $hostDumpPath"
}

$hash = (Get-FileHash -Path $hostDumpPath -Algorithm SHA256).Hash.ToLowerInvariant()
$shaPath = "${hostDumpPath}.sha256"
"$hash  $dumpFileName" | Out-File -FilePath $shaPath -Encoding ascii -NoNewline

Write-Host ("[BACKUP] Verified dump: {0} ({1:N0} bytes, sha256={2}...)" -f $hostDumpPath, $fileInfo.Length, $hash.Substring(0, 12)) -ForegroundColor Green

if ($IncludeRedisRdb) {
    $redisInspect = Invoke-NativeCapture { docker inspect -f "{{.State.Running}}" $RedisContainerName }
    if ($redisInspect.Code -eq 0 -and $redisInspect.Text.Trim() -eq "true") {
        $redisBackupDir = Join-Path $BackupDir "redis"
        New-Item -ItemType Directory -Force -Path $redisBackupDir | Out-Null
        $lastSaveBefore = (Invoke-NativeCapture { docker exec $RedisContainerName redis-cli LASTSAVE }).Text.Trim()
        Invoke-NativeCapture { docker exec $RedisContainerName redis-cli BGSAVE } | Out-Null
        for ($i = 0; $i -lt 15; $i++) {
            Start-Sleep -Milliseconds 300
            $lastSaveAfter = (Invoke-NativeCapture { docker exec $RedisContainerName redis-cli LASTSAVE }).Text.Trim()
            if ($lastSaveAfter -ne $lastSaveBefore) { break }
        }
        $rdbHostPath = Join-Path $redisBackupDir "redis_${timestamp}.rdb"
        $rdbCp = Invoke-NativeCapture { docker cp "${RedisContainerName}:/data/dump.rdb" $rdbHostPath }
        if ($rdbCp.Code -eq 0 -and (Test-Path $rdbHostPath)) {
            Write-Host "[BACKUP] Redis RDB snapshot saved: $rdbHostPath" -ForegroundColor Green
        }
        else {
            Write-Warning "Redis BGSAVE did not produce /data/dump.rdb (AOF appendonlydir still active in redis_data volume)."
        }
    }
}

# Safe retention pruning (preserve at least $KeepMinimum newest dumps)
if ($RetentionDays -gt 0) {
    $cutoff = (Get-Date).AddDays(-$RetentionDays)
    $allDumps = @(Get-ChildItem -Path $pgBackupDir -Filter "*.dump" | Sort-Object LastWriteTime -Descending)
    if ($allDumps.Count -gt $KeepMinimum) {
        $candidates = $allDumps | Select-Object -Skip $KeepMinimum | Where-Object { $_.LastWriteTime -lt $cutoff }
        foreach ($old in $candidates) {
            Remove-Item -Force -Path $old.FullName -ErrorAction SilentlyContinue
            Remove-Item -Force -Path ($old.FullName + ".sha256") -ErrorAction SilentlyContinue
            Write-Host "[RETENTION] Pruned expired backup: $($old.Name)" -ForegroundColor Yellow
        }
    }
}

Write-Output $hostDumpPath
