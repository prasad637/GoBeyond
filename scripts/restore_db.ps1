<#
.SYNOPSIS
    Safe PostgreSQL restore script for GO BEYOND with checksum verification and anti-overwrite guards.
.DESCRIPTION
    Validates backup existence, SHA-256 checksum, and pg_restore archive contents before executing.
    Refuses to overwrite the active database specified in .env unless -AllowActiveOverwrite
    and interactive exact-name confirmation are provided. Ideal for restoring to an isolated
    temporary or staging database for verification.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,

    [Parameter(Mandatory = $true)]
    [string]$TargetDatabase,

    [string]$EnvFile = ".env",
    [string]$ContainerName = "gobeyond-postgres",
    [switch]$CreateTargetDatabase,
    [switch]$ConfirmRestore,
    [switch]$AllowActiveOverwrite
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
        $map[$parts[0].Trim()] = $parts[1].Trim().Trim('"').Trim("'")
    }
    return $map
}

if (-not (Test-Path $BackupFile)) {
    throw "Backup file does not exist: $BackupFile"
}
$dumpItem = Get-Item $BackupFile
if ($dumpItem.Length -le 0) {
    throw "Backup file is empty (0 bytes): $BackupFile"
}

if ($TargetDatabase -notmatch '^[a-zA-Z_][a-zA-Z0-9_]*$') {
    throw "Invalid PostgreSQL database identifier '$TargetDatabase'. Use alphanumeric/underscore characters only."
}

$shaPath = "$BackupFile.sha256"
if (Test-Path $shaPath) {
    $expectedHash = ((Get-Content $shaPath -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
    $actualHash = (Get-FileHash -Path $BackupFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expectedHash -ne $actualHash) {
        throw "SHA-256 checksum mismatch for $BackupFile (expected $expectedHash, got $actualHash)"
    }
    Write-Host "[RESTORE] SHA-256 checksum verified." -ForegroundColor Green
}

$envMap = Read-EnvMap -Path $EnvFile
$pgUser = $envMap["POSTGRES_USER"]
$activeDb = $envMap["POSTGRES_DB"]
if (-not $pgUser -or -not $activeDb) {
    throw "POSTGRES_USER and POSTGRES_DB must be set in $EnvFile"
}

$pgInspect = Invoke-NativeCapture { docker inspect -f "{{.State.Running}}" $ContainerName }
if ($pgInspect.Code -ne 0 -or $pgInspect.Text.Trim() -ne "true") {
    throw "PostgreSQL container '$ContainerName' is not running."
}

# Strict guard: Never automatically overwrite the active database
if ($TargetDatabase -eq $activeDb) {
    if (-not $AllowActiveOverwrite) {
        throw "SAFETY BLOCK: TargetDatabase '$TargetDatabase' equals active database '$activeDb'. Pass -AllowActiveOverwrite and confirm interactively to overwrite."
    }
    $typed = Read-Host "DANGER: Restoring over ACTIVE database '$activeDb'. Type exact database name '$activeDb' to proceed"
    if ($typed -ne $activeDb) {
        throw "Restore aborted: confirmation did not match '$activeDb'."
    }
}
elseif (-not $ConfirmRestore) {
    $answer = Read-Host "Confirm restore of '$($dumpItem.Name)' into database '$TargetDatabase' (type YES to proceed)"
    if ($answer -ne "YES") {
        throw "Restore aborted by user."
    }
}

$tmpName = "restore_$([System.Guid]::NewGuid().ToString('N').Substring(0,8)).dump"
$containerTmpPath = "/tmp/$tmpName"

try {
    $cpRes = Invoke-NativeCapture { docker cp $dumpItem.FullName "${ContainerName}:${containerTmpPath}" }
    if ($cpRes.Code -ne 0) {
        throw "Failed to copy backup into PostgreSQL container: $($cpRes.Text)"
    }

    # Validate backup archive contents before touching any DB
    $tocRes = Invoke-NativeCapture { docker exec $ContainerName pg_restore --list $containerTmpPath }
    if ($tocRes.Code -ne 0) {
        throw "pg_restore --list failed; archive may be corrupt: $($tocRes.Text)"
    }
    Write-Host ("[RESTORE] Archive validated ({0} TOC lines)." -f $tocRes.Lines.Count) -ForegroundColor Cyan

    $dbExistsRes = Invoke-NativeCapture { docker exec $ContainerName psql -U $pgUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$TargetDatabase';" }
    if ($dbExistsRes.Code -ne 0) {
        throw "Failed querying pg_database: $($dbExistsRes.Text)"
    }

    if ($dbExistsRes.Text.Trim() -ne "1") {
        if (-not $CreateTargetDatabase) {
            throw "Target database '$TargetDatabase' does not exist. Pass -CreateTargetDatabase to create it cleanly."
        }
        Write-Host "[RESTORE] Creating target database '$TargetDatabase'..." -ForegroundColor Cyan
        $createRes = Invoke-NativeCapture { docker exec $ContainerName psql -U $pgUser -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE `"$TargetDatabase`" OWNER `"$pgUser`";" }
        if ($createRes.Code -ne 0) { throw "Failed creating target database '$TargetDatabase': $($createRes.Text)" }
    }
    elseif ($TargetDatabase -eq $activeDb) {
        Write-Host "[RESTORE] Cleaning active schema objects under explicit confirmation..." -ForegroundColor Yellow
        $dropRes = Invoke-NativeCapture { docker exec $ContainerName psql -U $pgUser -d $TargetDatabase -v ON_ERROR_STOP=1 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION `"$pgUser`";" }
        if ($dropRes.Code -ne 0) { throw "Failed resetting public schema on '$TargetDatabase': $($dropRes.Text)" }
    }

    # Ensure required btree_gist extension for dining exclusion constraint
    $extRes = Invoke-NativeCapture { docker exec $ContainerName psql -U $pgUser -d $TargetDatabase -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS btree_gist;" }
    if ($extRes.Code -ne 0) { throw "Failed creating btree_gist extension: $($extRes.Text)" }

    Write-Host "[RESTORE] Restoring backup into '$TargetDatabase'..." -ForegroundColor Cyan
    $restoreRes = Invoke-NativeCapture { docker exec $ContainerName pg_restore -U $pgUser -d $TargetDatabase --no-owner --no-acl --single-transaction --exit-on-error $containerTmpPath }
    if ($restoreRes.Code -ne 0) {
        throw "pg_restore failed with exit code $($restoreRes.Code): $($restoreRes.Text)"
    }

    $verifySql = "SELECT 'alembic_version' AS tbl, COUNT(*) FROM alembic_version UNION ALL SELECT 'users', COUNT(*) FROM users UNION ALL SELECT 'locations', COUNT(*) FROM locations UNION ALL SELECT 'partners', COUNT(*) FROM partners UNION ALL SELECT 'movies', COUNT(*) FROM movies UNION ALL SELECT 'restaurants', COUNT(*) FROM restaurants UNION ALL SELECT 'events', COUNT(*) FROM events UNION ALL SELECT 'sports_venues', COUNT(*) FROM sports_venues UNION ALL SELECT 'activities', COUNT(*) FROM activities UNION ALL SELECT 'coupons', COUNT(*) FROM coupons;"
    Write-Host "[RESTORE] Verified row counts in '$TargetDatabase':" -ForegroundColor Green
    $cntRes = Invoke-NativeCapture { docker exec $ContainerName psql -U $pgUser -d $TargetDatabase -c $verifySql }
    Write-Output $cntRes.Text
}
finally {
    Invoke-NativeCapture { docker exec $ContainerName rm -f $containerTmpPath } | Out-Null
}
