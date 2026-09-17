param([switch]$Apply)

$ErrorActionPreference = 'Stop'
$root = 'C:\'
$destinationRoot = 'C:\PMS\.runtime\release-history\20260917'
$names = @(
    'PMS-enable-production-20260914',
    'PMS-kingdee-20260914',
    'PMS-kingdee-auto-audit-20260914',
    'PMS-kingdee-occupancy-20260914',
    'PMS-login-feedback-20260914',
    'PMS-sync',
    'PMS-unify-20260914',
    'PMS - 副本'
)

$tasks = @(Get-ScheduledTask -TaskName 'PMS-*' -ErrorAction SilentlyContinue)
$taskActions = @($tasks | ForEach-Object { $_.Actions | ForEach-Object { "$(($_.Execute)) $(($_.Arguments))" } })
$processLines = @(Get-CimInstance Win32_Process | ForEach-Object { $_.CommandLine } | Where-Object { $_ })

function Get-DirectoryStats([string]$path) {
    $measure = Get-ChildItem -LiteralPath $path -Recurse -File -Force -ErrorAction Stop |
        Measure-Object -Property Length -Sum
    return [pscustomobject]@{
        Count = $measure.Count
        Bytes = [long]$measure.Sum
    }
}

$planned = @()
foreach ($name in $names) {
    $source = Join-Path $root $name
    $target = Join-Path $destinationRoot $name
    $sourceExists = Test-Path -LiteralPath $source -PathType Container
    $targetExists = Test-Path -LiteralPath $target -PathType Container
    if ($sourceExists -and $targetExists) { throw "Source and target both exist: $name" }
    if (-not $sourceExists -and -not $targetExists) { throw "Directory missing: $name" }
    if ($sourceExists) {
        foreach ($reference in @($taskActions + $processLines)) {
            if ($reference -and $reference.IndexOf("$source\", [StringComparison]::OrdinalIgnoreCase) -ge 0) {
                throw "Active reference to $source; stop and investigate"
            }
        }
    }
    $stats = Get-DirectoryStats $(if ($sourceExists) { $source } else { $target })
    $planned += [pscustomobject]@{
        Name = $name
        Source = $source
        Target = $target
        Files = $stats.Count
        Bytes = $stats.Bytes
        Status = if ($sourceExists) { 'Pending' } else { 'Archived' }
    }
}

$planned | Format-Table Name, Status, Files, Bytes -AutoSize
if (-not $Apply) {
    Write-Output "DRY_RUN=$(@($planned | Where-Object Status -eq 'Pending').Count) pending directories; no files moved"
    return
}

New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null
foreach ($item in $planned) {
    if ($item.Status -eq 'Archived') { continue }
    try {
        Move-Item -LiteralPath $item.Source -Destination $item.Target -ErrorAction Stop
        $verified = Get-DirectoryStats $item.Target
        if ($verified.Count -ne $item.Files -or $verified.Bytes -ne $item.Bytes) {
            throw "Verification failed after move: $($item.Name)"
        }
        $item.Status = 'Archived'
        Write-Output "MOVED=$($item.Name) FILES=$($item.Files) BYTES=$($item.Bytes)"
    } catch {
        if (Test-Path -LiteralPath $item.Target) { throw }
        $item.Status = 'PendingLocked'
        Write-Warning "Move deferred: $($item.Name): $($_.Exception.Message)"
    }
}
$manifest = Join-Path $destinationRoot 'move-manifest.csv'
$planned | Export-Csv -LiteralPath $manifest -NoTypeInformation -Encoding UTF8
Write-Output "VERIFIED=$(@($planned | Where-Object Status -eq 'Archived').Count) PENDING=$(@($planned | Where-Object Status -ne 'Archived').Count) MANIFEST=$manifest"
